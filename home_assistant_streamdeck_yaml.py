#!/usr/bin/env python3
"""Home Assistant Stream Deck integration."""
from __future__ import annotations

import asyncio
import colorsys
import functools as ft
import hashlib
import io
import json
import re
import time
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, TypeAlias

import jinja2
import pkg_resources
import requests
import websockets
import yaml
from lxml import etree
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, Field, PrivateAttr, validator
from rich.console import Console
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from StreamDeck.Devices import StreamDeck

__version__ = pkg_resources.get_distribution("home_assistant_streamdeck_yaml").version


SCRIPT_DIR = Path(__file__).parent
ASSETS_PATH = SCRIPT_DIR / "assets"
DEFAULT_CONFIG = SCRIPT_DIR / "configuration.yaml"
DEFAULT_FONT: str = "Roboto-Regular.ttf"
DEFAULT_MDI_ICONS = {"light": "lightbulb", "switch": "power-socket-eu"}
ICON_PIXELS = 72
_ID_COUNTER = 0

console = Console()
StateDict: TypeAlias = dict[str, dict[str, Any]]


class Button(BaseModel, extra="forbid"):  # type: ignore[call-arg]
    """Button configuration."""

    entity_id: str | None = Field(
        default=None,
        allow_template=True,
        description="The `entity_id` that this button controls."
        " This entitity will be passed to the `service` when the button is pressed.",
    )
    service: str | None = Field(
        default=None,
        allow_template=True,
        description="The `service` that will be called when the button is pressed.",
    )
    service_data: dict[str, Any] | None = Field(
        default=None,
        allow_template=True,
        description="The `service_data` that will be passed to the `service` when the button is pressed."
        " If empty, the `entity_id` will be passed.",
    )
    target: dict[str, Any] | None = Field(
        default=None,
        allow_template=True,
        description="The `target` that will be passed to the `service` when the button is pressed.",
    )
    text: str = Field(
        default="",
        allow_template=True,
        description="The text to display on the button."
        " If empty, no text is displayed."
        r" You might want to add `\n` characters to spread the text over several"
        r" lines, or use the `\|` character in YAML to create a multi-line string.",
    )
    text_color: str | None = Field(
        default=None,
        allow_template=True,
        description="Color of the text."
        " If empty, the color is `white`, unless an `entity_id` is specified, in"
        " which case the color is `amber` when the state is `on`, and `white` when it is `off`.",
    )
    text_size: int = Field(
        default=12,
        allow_template=False,
        description="Integer size of the text.",
    )
    icon: str | None = Field(
        default=None,
        allow_template=True,
        description="The icon filename to display on the button."
        " Make the path absolute (e.g., `/config/streamdeck/my_icon.png`) or relative to the"
        " `assets` directory (e.g., `my_icon.png`)."
        " If empty, a icon with `icon_background_color` and `text` is displayed."
        " The icon can be a URL to an image,"
        " like `'url:https://www.nijho.lt/authors/admin/avatar.jpg'`, or a `spotify:`"
        " icon, like `'spotify:album/6gnYcXVaffdG0vwVM34cr8'`."
        " If the icon is a `spotify:` icon, the icon will be downloaded and cached.",
    )
    icon_mdi: str | None = Field(
        default=None,
        allow_template=True,
        description="The Material Design Icon to display on the button."
        " If empty, no icon is displayed."
        " See https://mdi.bessarabov.com/ for a list of icons."
        " The SVG icon will be downloaded and cached.",
    )
    icon_background_color: str = Field(
        default="#000000",
        allow_template=True,
        description="A color (in hex format, e.g., '#FF0000') for the background of the icon (if no `icon` is specified).",
    )
    icon_mdi_color: str | None = Field(
        default=None,
        allow_template=True,
        description="The color of the Material Design Icon (in hex format, e.g., '#FF0000')."
        " If empty, the color is derived from `text_color` but is less saturated (gray is mixed in).",
    )
    icon_gray_when_off: bool = Field(
        default=False,
        allow_template=False,
        description="When specifying `icon` and `entity_id`, if the state is `off`, the icon will be converted to grayscale.",
    )
    delay: float = Field(
        default=0.0,
        allow_template=False,
        description="The delay (in seconds) before the `service` is called."
        " This is useful if you want to wait before calling the `service`."
        " Counts down from the time the button is pressed."
        " If while counting the button is pressed again, the timer is cancelled.",
    )
    special_type: Literal[
        "next-page",
        "previous-page",
        "empty",
        "go-to-page",
        "turn-off",
        "light-control",
    ] | None = Field(
        default=None,
        allow_template=False,
        description="Special type of button."
        " If no specified, the button is a normal button."
        " If `next-page`, the button will go to the next page."
        " If `previous-page`, the button will go to the previous page."
        " If `turn-off`, the button will turn off the SteamDeck until any button is pressed."
        " If `empty`, the button will be empty."
        " If `go-to-page`, the button will go to the page specified by `special_type_data`"
        " (either an `int` or `str` (name of the page))."
        " If `light-control`, the button will control a light, and the `special_type_data`"
        " can be a dictionary, see its description.",
    )
    special_type_data: Any | None = Field(
        default=None,
        allow_template=True,
        description="Data for the special type of button."
        " If `go-to-page`, the data should be an `int` or `str` (name of the page)."
        " If `light-control`, the data should optionally be a dictionary."
        " The dictionary can contain the following keys:"
        " The `colors` key and a value a list of max (`n_keys_on_streamdeck - 5`) hex colors."
        " The `colormap` key and a value a colormap (https://matplotlib.org/stable/tutorials/colors/colormaps.html)"
        " can be used. This requires the `matplotlib` package to be installed. If no"
        " list of `colors` or `colormap` is specified, 10 equally spaced colors are used.",
    )

    _timer: AsyncDelayedCallback | None = PrivateAttr(None)

    @classmethod
    def from_yaml(cls: type[Button], yaml_str: str) -> Button:
        """Set the attributes from a YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(**data[0])

    @classmethod
    def to_markdown_table(cls: type[Button]) -> str:
        """Return a markdown table with the schema."""
        import pandas as pd

        rows = []
        for k, field in cls.__fields__.items():
            info = field.field_info
            if info.description is None:
                continue

            def code(text: str) -> str:
                return f"`{text}`"

            row = {
                "Variable name": code(k),
                "Allow template": "✅" if info.extra["allow_template"] else "❌",
                "Description": info.description,
                "Default": code(info.default) if info.default else "",
                "Type": code(field._type_display()),  # noqa: SLF001
            }
            rows.append(row)
        return pd.DataFrame(rows).to_markdown(index=False)

    @property
    def domain(self) -> str | None:
        """Return the domain of the entity."""
        if self.service is None:
            return None
        return self.service.split(".", 1)[0]

    @classmethod
    def templatable(cls: type[Button]) -> set[str]:
        """Return if an attribute is templatable, which is if the type-annotation is str."""
        schema = cls.schema()
        properties = schema["properties"]
        return {k for k, v in properties.items() if v["allow_template"]}

    def rendered_template_button(
        self,
        complete_state: StateDict,
    ) -> Button:
        """Return a button with the rendered text."""
        dct = self.dict(exclude_unset=True)
        for key in self.templatable():
            if key not in dct:
                continue
            val = dct[key]
            if isinstance(val, dict):  # e.g., service_data, target
                for k, v in val.items():
                    val[k] = _render_jinja(v, complete_state)
            else:
                dct[key] = _render_jinja(val, complete_state)  # type: ignore[assignment]
        return Button(**dct)

    def try_render_icon(
        self,
        complete_state: StateDict,
        *,
        key_pressed: bool = False,
        size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
        icon_mdi_margin: int = 0,
        font_filename: str = DEFAULT_FONT,
    ) -> Image.Image:
        """Try to render the icon."""
        try:
            return self.render_icon(
                complete_state,
                key_pressed=key_pressed,
                size=size,
                icon_mdi_margin=icon_mdi_margin,
                font_filename=font_filename,
            )
        except Exception as exc:  # noqa: BLE001
            console.print_exception()
            warnings.warn(
                f"Failed to render icon for {self}: {exc}",
                IconWarning,
                stacklevel=2,
            )
            return _generate_failed_icon(size)

    def render_icon(  # noqa: PLR0912
        self,
        complete_state: StateDict,
        *,
        key_pressed: bool = False,
        size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
        icon_mdi_margin: int = 0,
        font_filename: str = DEFAULT_FONT,
    ) -> Image.Image:
        """Render the icon."""
        if self.is_sleeping():
            button, image = self.sleep_button_and_image(size)
        else:
            button = self.rendered_template_button(complete_state)
            image = None

        if isinstance(button.icon, str) and ":" in button.icon:
            which, id_ = button.icon.split(":", 1)
            if which == "spotify":
                filename = _to_filename(button.icon, ".jpeg")
                # copy to avoid modifying the cached image
                image = _download_spotify_image(id_, filename).copy()
            if which == "url":
                filename = _url_to_filename(id_)
                # copy to avoid modifying the cached image
                image = _download_image(id_, filename, size).copy()

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
        elif button.special_type == "turn-off":
            text = button.text or "Turn off"
            icon_mdi = button.icon_mdi or "power"
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

        if image is None:
            image = _init_icon(
                icon_background_color=button.icon_background_color,
                icon_filename=button.icon,
                icon_mdi=icon_mdi,
                icon_mdi_margin=icon_mdi_margin,
                icon_mdi_color=_named_to_hex(button.icon_mdi_color or text_color),
                size=size,
            ).copy()  # copy to avoid modifying the cached image

        if icon_convert_to_grayscale:
            image = _convert_to_grayscale(image)

        _add_text(
            image,
            font_filename,
            self.text_size,
            text,
            text_color=text_color if not key_pressed else "green",
        )
        return image

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
        if (
            special_type in {"next-page", "previous-page", "empty", "turn-off"}
            and v is not None
        ):
            msg = f"special_type_data needs to be empty with {special_type=}"
            raise AssertionError(msg)
        if special_type == "light-control":
            if v is None:
                v = {}
            if not isinstance(v, dict):
                msg = (
                    "With 'light-control', 'special_type_data' must"
                    f" be a dict, not '{v}'"
                )
                raise AssertionError(msg)
            # Can only have the following keys: colors and colormap
            allowed_keys = {"colors", "colormap"}
            invalid_keys = v.keys() - allowed_keys
            if invalid_keys:
                msg = (
                    f"Invalid keys in 'special_type_data', only {allowed_keys} allowed"
                )
                raise AssertionError(msg)
            # If colors is present, it must be a list of strings
            if "colors" in v:
                if not isinstance(v["colors"], (tuple, list)):
                    msg = "If 'colors' is present, it must be a list"
                    raise AssertionError(msg)
                for color in v["colors"]:
                    if not isinstance(color, str):
                        msg = "All colors must be strings"
                        raise AssertionError(msg)  # noqa: TRY004
                # Cast colors to tuple (to make it hashable)
                v["colors"] = tuple(v["colors"])
        return v

    def maybe_start_or_cancel_timer(
        self,
        callback: Callable[[], None | Coroutine] | None = None,
    ) -> bool:
        """Start or cancel the timer."""
        if self.delay:
            if self._timer is None:
                self._timer = AsyncDelayedCallback(delay=self.delay, callback=callback)
            if self._timer.is_running():
                self._timer.cancel()
            else:
                self._timer.start()
            return True
        return False

    def is_sleeping(self) -> bool:
        """Return True if the timer is sleeping."""
        return self._timer is not None and self._timer.is_sleeping

    def sleep_button_and_image(
        self,
        size: tuple[int, int],
    ) -> tuple[Button, Image.Image]:
        """Return the button and image for the sleep button."""
        assert self._timer is not None
        remaining = self._timer.remaining_time()
        pct = round(remaining / self.delay * 100)
        image = _draw_percentage_ring(pct, size)
        button = Button(
            text=f"{remaining:.0f}s\n{pct}%",
            text_color="white",
        )
        return button, image


def _to_filename(id_: str, suffix: str = "") -> Path:
    """Converts an id with ":" and "_" to a filename with optional suffix."""
    filename = ASSETS_PATH / id_.replace("/", "_").replace(":", "_")
    return filename.with_suffix(suffix)


class Page(BaseModel):
    """A page of buttons."""

    name: str
    buttons: list[Button] = Field(default_factory=list)
    single_click: bool = False


class Config(BaseModel):
    """Configuration file."""

    pages: list[Page] = Field(default_factory=list)
    anonymous_pages: list[Page] = Field(default_factory=list)
    current_page_index: int = 0
    state_entity_id: str | None = None
    is_on: bool = True
    brightness: int = 100
    _special_page: Page | None = PrivateAttr(default=None)
    _last_page: int | None = PrivateAttr(default=None)

    def update_timers(
        self,
        deck: StreamDeck,
        complete_state: dict[str, dict[str, Any]],
    ) -> None:
        """Update all timers."""
        for key in range(deck.key_count()):
            button = self.button(key)
            if button is not None and button.is_sleeping():
                console.log(f"Updating timer for key {key}")
                update_key_image(
                    deck,
                    key=key,
                    config=self,
                    complete_state=complete_state,
                    key_pressed=False,
                )

    def next_page(self) -> Page:
        """Go to the next page."""
        self._last_page = self.current_page_index
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
        self._last_page = self.current_page_index
        self.current_page_index = self.previous_page_index
        return self.pages[self.current_page_index]

    def current_page(self) -> Page:
        """Return the current page."""
        if self._special_page is not None:
            return self._special_page
        return self.pages[self.current_page_index]

    def button(self, key: int) -> Button | None:
        """Return the button for a key."""
        buttons = self.current_page().buttons
        if key < len(buttons):
            return buttons[key]
        return None

    def to_page(self, page: int | str) -> Page:
        """Go to a page based on the page name or index."""
        self._last_page = self.current_page_index
        if isinstance(page, int):
            self.current_page_index = page
            return self.current_page()

        for i, p in enumerate(self.pages):
            if p.name == page:
                self.current_page_index = i
                return self.current_page()

        for p in self.anonymous_pages:
            if p.name == page:
                self._special_page = p
                return p

        return self.current_page()

    def to_last_page(self) -> Page:
        """Go to the last page that was visited."""
        if self._last_page is not None:
            self.current_page_index = self._last_page
        return self.current_page()


def _next_id() -> int:
    global _ID_COUNTER
    _ID_COUNTER += 1
    return _ID_COUNTER


class AsyncDelayedCallback:
    """A callback that is called after a delay.

    Parameters
    ----------
    delay
        The delay in seconds after which the callback will be called.
    callback
        The function or coroutine to be called after the delay.
    """

    def __init__(
        self,
        delay: float,
        callback: Callable[[], None | Coroutine] | None = None,
    ) -> None:
        """Initialize."""
        self.delay = delay
        self.callback = callback
        self.task: asyncio.Task | None = None
        self.start_time: float | None = None
        self.is_sleeping: bool = False

    async def _run(self) -> None:
        """Run the timer. Don't call this directly, use start() instead."""
        self.is_sleeping = True
        self.start_time = time.time()
        await asyncio.sleep(self.delay)
        self.is_sleeping = False
        if self.callback is not None:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback()
            else:
                self.callback()

    def is_running(self) -> bool:
        """Return whether the timer is running."""
        return self.task is not None and not self.task.done()

    def start(self) -> None:
        """Start the timer."""
        if self.task is not None and not self.task.done():
            self.cancel()
        self.task = asyncio.ensure_future(self._run())

    def cancel(self) -> None:
        """Cancel the timer."""
        console.log("Cancel timer")
        if self.task:
            self.task.cancel()
            self.is_sleeping = False
            self.task = None

    def remaining_time(self) -> float:
        """Return the remaining time before the timer expires."""
        if self.task is None:
            return 0
        if self.start_time is not None:
            elapsed_time = time.time() - self.start_time
            return max(0, self.delay - elapsed_time)
        return 0


def _draw_percentage_ring(
    percentage: int,
    size: tuple[int, int],
    *,
    radius: int | None = None,
    thickness: int = 4,
    ring_color: tuple[int, int, int] = (255, 0, 0),
    full_ring_backgroud_color: tuple[int, int, int] = (100, 100, 100),
) -> Image.Image:
    """Draw a ring with a percentage."""
    img = Image.new("RGB", size, (0, 0, 0))

    if radius is None:
        radius = size[0] // 2 - thickness // 2

    # Draw the full ring for the background
    draw = ImageDraw.Draw(img)
    draw.ellipse(
        [
            (size[0] // 2 - radius, size[1] // 2 - radius),
            (size[0] // 2 + radius, size[1] // 2 + radius),
        ],
        outline=full_ring_backgroud_color,
        width=thickness,
    )

    # Draw the percentage of the ring with a bright color
    start_angle = -90
    end_angle = start_angle + (360 * percentage / 100)
    draw.arc(
        [
            (size[0] // 2 - radius, size[1] // 2 - radius),
            (size[0] // 2 + radius, size[1] // 2 + radius),
        ],
        start_angle,
        end_angle,
        fill=ring_color,
        width=thickness,
    )
    return img


def _linspace(start: float, stop: float, num: int) -> list[float]:
    """Return evenly spaced numbers over a specified interval."""
    if num == 1:
        return [start]
    step = (stop - start) / (num - 1)
    return [start + i * step for i in range(num)]


def _generate_colors_from_colormap(num_colors: int, colormap: str) -> tuple[str, ...]:
    """Returns `num_colors` number of colors in hexadecimal format, sampled from colormaps."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ModuleNotFoundError:
        msg = "You need to install matplotlib to use the colormap feature."
        raise ModuleNotFoundError(msg) from None

    cmap = plt.get_cmap(colormap)
    colors = cmap(np.linspace(0, 1, num_colors))
    return tuple(plt.matplotlib.colors.to_hex(color) for color in colors)


def _generate_uniform_hex_colors(n_colors: int) -> tuple[str, ...]:
    """Generate a list of `n_colors` hex colors that are uniformly perceptually spaced.

    Parameters
    ----------
    n_colors
        The number of colors to generate.

    Returns
    -------
    list[str]
        A list of `n_colors` hex colors, represented as strings.

    Examples
    --------
    >>> _generate_uniform_hex_colors(3)
    ['#0000ff', '#00ff00', '#ff0000']
    """

    def generate_hues(n_hues: int) -> list[float]:
        """Generate `n_hues` hues that are uniformly spaced around the color wheel."""
        return _linspace(0, 1, n_hues)

    def generate_saturations(n_saturations: int) -> list[float]:
        """Generate `n_saturations` saturations that increase linearly from 0 to 1."""
        return _linspace(0, 1, n_saturations)

    def generate_values(n_values: int) -> list[float]:
        """Generate `n_values` values that increase linearly from 1 to 0.5 and then decrease to 0."""
        values = _linspace(1, 0.5, n_values // 2)
        if n_values % 2 == 1:
            values.append(0.0)
        values += _linspace(0.5, 0, n_values // 2)
        return values

    def hsv_to_hex(hsv: tuple[float, float, float]) -> str:
        """Convert an HSV color tuple to a hex color string."""
        rgb = tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(*hsv))
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    hues = generate_hues(n_colors)
    saturations = generate_saturations(n_colors)
    values = generate_values(n_colors)
    hsv_colors = [(h, s, v) for h in hues for s in saturations for v in values]
    hex_colors = [hsv_to_hex(hsv) for hsv in hsv_colors]
    return tuple(hex_colors[:n_colors])


def _max_contrast_color(hex_color: str) -> str:
    """Given hex color return a color with maximal contrast."""
    # Convert hex color to RGB format
    r, g, b = _hex_to_rgb(hex_color)
    # Convert RGB color to grayscale
    gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    # Determine whether white or black will have higher contrast
    middle_range = 128
    return "#FFFFFF" if gray < middle_range else "#000000"


@ft.lru_cache(maxsize=16)
def _light_page(
    entity_id: str,
    n_colors: int,
    colors: tuple[str, ...] | None,
    colormap: str | None,
) -> Page:
    """Return a page of buttons for controlling lights."""
    if colormap is None and colors is None:
        colors = _generate_uniform_hex_colors(n_colors)
    elif colormap is not None:
        colors = _generate_colors_from_colormap(n_colors, colormap)
    assert colors is not None
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
    buttons_brightness = []
    for brightness in [0, 10, 30, 60, 100]:
        background_color = _scale_hex_color("#FFFFFF", brightness / 100)
        button = Button(
            icon_background_color=background_color,
            service="light.turn_on",
            text_color=_max_contrast_color(background_color),
            text=f"{brightness}%",
            service_data={
                "entity_id": entity_id,
                "brightness_pct": brightness,
            },
        )
        buttons_brightness.append(button)
    return Page(
        name="Lights",
        buttons=buttons_colors + buttons_brightness,
    )


@asynccontextmanager
async def setup_ws(
    host: str,
    token: str,
    protocol: Literal["wss", "ws"],
) -> websockets.WebSocketClientProtocol:
    """Set up the connection to Home Assistant."""
    uri = f"{protocol}://{host}/api/websocket"
    while True:
        try:
            # limit size to 10 MiB
            async with websockets.connect(uri, max_size=10485760) as websocket:
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


async def handle_changes(
    websocket: websockets.WebSocketClientProtocol,
    complete_state: StateDict,
    deck: StreamDeck,
    config: Config,
) -> None:
    """Handle state changes."""

    async def process_websocket_messages() -> None:
        """Process websocket messages."""
        while True:
            data = json.loads(await websocket.recv())
            _update_state(complete_state, data, config, deck)

    async def call_update_timers() -> None:
        """Call config.update_timers every second."""
        while True:
            await asyncio.sleep(1)
            config.update_timers(deck, complete_state)

    # Run the websocket message processing and timer update tasks concurrently
    await asyncio.gather(process_websocket_messages(), call_update_timers())


def _keys(entity_id: str, buttons: list[Button]) -> list[int]:
    """Get the key indices for an entity_id."""
    return [i for i, button in enumerate(buttons) if button.entity_id == entity_id]


def _update_state(
    complete_state: StateDict,
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

            # Handle the state entity (turning on/off display)
            if eid == config.state_entity_id:
                is_on = complete_state[config.state_entity_id]["state"] == "on"
                if is_on:
                    turn_on(config, deck, complete_state)
                else:
                    turn_off(config, deck)
                return

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
    complete_state: StateDict,
) -> Any:
    """Get the state attribute for an entity."""
    return complete_state.get(entity_id, {}).get("attributes", {}).get(attr)


def _is_state_attr(
    entity_id: str,
    attr: str,
    value: Any,
    complete_state: StateDict,
) -> bool:
    """Check if the state attribute for an entity is a value."""
    return _state_attr(entity_id, attr, complete_state) == value


def _states(
    entity_id: str,
    *,
    with_unit: bool = False,
    rounded: bool = False,
    complete_state: StateDict | None = None,
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
    return state


def _is_state(
    entity_id: str,
    state: str,
    complete_state: StateDict,
) -> bool:
    """Check if the state for an entity is a value."""
    return _states(entity_id, complete_state=complete_state) == state


def _min_filter(value: float, other_value: float) -> float:
    """Return the minimum of two values.

    Can be used in Jinja templates like
    >>> {{ 1 | min(2) }}
    1
    """
    return min(value, other_value)


def _max_filter(value: float, other_value: float) -> float:
    """Return the maximum of two values.

    Can be used in Jinja templates like
    >>> {{ 1 | max(2) }}
    2
    """
    return max(value, other_value)


def _render_jinja(text: str, complete_state: StateDict) -> str:
    """Render a Jinja template."""
    if not isinstance(text, str):
        return text
    if "{" not in text:
        return text
    try:
        env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=False,  # noqa: S701
        )
        env.filters["min"] = _min_filter
        env.filters["max"] = _max_filter
        template = env.from_string(text)
        return template.render(  # noqa: TRY300
            min=min,
            max=max,
            is_state_attr=ft.partial(_is_state_attr, complete_state=complete_state),
            state_attr=ft.partial(_state_attr, complete_state=complete_state),
            states=ft.partial(_states, complete_state=complete_state),
            is_state=ft.partial(_is_state, complete_state=complete_state),
        ).strip()
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
    target: dict[str, Any] | None = None,
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
    if target is not None:
        subscribe_payload["target"] = target
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
    try:
        etree.fromstring(svg_content)  # noqa: S320
    except etree.XMLSyntaxError:
        msg = (f"Invalid SVG: {url}, `svg_content` starts with: {svg_content[:100]!r}",)
        console.log(f"[b red]{msg}[/]")
        raise ValueError(msg) from None

    with filename_svg.open("wb") as f:
        f.write(svg_content)
    return filename_svg


@ft.lru_cache(maxsize=128)  # storing 128 72x72 icons in memory takes ≈2MB
def _init_icon(
    *,
    icon_filename: str | None = None,
    icon_mdi: str | None = None,
    icon_mdi_margin: int | None = None,
    icon_mdi_color: str | None = None,  # hex color
    icon_background_color: str | None = None,  # hex color
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
    """Initialize the icon."""
    if icon_filename is not None:
        icon_path = Path(icon_filename)
        path = icon_path if icon_path.is_absolute() else ASSETS_PATH / icon_path
        icon = Image.open(path)
        # Convert to RGB if needed
        if icon.mode != "RGB":
            icon = icon.convert("RGB")
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
        ).copy()  # copy to avoid modifying the cached image
    if icon_background_color is None:
        icon_background_color = "white"
    color = _named_to_hex(icon_background_color)
    rgb_color = _hex_to_rgb(color)
    return Image.new("RGB", size, rgb_color)


def _add_text(
    image: Image.Image,
    font_filename: str,
    text_size: int,
    text: str,
    text_color: str,
) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ASSETS_PATH / font_filename), text_size)
    draw.text(
        (image.width / 2, image.height / 2),
        text=text,
        font=font,
        anchor="ms",
        fill=text_color,
        align="center",
    )


def _generate_failed_icon(
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
    """Generate a red icon with 'rendering failed' text."""
    background_color = "red"
    text_color = "white"
    font_filename = DEFAULT_FONT
    text_size = int(min(size) * 0.15)  # Adjust font size based on the icon size
    icon = Image.new("RGB", size, background_color)
    _add_text(
        image=icon,
        font_filename=font_filename,
        text_size=text_size,
        text="Rendering\nfailed",
        text_color=text_color,
    )
    return icon


def update_key_image(
    deck: StreamDeck,
    *,
    key: int,
    config: Config,
    complete_state: StateDict,
    key_pressed: bool = False,
) -> None:
    """Update the image for a key."""
    button = config.button(key)
    if button is None:
        return
    if button.special_type == "empty":
        return
    size = deck.key_image_format()["size"]
    image = button.try_render_icon(
        complete_state=complete_state,
        key_pressed=key_pressed,
        size=size,
    )
    assert image is not None
    image = PILHelper.to_native_format(deck, image)
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
        return Config(
            pages=data["pages"],
            state_entity_id=data.get("state_entity_id"),
            brightness=data.get("brightness", 100),
        )


def turn_on(config: Config, deck: StreamDeck, complete_state: StateDict) -> None:
    """Turn on the Stream Deck and update all key images."""
    console.log(f"Calling turn_on, with {config.is_on=}")
    if config.is_on:
        return
    config.is_on = True
    update_all_key_images(deck, config, complete_state)
    deck.set_brightness(config.brightness)


def turn_off(config: Config, deck: StreamDeck) -> None:
    """Turn off the Stream Deck."""
    console.log(f"Calling turn_off, with {config.is_on=}")
    if not config.is_on:
        return
    config.is_on = False
    # This resets all buttons except the turn-off button that
    # was just pressed, however, this doesn't matter with the
    # 0 brightness. Unless no button was pressed.
    deck.reset()
    deck.set_brightness(0)


async def _handle_key_press(
    websocket: websockets.WebSocketClientProtocol,
    complete_state: StateDict,
    config: Config,
    button: Button,
    deck: StreamDeck,
) -> None:
    if not config.is_on:
        turn_on(config, deck, complete_state)
        return

    def update_all() -> None:
        deck.reset()
        update_all_key_images(deck, config, complete_state)

    if button.special_type == "next-page":
        config.next_page()
        update_all()
    elif button.special_type == "previous-page":
        config.previous_page()
        update_all()
    elif button.special_type == "go-to-page":
        assert isinstance(button.special_type_data, (str, int))
        config.to_page(button.special_type_data)  # type: ignore[arg-type]
        update_all()
    elif button.special_type == "turn-off":
        turn_off(config, deck)
    elif button.special_type == "light-control":
        assert isinstance(button.special_type_data, dict)
        page = _light_page(
            entity_id=button.entity_id,
            n_colors=10,
            colormap=button.special_type_data.get("colormap", None),
            colors=button.special_type_data.get("colors", None),
        )
        assert config._special_page is None  # noqa: SLF001
        config._special_page = page  # noqa: SLF001
        update_all()
    elif button.service is not None:
        button = button.rendered_template_button(complete_state)
        if button.service_data is None:
            service_data = {}
            if button.entity_id is not None:
                service_data["entity_id"] = button.entity_id
        else:
            service_data = button.service_data
        console.log(f"Calling service {button.service} with data {service_data}")
        assert button.service is not None  # for mypy
        await call_service(websocket, button.service, service_data, button.target)


def _on_press_callback(
    websocket: websockets.WebSocketClientProtocol,
    complete_state: StateDict,
    config: Config,
) -> Callable[[StreamDeck, int, bool], Coroutine[StreamDeck, int, None]]:
    async def key_change_callback(
        deck: StreamDeck,
        key: int,
        key_pressed: bool,  # noqa: FBT001
    ) -> None:
        console.log(f"Key {key} {'pressed' if key_pressed else 'released'}")

        button = config.button(key)
        assert button is not None
        if button is not None and key_pressed:

            async def cb() -> None:
                """Update the deck once more after the timer is over."""
                assert button is not None  # for mypy
                await _handle_key_press(websocket, complete_state, config, button, deck)

            if button.maybe_start_or_cancel_timer(cb):
                key_pressed = False  # do not click now

        try:
            update_key_image(
                deck,
                key=key,
                config=config,
                complete_state=complete_state,
                key_pressed=key_pressed,
            )
            if key_pressed:
                has_special_page = config._special_page is not None  # noqa: SLF001
                await _handle_key_press(websocket, complete_state, config, button, deck)
                if has_special_page:
                    # Reset after a keypress
                    config._special_page = None  # noqa: SLF001
                    deck.reset()
                    update_all_key_images(deck, config, complete_state)
        except Exception as e:  # noqa: BLE001
            console.print_exception(show_locals=True)
            console.log(f"key_change_callback failed with a {type(e)}: {e}")

    return key_change_callback


@ft.lru_cache(maxsize=128)
def _download(url: str) -> bytes:
    """Download the content from the URL."""
    console.log(f"Downloading {url}")
    response = requests.get(url, timeout=5)
    console.log(f"Downloaded {len(response.content)} bytes")
    return response.content


def _url_to_filename(url: str, hash_len: int = 8) -> Path:
    """Converts a URL to a Path on disk with an optional hash.

    Parameters
    ----------
    url
        The URL to convert to a filename.
    hash_len
        The length of the hash to include in the filename, by default 8.

    Returns
    -------
    Path
        The filename with the hash included, if specified.
    """
    domain, path = re.findall(r"(?<=://)([a-zA-Z\.]+).*?(/.*)", url)[0]
    h = hashlib.sha256(f"{domain}{path}".encode()).hexdigest()[:hash_len]
    extension = Path(path).suffix
    filename = f"{domain.replace('.', '_')}-{h}{extension}"
    return ASSETS_PATH / Path(filename)


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


class IconWarning(UserWarning):
    """Warning for when an icon is not found."""


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
    import cairosvg  # importing here because it requires a non Python dep

    with filename_svg.open() as f:
        svg_content = f.read()

    fill_color = _scale_hex_color(color, opacity)

    try:
        svg_tree = etree.fromstring(svg_content)  # noqa: S320
        svg_tree.attrib["fill"] = fill_color
        svg_tree.attrib["style"] = f"background-color: {background_color}"
        modified_svg_content = etree.tostring(svg_tree)
    except etree.XMLSyntaxError:
        msg = (
            f"XML parsing failed for {filename_svg}. Creating an image with solid"
            f" fill color. Received `svg_content` starts with {svg_content[:100]}."
        )
        warnings.warn(msg, IconWarning, stacklevel=2)
        console.log(f"[b red]{msg}[/]")
        modified_svg_content = None

    png_content = (
        cairosvg.svg2png(
            bytestring=modified_svg_content,
            background_color=background_color,
            scale=4,
        )
        if modified_svg_content
        else None
    )

    image = (
        Image.open(io.BytesIO(png_content))
        if png_content
        else Image.new("RGBA", size, fill_color)
    )

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
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
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
    return _download_image(image_url, filename, size)


@ft.lru_cache(maxsize=32)  # Change only a few images, because they might be large
def _download_image(
    url: str,
    filename: Path | None = None,
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
    """Download an image for a given url."""
    if filename is not None and filename.exists():
        return Image.open(filename)
    image_content = _download(url)
    image = Image.open(io.BytesIO(image_content))
    if image.mode != "RGB":
        image = image.convert("RGB")
    if filename is not None:
        image.save(filename)
    image = image.resize(size)
    return image


def update_all_key_images(
    deck: StreamDeck,
    config: Config,
    complete_state: StateDict,
) -> None:
    """Update all key images."""
    console.log("Called update_all_key_images")
    for key in range(deck.key_count()):
        update_key_image(
            deck,
            key=key,
            config=config,
            complete_state=complete_state,
            key_pressed=False,
        )


async def run(
    host: str,
    token: str,
    protocol: Literal["wss", "ws"],
    config: Config,
) -> None:
    """Main entry point for the Stream Deck integration."""
    deck = get_deck()
    async with setup_ws(host, token, protocol) as websocket:
        complete_state = await get_states(websocket)
        update_all_key_images(deck, config, complete_state)
        deck.set_key_callback_async(
            _on_press_callback(websocket, complete_state, config),
        )
        deck.set_brightness(config.brightness)
        await subscribe_state_changes(websocket)
        await handle_changes(websocket, complete_state, deck, config)


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
    parser.add_argument(
        "--protocol",
        default=os.environ.get("WEBSOCKET_PROTOCOL", "wss"),
        choices=["wss", "ws"],
    )
    args = parser.parse_args()
    console.log(f"Using version {__version__} of the Home Assistant Stream Deck.")
    console.log(
        f"Starting Stream Deck integration with {args.host=}, {args.config=}, {args.protocol=}",
    )
    config = read_config(args.config)
    asyncio.run(
        run(
            host=args.host,
            token=args.token,
            protocol=args.protocol,
            config=config,
        ),
    )


if __name__ == "__main__":
    main()
