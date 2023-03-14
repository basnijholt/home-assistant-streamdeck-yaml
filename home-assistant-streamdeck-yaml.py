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
import requests
import rich
import websockets
import yaml
from lxml import etree
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, Field
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from StreamDeck.Devices import StreamDeck

ASSETS_PATH = Path(__file__).parent / "assets"

DEFAULT_MDI_ICONS = {"light": "lightbulb", "switch": "power-socket-eu"}

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
    icon_gray_when_off: bool = False
    special_type: Literal["next-page", "previous-page", "empty"] | None = None

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


class Page(BaseModel):
    """A page of buttons."""

    name: str
    buttons: list[Button] = Field(default_factory=list)


class Config(BaseModel):
    """Configuration file."""

    pages: list[Page] = Field(default_factory=list)
    current_page_index: int = 0

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
        return self.pages[self.current_page_index]

    def button(self, key: int) -> Button:
        """Return the button for a key."""
        return self.current_page().buttons[key]


def _next_id() -> int:
    global _ID_COUNTER
    _ID_COUNTER += 1
    return _ID_COUNTER


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
                rich.print(auth_response)
                rich.print("Connected to Home Assistant")
                yield websocket
        except ConnectionResetError:
            # Connection was reset, retrying in 3 seconds
            rich.print("Connection was reset, retrying in 3 seconds")
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
                rich.print(f"Updating key {key} for {eid}")
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
        rich.print(f"Error rendering template: {err} with error type {type(err)}")
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
            rich.print(state_dict)
            await unsubscribe(websocket, _id)
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


def _named_to_hex(color: str) -> str:
    """Convert a named color to a hex color."""
    rgb: tuple[int, int, int] = ImageColor.getrgb(color)
    color = "#{:02x}{:02x}{:02x}".format(*rgb)
    if color.startswith("#"):
        return color
    msg = f"Invalid color: {color}"
    raise ValueError(msg)


def _convert_to_grayscale(image: Image) -> Image:
    """Convert an image to grayscale."""
    return image.convert("L").convert("RGB")


def render_key_image(
    deck: StreamDeck,
    *,
    text_color: str = "white",
    icon_filename: str | None = None,
    icon_convert_to_grayscale: bool = False,
    icon_mdi: str | None = None,
    icon_mdi_margin: int = 0,
    font_filename: str = "Roboto-Regular.ttf",
    font_size: int = 12,
    label_text: str = "",
) -> memoryview:
    """Render an image for a key."""
    if icon_filename is not None:
        icon = Image.open(ASSETS_PATH / icon_filename)
        if icon_convert_to_grayscale:
            icon = _convert_to_grayscale(icon)
    elif icon_mdi is not None:
        url = _mdi_url(icon_mdi)
        icon = _download_and_convert_svg_to_png(
            url=url,
            color=_named_to_hex(text_color),
            opacity=0.3,
            margin=icon_mdi_margin,
        )
    else:
        icon = Image.new("RGB", (deck.KEY_PIXEL_WIDTH, deck.KEY_PIXEL_HEIGHT), "black")
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
        text = "Next\nPage"
        icon_mdi = "chevron-right"
    elif button.special_type == "previous-page":
        text = "Previous\nPage"
        icon_mdi = "chevron-left"
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
        icon_filename=button.icon,
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
    print(f"Found {deck.key_count()} keys, {deck=}")
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
    elif button.service is not None:
        button = button.rendered_button(complete_state)
        if button.service_data is None:
            service_data = {}
            if button.entity_id is not None:
                service_data["entity_id"] = button.entity_id
        else:
            service_data = button.service_data
        rich.print(
            f"Calling service {button.service} with data {service_data}",
            flush=True,
        )
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
        rich.print(f"Key {key} {'pressed' if key_pressed else 'released'}")
        try:
            update_key_image(
                deck,
                key=key,
                config=config,
                complete_state=complete_state,
                key_pressed=key_pressed,
            )
            if key_pressed:
                await _handle_key_press(websocket, complete_state, config, key, deck)
        except Exception as e:  # noqa: BLE001
            rich.print(f"key_change_callback failed with a {type(e)}: {e}")

    return key_change_callback


@ft.lru_cache(maxsize=128)
def _download(url: str) -> bytes:
    """Download the content from the URL."""
    response = requests.get(url, timeout=5)
    return response.content


def _scale_hex_color(hex_color: str, scale: float) -> str:
    """Scales a HEX color by a given factor.

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
def _download_and_convert_svg_to_png(
    *,
    url: str,
    color: str,
    opacity: float,
    margin: int,
    filename: str | Path | None = None,
) -> Image:
    """Download an SVG file from a given URL to PNG.

    Modify the fill and background colors based on the input color value,
    convert it to PNG format, and save the resulting PNG image to a file.

    Parameters
    ----------
    url
        The URL of the SVG file.
    color
        The HEX color to use for the icon.
    opacity
        The opacity of the icon. 0 is black, 1 is full color.
    margin
        The margin to add around the icon.
    filename
        The name of the file to save the PNG content to.
    """
    svg_content = _download(url)

    # Modify the SVG content to set the fill and background colors
    svg_tree = etree.fromstring(svg_content)
    fill_color = _scale_hex_color(color, opacity)
    svg_tree.attrib["fill"] = fill_color
    svg_tree.attrib["style"] = "background-color: #000000"
    modified_svg_content = etree.tostring(svg_tree)

    # Convert the modified SVG content to PNG format using cairosvg
    png_content = cairosvg.svg2png(
        bytestring=modified_svg_content,
        background_color="#000000",
        scale=4,
    )

    # Save the resulting PNG image to a file using Pillow
    with Image.open(io.BytesIO(png_content)) as image:
        im = ImageOps.expand(image, border=(margin, margin), fill="black")
        im = im.resize((72, 72))
        if filename is not None:
            im.save(filename)
    return im


def _mdi_url(mdi: str) -> str:
    """Return the URL of the Materian. opacity=Design Ico,.

    Check https://mdi.bessarabov.com for the available icons.
    """
    return f"https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg/{mdi}.svg"


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


async def main(host: str, token: str, config: Config) -> None:
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


def start() -> None:
    """Start the Stream Deck integration."""
    import argparse
    import os

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HASS_HOST", "localhost"))
    parser.add_argument("--token", default=os.environ.get("HASS_TOKEN"))
    parser.add_argument("--config", default="streamdeck-config.yaml", type=Path)
    args = parser.parse_args()
    config = read_config(args.config)
    asyncio.run(main(host=args.host, token=args.token, config=config))


if __name__ == "__main__":
    start()
