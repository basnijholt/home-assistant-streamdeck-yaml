#!/usr/bin/env python3
"""Home Assistant Stream Deck integration."""
from __future__ import annotations

import asyncio
import functools as ft
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal

import cairosvg
import jinja2
import matplotlib.pyplot as plt
import numpy as np
import requests
import websockets
import yaml
from lxml import etree
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, Field, validator
from rich.console import Console
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

console = Console()


if TYPE_CHECKING:
    from collections.abc import Coroutine

    from StreamDeck.Devices import StreamDeck

SCRIPT_DIR = Path(__file__).parent
ASSETS_PATH = SCRIPT_DIR / "assets"
DEFAULT_CONFIG = SCRIPT_DIR / "configuration.yaml"
DEFAULT_MDI_ICONS = {"light": "lightbulb", "switch": "power-socket-eu"}
ICON_PIXELS = 72
_ID_COUNTER = 0


class Button(BaseModel, extra="forbid"):  # type: ignore[call-arg]
    """Button configuration."""

    entity_id: str | None = None
    service: str | None = None
    service_data: dict[str, Any] | None = None
    text: str = ""
    text_color: str | None = None
    text_size: int = 12
    icon: str | None = None
    icon_mdi: str | None = None
    icon_background_color: str = "#000000"
    icon_mdi_color: str | None = None
    icon_gray_when_off: bool = False
    special_type: Literal[
        "next-page",
        "previous-page",
        "empty",
        "go-to-page",
        "light-control",
    ] | None = None
    special_type_data: Any | None = None

    @property
    def domain(self) -> str | None:
        """Return the domain of the entity."""
        if self.service is None:
            return None
        return self.service.split(".", 1)[0]

    @property
    def templatable(self) -> set[str]:
        """Return if an attribute is templatable, which is if the type-annotation is str."""
        return {
            "entity_id",
            "service",
            "service_data",
            "text",
            "text_color",
            "icon",
            "icon_mdi",
            "icon_mdi_color",
        }

    def rendered_button(self, complete_state: dict[str, dict[str, Any]]) -> Button:
        """Return a button with the rendered text."""
        rendered_button = self.copy()
        for field_name in self.templatable:
            field_value = getattr(self, field_name)
            if isinstance(field_value, dict):  # e.g., service_data
                new = {}
                for k, v in field_value.items():
                    new[k] = _render_jinja(v, complete_state)
            elif isinstance(field_value, str):
                new = _render_jinja(field_value, complete_state)  # type: ignore[assignment]
            else:
                new = field_value
            setattr(rendered_button, field_name, new)
        return rendered_button

    def render_icon(self) -> str | None:
        """Render the icon."""
        if self.icon is None:
            return None

        if ":" in self.icon:
            which, id_ = self.icon.split(":", 1)
            if which == "spotify":
                filename = _to_filename(self.icon, ".jpeg")
                _download_spotify_image(id_, filename)
                return str(filename)

        return self.icon

    @validator("special_type_data")
    def _validate_special_type(
        cls: type[Button],
        v: Any,
        values: dict[str, Any],
    ) -> Any:
        """Validate the special_type_data."""
        special_type = values["special_type"]
        if special_type == "go-to-page" and not isinstance(v, (int, str)):
            msg = (
                "If special_type is go-to-page, special_type_data must be an int or str"
            )
            raise AssertionError(msg)
        if special_type in {"next-page", "previous-page", "empty"} and v is not None:
            msg = f"special_type_data needs to be empty with {special_type=}"
            raise AssertionError(msg)
        if special_type == "light-control":
            data = values.get("special_type_data")
            if data is None:
                return v
            assert isinstance(data, dict)
            assert "colormap" in data
        return v


def _to_filename(id_: str, suffix: str = "") -> Path:
    """Converts an id with ":" and "_" to a filename with optional suffix."""
    filename = ASSETS_PATH / id_.replace("/", "_").replace(":", "_")
    return filename.with_suffix(suffix)


class Page(BaseModel):
    """A page of buttons."""

    name: str
    buttons: list[Button] = Field(default_factory=list)


class Config(BaseModel):
    """Configuration file."""

    pages: list[Page] = Field(default_factory=list)
    current_page_index: int = 0
    special_page: Page | None = None

    def next_page(self) -> Page:
        """Go to the next page."""
        self.current_page_index = self.next_page_index
        return self.pages[self.current_page_index]

    @property
    def next_page_index(self) -> int:
        """Return the next page index."""
        return (self.current_page_index + 1) % len(self.pages)

    @property
    def previous_page_index(self) -> int:
        """Return the previous page index."""
        return (self.current_page_index - 1) % len(self.pages)

    def previous_page(self) -> Page:
        """Go to the previous page."""
        self.current_page_index = self.previous_page_index
        return self.pages[self.current_page_index]

    def current_page(self) -> Page:
        """Return the current page."""
        if self.special_page is not None:
            return self.special_page
        return self.pages[self.current_page_index]

    def button(self, key: int) -> Button:
        """Return the button for a key."""
        return self.current_page().buttons[key]

    def to_page(self, page: int | str) -> Page:
        """Go to a page based on the page name or index."""
        if isinstance(page, int):
            self.current_page_index = page
        else:
            for i, p in enumerate(self.pages):
                if p.name == page:
                    self.current_page_index = i
                    break
        return self.current_page()


def _next_id() -> int:
    global _ID_COUNTER
    _ID_COUNTER += 1
    return _ID_COUNTER


def _generate_colors(num_colors: int, colormap: str = "hsv") -> list[str]:
    """Returns `num_colors` number of colors in hexadecimal format, sampled from colormaps."""
    cmap = plt.get_cmap(colormap)
    colors = cmap(np.linspace(0, 1, num_colors))
    return [plt.matplotlib.colors.to_hex(color) for color in colors]


@ft.lru_cache(maxsize=16)
def _light_page(
    entity_id: str,
    n_colors: int = 10,
    colormap: str = "plasma",
) -> Page:
    """Return a page of buttons for controlling lights."""
    # List of 10 colors
    colors = _generate_colors(n_colors, colormap)
    buttons_colors = [
        Button(
            icon_background_color=color,
            service="light.turn_on",
            service_data={
                "entity_id": entity_id,
                "rgb_color": _hex_to_rgb(color),
            },
        )
        for color in colors
    ]
    buttons_brightness = [
        Button(
            icon_background_color=_scale_hex_color("#FFFFFF", brightness / 100),
            service="light.turn_on",
            text_color=_scale_hex_color("#FFFFFF", 0.8 - brightness / 100),
            text=f"{brightness}%",
            service_data={
                "entity_id": entity_id,
                "brightness_pct": brightness,
            },
        )
        for brightness in [0, 10, 30, 60, 100]
    ]
    return Page(name="Lights", buttons=buttons_colors + buttons_brightness)


@asynccontextmanager
async def setup_ws(host: str, token: str) -> websockets.WebSocketClientProtocol:
    """Set up the connection to Home Assistant."""
    uri = f"wss://{host}/api/websocket"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                # Send an authentication message to Home Assistant
                auth_payload = {"type": "auth", "access_token": token}
                await websocket.send(json.dumps(auth_payload))

                # Wait for the authentication response
                auth_response = await websocket.recv()
                console.log(auth_response)
                console.log("Connected to Home Assistant")
                yield websocket
        except ConnectionResetError:
            # Connection was reset, retrying in 3 seconds
            console.print_exception(show_locals=True)
            console.log("Connection was reset, retrying in 3 seconds")
            await asyncio.sleep(5)


async def subscribe_state_changes(
    websocket: websockets.WebSocketClientProtocol,
) -> None:
    """Subscribe to the state change events."""
    subscribe_payload = {
        "type": "subscribe_events",
        "event_type": "state_changed",
        "id": _next_id(),
    }
    await websocket.send(json.dumps(subscribe_payload))


async def handle_state_changes(
    websocket: websockets.WebSocketClientProtocol,
    complete_state: dict[str, dict[str, Any]],
    deck: StreamDeck,
    config: Config,
) -> None:
    """Handle state changes."""
    # Wait for the state change events
    while True:
        data = json.loads(await websocket.recv())
        _update_state(complete_state, data, config, deck)


def _keys(entity_id: str, buttons: list[Button]) -> list[int]:
    """Get the key indices for an entity_id."""
    return [i for i, button in enumerate(buttons) if button.entity_id == entity_id]


def _update_state(
    complete_state: dict[str, dict[str, Any]],
    data: dict[str, Any],
    config: Config,
    deck: StreamDeck,
) -> None:
    """Update the state dictionary and update the keys."""
    buttons = config.current_page().buttons
    if data["type"] == "event":
        event_data = data["event"]
        if event_data["event_type"] == "state_changed":
            event_data = event_data["data"]
            eid = event_data["entity_id"]
            complete_state[eid] = event_data["new_state"]
            keys = _keys(eid, buttons)
            for key in keys:
                console.log(f"Updating key {key} for {eid}")
                update_key_image(
                    deck,
                    key=key,
                    config=config,
                    complete_state=complete_state,
                    key_pressed=False,
                )


def _state_attr(
    entity_id: str,
    attr: str,
    complete_state: dict[str, dict[str, Any]],
) -> Any:
    """Get the state attribute for an entity."""
    return complete_state.get(entity_id, {}).get("attributes", {}).get(attr)


def _is_state_attr(
    entity_id: str,
    attr: str,
    value: Any,
    complete_state: dict[str, dict[str, Any]],
) -> bool:
    """Check if the state attribute for an entity is a value."""
    return _state_attr(entity_id, attr, complete_state) == value


def _states(
    entity_id: str,
    *,
    with_unit: bool = False,
    rounded: bool = False,
    complete_state: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """Get the state for an entity."""
    assert complete_state is not None
    entity_state = complete_state.get(entity_id, {})
    if not entity_state:
        return None
    state = entity_state["state"]
    if with_unit:
        unit = entity_state.get("attributes", {}).get("unit_of_measurement")
        if unit:
            state += f" {unit}"
    if rounded:
        state = round(float(state))
    return state  # noqa: RET504


def _is_state(
    entity_id: str,
    state: str,
    complete_state: dict[str, dict[str, Any]],
) -> bool:
    """Check if the state for an entity is a value."""
    return _states(entity_id, complete_state=complete_state) == state


def _render_jinja(text: str, complete_state: dict[str, dict[str, Any]]) -> str:
    """Render a Jinja template."""
    try:
        if not isinstance(text, str):
            return text
        if "{" not in text:
            return text
        template = jinja2.Template(text)
        return template.render(  # noqa: TRY300
            min=min,
            max=max,
            is_state_attr=ft.partial(_is_state_attr, complete_state=complete_state),
            state_attr=ft.partial(_state_attr, complete_state=complete_state),
            states=ft.partial(_states, complete_state=complete_state),
            is_state=ft.partial(_is_state, complete_state=complete_state),
        )
    except jinja2.exceptions.TemplateError as err:
        console.print_exception(show_locals=True)
        console.log(f"Error rendering template: {err} with error type {type(err)}")
        return text


async def get_states(websocket: websockets.WebSocketClientProtocol) -> dict[str, Any]:
    """Get the current state of all entities."""
    _id = _next_id()
    subscribe_payload = {"type": "get_states", "id": _id}
    await websocket.send(json.dumps(subscribe_payload))
    while True:
        data = json.loads(await websocket.recv())
        if data["type"] == "result":
            # Extract the state data from the response
            state_dict = {state["entity_id"]: state for state in data["result"]}
            console.log(state_dict)
            return state_dict


async def unsubscribe(websocket: websockets.WebSocketClientProtocol, id_: int) -> None:
    """Unsubscribe from an event."""
    subscribe_payload = {
        "id": _next_id(),
        "type": "unsubscribe_events",
        "subscription": id_,
    }
    await websocket.send(json.dumps(subscribe_payload))


async def call_service(
    websocket: websockets.WebSocketClientProtocol,
    service: str,
    data: dict[str, Any],
) -> None:
    """Call a service."""
    domain, service = service.split(".")
    subscribe_payload = {
        "id": _next_id(),
        "type": "call_service",
        "domain": domain,
        "service": service,
        "service_data": data,
    }
    await websocket.send(json.dumps(subscribe_payload))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert an RGB color to a hex color."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    # Remove '#' if present
    if hex_color.startswith("#"):
        hex_color = hex_color[1:]

    # Convert hexadecimal to RGB
    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    # Return RGB tuple
    return (r, g, b)


def _named_to_hex(color: str) -> str:
    """Convert a named color to a hex color."""
    rgb: tuple[int, int, int] | str = ImageColor.getrgb(color)
    if isinstance(rgb, tuple):
        return _rgb_to_hex(rgb)
    if color.startswith("#"):
        return color
    msg = f"Invalid color: {color}"
    raise ValueError(msg)


def _convert_to_grayscale(image: Image.Image) -> Image.Image:
    """Convert an image to grayscale."""
    return image.convert("L").convert("RGB")


def _download_and_save_mdi(icon_mdi: str) -> Path:
    url = _mdi_url(icon_mdi)
    filename_svg = ASSETS_PATH / f"{icon_mdi}.svg"
    if filename_svg.exists():
        return filename_svg
    svg_content = _download(url)
    with filename_svg.open("wb") as f:
        f.write(svg_content)
    return filename_svg


def _init_icon(
    *,
    icon_filename: str | None = None,
    icon_mdi: str | None = None,
    icon_mdi_margin: int | None = None,
    icon_mdi_color: str | None = None,  # hex color
    icon_background_color: str | None = None,  # hex color
    icon_convert_to_grayscale: bool = False,
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
    """Initialize the icon."""
    if icon_filename is not None:
        icon = Image.open(ASSETS_PATH / icon_filename)
        if icon_convert_to_grayscale:
            icon = _convert_to_grayscale(icon)
        return icon
    if icon_mdi is not None:
        assert icon_mdi_margin is not None
        filename_svg = _download_and_save_mdi(icon_mdi)
        return _convert_svg_to_png(
            filename_svg=filename_svg,
            color=icon_mdi_color,
            background_color=icon_background_color,
            opacity=0.3,
            margin=icon_mdi_margin,
            size=size,
        )
    if icon_background_color is None:
        icon_background_color = "white"
    color = _named_to_hex(icon_background_color)
    rgb_color = _hex_to_rgb(color)
    return Image.new("RGB", size, rgb_color)


def render_key_image(
    deck: StreamDeck,
    *,
    text_color: str = "white",
    icon_filename: str | None = None,
    icon_background_color: str = "#000000",
    icon_convert_to_grayscale: bool = False,
    icon_mdi: str | None = None,
    icon_mdi_margin: int = 0,
    icon_mdi_color: str | None = None,
    font_filename: str = "Roboto-Regular.ttf",
    font_size: int = 12,
    label_text: str = "",
) -> memoryview:
    """Render an image for a key."""
    size = (deck.KEY_PIXEL_WIDTH, deck.KEY_PIXEL_HEIGHT)
    icon = _init_icon(
        icon_background_color=icon_background_color,
        icon_filename=icon_filename,
        icon_mdi=icon_mdi,
        icon_mdi_margin=icon_mdi_margin,
        icon_mdi_color=_named_to_hex(icon_mdi_color or text_color),
        icon_convert_to_grayscale=icon_convert_to_grayscale,
        size=size,
    )
    image = PILHelper.create_scaled_image(deck, icon, margins=[0, 0, 0, 0])
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ASSETS_PATH / font_filename), font_size)
    draw.text(
        (image.width / 2, image.height / 2),
        text=label_text,
        font=font,
        anchor="ms",
        fill=text_color,
        align="center",
    )
    return PILHelper.to_native_format(deck, image)


def update_key_image(
    deck: StreamDeck,
    *,
    key: int,
    config: Config,
    complete_state: dict[str, dict[str, Any]],
    key_pressed: bool = False,
) -> None:
    """Update the image for a key."""
    button = config.button(key)
    if button.special_type == "empty":
        return
    button = button.rendered_button(complete_state)
    icon_convert_to_grayscale = False
    text = button.text
    text_color = button.text_color or "white"
    icon_mdi = button.icon_mdi

    if button.special_type == "next-page":
        text = button.text or "Next\nPage"
        icon_mdi = button.icon_mdi or "chevron-right"
    elif button.special_type == "previous-page":
        text = button.text or "Previous\nPage"
        icon_mdi = button.icon_mdi or "chevron-left"
    elif button.special_type == "go-to-page":
        page = button.special_type_data
        text = button.text or f"Go to\nPage\n{page}"
        icon_mdi = button.icon_mdi or "book-open-page-variant"
    elif button.entity_id in complete_state:
        # Has entity_id
        state = complete_state[button.entity_id]

        if button.text_color is not None:
            text_color = button.text_color
        elif state["state"] == "on":
            text_color = "orangered"

        if (
            button.icon_mdi is None
            and button.icon is None
            and button.domain in DEFAULT_MDI_ICONS
        ):
            icon_mdi = DEFAULT_MDI_ICONS[button.domain]

        if state["state"] == "off":
            icon_convert_to_grayscale = button.icon_gray_when_off

    image = render_key_image(
        deck,
        label_text=text,
        text_color=text_color if not key_pressed else "green",
        icon_mdi=icon_mdi,
        icon_background_color=button.icon_background_color,
        icon_filename=button.render_icon(),
        icon_mdi_color=button.icon_mdi_color,
        icon_convert_to_grayscale=icon_convert_to_grayscale,
        font_size=button.text_size,
    )
    with deck:
        deck.set_key_image(key, image)


def get_deck() -> StreamDeck:
    """Get the first Stream Deck device found on the system."""
    streamdecks = DeviceManager().enumerate()
    found = False
    for deck in streamdecks:
        if not deck.is_visual():
            continue
        deck.open()
        deck.reset()
        found = True
        break
    if not found:
        msg = "No Stream Deck found"
        raise RuntimeError(msg)
    console.log(f"Found {deck.key_count()} keys, {deck=}")
    return deck


def read_config(fname: Path) -> Config:
    """Read the configuration file."""
    with fname.open() as f:
        data = yaml.safe_load(f)
        return Config(pages=data["pages"])


async def _handle_key_press(
    websocket: websockets.WebSocketClientProtocol,
    complete_state: dict[str, dict[str, Any]],
    config: Config,
    key: int,
    deck: StreamDeck,
) -> None:
    button = config.button(key)
    if button.special_type == "next-page":
        config.next_page()
        deck.reset()
        update_all_key_images(deck, config, complete_state)
    elif button.special_type == "previous-page":
        config.previous_page()
        deck.reset()
        update_all_key_images(deck, config, complete_state)
    elif button.special_type == "go-to-page":
        config.to_page(button.special_type_data)  # type: ignore[arg-type]
        deck.reset()
        update_all_key_images(deck, config, complete_state)
    elif button.special_type == "light-control":
        assert config.special_page is not None
        page = _light_page(
            entity_id=button.entity_id,
            n_colors=10,
            colormap=config.special_page["colormap"],
        )
        config.special_page = page
        deck.reset()
        update_all_key_images(deck, config, complete_state)
    elif button.service is not None:
        button = button.rendered_button(complete_state)
        if button.service_data is None:
            service_data = {}
            if button.entity_id is not None:
                service_data["entity_id"] = button.entity_id
        else:
            service_data = button.service_data
        console.log(f"Calling service {button.service} with data {service_data}")
        assert button.service is not None  # for mypy
        await call_service(websocket, button.service, service_data)


def _on_press_callback(
    websocket: websockets.WebSocketClientProtocol,
    complete_state: dict[str, dict[str, Any]],
    config: Config,
) -> Callable[[StreamDeck, int, bool], Coroutine[StreamDeck, int, None]]:
    async def key_change_callback(
        deck: StreamDeck,
        key: int,
        key_pressed: bool,  # noqa: FBT001
    ) -> None:
        console.log(f"Key {key} {'pressed' if key_pressed else 'released'}")
        try:
            update_key_image(
                deck,
                key=key,
                config=config,
                complete_state=complete_state,
                key_pressed=key_pressed,
            )
            if key_pressed:
                has_special_page = config.special_page is not None
                await _handle_key_press(websocket, complete_state, config, key, deck)
                if has_special_page:
                    # Reset after a keypress
                    config.special_page = None
                    # Reset all icons
                    update_all_key_images(deck, config, complete_state)
        except Exception as e:  # noqa: BLE001
            console.print_exception(show_locals=True)
            console.log(f"key_change_callback failed with a {type(e)}: {e}")

    return key_change_callback


@ft.lru_cache(maxsize=128)
def _download(url: str) -> bytes:
    """Download the content from the URL."""
    response = requests.get(url, timeout=5)
    return response.content


def _scale_hex_color(hex_color: str, scale: float) -> str:
    """Scales a HEX color by a given factor.

    0 is black, 1 is the original color.

    Parameters
    ----------
    hex_color
        A HEX color in the format "#RRGGBB".
    scale
        A scaling factor between 0 and 1.

    Returns
    -------
    A scaled HEX color in the format "#RRGGBB".
    """
    scale = max(0, min(1, scale))
    # Convert HEX color to RGB values
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    # Scale RGB values
    r = int(r * scale)
    g = int(g * scale)
    b = int(b * scale)

    # Convert scaled RGB values back to HEX color
    return f"#{r:02x}{g:02x}{b:02x}"


@ft.lru_cache(maxsize=128)
def _convert_svg_to_png(
    *,
    filename_svg: Path,
    color: str,
    background_color: str,
    opacity: float,
    margin: int,
    filename_png: str | Path | None = None,
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
    """Load a SVG file and convert to PNG.

    Modify the fill and background colors based on the input color value,
    convert it to PNG format, and save the resulting PNG image to a file.

    Parameters
    ----------
    filename_svg
        The file name of the SVG file.
    color
        The HEX color to use for the icon.
    background_color
        The HEX color to use for the background.
    opacity
        The opacity of the icon. 0 is black, 1 is full color.
    margin
        The margin to add around the icon.
    filename_png
        The name of the file to save the PNG content to.
    size
        The size of the resulting PNG image.
    """
    with filename_svg.open() as f:
        svg_content = f.read()
    # Modify the SVG content to set the fill and background colors
    svg_tree = etree.fromstring(svg_content)
    fill_color = _scale_hex_color(color, opacity)
    svg_tree.attrib["fill"] = fill_color
    svg_tree.attrib["style"] = f"background-color: {background_color}"
    modified_svg_content = etree.tostring(svg_tree)

    # Convert the modified SVG content to PNG format using cairosvg
    png_content = cairosvg.svg2png(
        bytestring=modified_svg_content,
        background_color=background_color,
        scale=4,
    )

    # Save the resulting PNG image to a file using Pillow
    with Image.open(io.BytesIO(png_content)) as image:
        im = ImageOps.expand(image, border=(margin, margin), fill="black")
        im = im.resize(size)
        if filename_png is not None:
            im.save(filename_png)
    return im


def _mdi_url(mdi: str) -> str:
    """Return the URL of the Materian. opacity=Design Ico,.

    Check https://mdi.bessarabov.com for the available icons.
    """
    return f"https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg/{mdi}.svg"


@ft.lru_cache(maxsize=128)
def _download_spotify_image(
    id_: str,
    filename: Path | None = None,
) -> Image.Image | None:
    """Download the Spotify image for the given ID.

    Examples of ids are:
    - "playlist/37i9dQZF1DXaRycgyh6kXP"
    - "episode/3RIaY4PM7h4mO2IaD0eSXo"
    - "track/4o0LyB69tylqDG6eTGhmig"
    """
    if filename is not None and filename.exists():
        return Image.open(filename)
    url = f"https://embed.spotify.com/oembed/?url=http://open.spotify.com/{id_}"
    content = _download(url)
    data = json.loads(content)
    image_url = data["thumbnail_url"]
    image_content = _download(image_url)
    image = Image.open(io.BytesIO(image_content))
    if filename is not None:
        image.save(filename)
        return None
    return image


def update_all_key_images(
    deck: StreamDeck,
    config: Config,
    complete_state: dict[str, dict[str, Any]],
) -> None:
    """Update all key images."""
    for key in range(deck.key_count()):
        update_key_image(
            deck,
            key=key,
            config=config,
            complete_state=complete_state,
            key_pressed=False,
        )


async def run(host: str, token: str, config: Config) -> None:
    """Main entry point for the Stream Deck integration."""
    deck = get_deck()
    async with setup_ws(host, token) as websocket:
        complete_state = await get_states(websocket)
        update_all_key_images(deck, config, complete_state)
        deck.set_key_callback_async(
            _on_press_callback(websocket, complete_state, config),
        )
        deck.set_brightness(100)
        await subscribe_state_changes(websocket)
        await handle_state_changes(websocket, complete_state, deck, config)


def main() -> None:
    """Start the Stream Deck integration."""
    import argparse
    import os

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HASS_HOST", "localhost"))
    parser.add_argument("--token", default=os.environ.get("HASS_TOKEN"))
    parser.add_argument(
        "--config",
        default=os.environ.get("STREAMDECK_CONFIG", DEFAULT_CONFIG),
        type=Path,
    )
    args = parser.parse_args()
    config = read_config(args.config)
    asyncio.run(run(host=args.host, token=args.token, config=config))


if __name__ == "__main__":
    main()
