#!/usr/bin/env python3
"""Home Assistant Stream Deck integration."""

from __future__ import annotations

import asyncio
import colorsys
import functools as ft
import hashlib
import io
import json
import locale
import math
import re
import signal
import ssl
import sys
import time
import warnings
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    TextIO,
    TypeAlias,
    get_args,
)

import jinja2
import requests
import websockets
import yaml
from lxml import etree
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, Field, PrivateAttr, validator
from pydantic.fields import Undefined
from rich.console import Console
from rich.table import Table
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Devices.StreamDeck import DialEventType, TouchscreenEventType
from StreamDeck.ImageHelpers import PILHelper

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from types import FrameType

    import pandas as pd
    from StreamDeck.Devices import StreamDeck


try:
    __version__ = version("home_assistant_streamdeck_yaml")
except PackageNotFoundError:
    __version__ = "unknown"


SCRIPT_DIR = Path(__file__).parent
ASSETS_PATH = SCRIPT_DIR / "assets"
DEFAULT_CONFIG = SCRIPT_DIR / "configuration.yaml"
DEFAULT_FONT: str = "Roboto-Regular.ttf"
DEFAULT_MDI_ICONS = {
    "light": "lightbulb",
    "switch": "power-socket-eu",
    "script": "script",
}
ICON_PIXELS = 72
_ID_COUNTER = 0

# Resolution for Stream deck plus
LCD_PIXELS_X = 800
LCD_PIXELS_Y = 100

# Default resolution for each icon on Stream deck plus
LCD_ICON_SIZE_X = 200
LCD_ICON_SIZE_Y = 100

press_start_times: dict[int, float] = {}  # Dictionary to store press start times per key.

console = Console()
StateDict: TypeAlias = dict[str, dict[str, Any]]


class _ButtonDialBase(BaseModel, extra="forbid"):  # type: ignore[call-arg]
    """Parent of Button and Dial."""

    entity_id: str | None = Field(
        default=None,
        allow_template=True,
        description="The `entity_id` that this button controls."
        " This entity will be passed to the `service` when the button is pressed."
        " The button is re-rendered whenever the state of this entity changes.",
    )
    linked_entity: str | None = Field(
        default=None,
        allow_template=True,
        description="A secondary entity_id that is used for updating images and states",
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
    text: str | None = Field(
        default=None,
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
    text_offset: int = Field(
        default=0,
        allow_template=False,
        description="The text's position can be moved up or down from the center of"
        " the button, and this movement is measured in pixels. The value can be"
        " positive (for upward movement) or negative (for downward movement).",
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
        " If the icon is a `spotify:` icon, the icon will be downloaded and cached."
        " The icon can also display a partially complete ring, like a progress bar,"
        " or sensor value, like `ring:25` for a 25% complete ring.",
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
    delay: float | str = Field(
        default=0.0,
        allow_template=True,
        description="The delay (in seconds) before the `service` is called."
        " This is useful if you want to wait before calling the `service`."
        " Counts down from the time the button is pressed."
        " If while counting the button is pressed again, the timer is cancelled."
        " Should be a float or template string that evaluates to a float.",
    )

    _timer: AsyncDelayedCallback | None = PrivateAttr(None)

    @classmethod
    def templatable(cls: type[Button]) -> set[str]:
        """Return if an attribute is templatable, which is if the type-annotation is str."""
        schema = cls.schema()
        properties = schema["properties"]
        return {k for k, v in properties.items() if v["allow_template"]}

    @classmethod
    def to_pandas_table(cls: type[Button]) -> pd.DataFrame:
        """Return a pandas table with the schema."""
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
                "Type": code(field._type_display()),
            }
            rows.append(row)
        return pd.DataFrame(rows)

    @classmethod
    def to_markdown_table(cls: type[Button]) -> str:
        """Return a markdown table with the schema."""
        return cls.to_pandas_table().to_markdown(index=False)


SpecialType: TypeAlias = Literal[
    "next-page",
    "previous-page",
    "empty",
    "go-to-page",
    "close-page",
    "turn-off",
    "light-control",
    "reload",
]


class Button(_ButtonDialBase, extra="forbid"):  # type: ignore[call-arg]
    """Button configuration."""

    special_type: SpecialType | None = Field(
        default=None,
        allow_template=False,
        description="Special type of button."
        " If no specified, the button is a normal button."
        " If `next-page`, the button will go to the next page."
        " If `previous-page`, the button will go to the previous page."
        " If `turn-off`, the button will turn off the SteamDeck until any button is pressed."
        " If `empty`, the button will be empty."
        " If `close-page`, the button will close the current page and return to the previous one."
        " If `go-to-page`, the button will go to the page specified by `special_type_data`"
        " (either an `int` or `str` (name of the page))."
        " If `light-control`, the button will control a light, and the `special_type_data`"
        " can be a dictionary, see its description."
        " If `reload`, the button will reload the configuration file when pressed.",
    )
    special_type_data: Any | None = Field(
        default=None,
        allow_template=True,
        description="Data for the special type of button."
        " If `go-to-page`, the data should be an `int` or `str` (name of the page)."
        " If `light-control`, the data should optionally be a dictionary."
        " The dictionary can contain the following keys:"
        " The `colors` key and a value a list of max (`n_keys_on_streamdeck - 6`) hex colors."
        " The `color_temp_kelvin` key and a value a list of max (`n_keys_on_streamdeck - 6`) color temperatures in Kelvin."
        " The `colormap` key and a value a colormap (https://matplotlib.org/stable/tutorials/colors/colormaps.html)"
        " can be used. This requires the `matplotlib` package to be installed. If no"
        " list of `colors` or `colormap` is specified, 10 equally spaced colors are used."
        " The `brightnesses` key and a value of brightness level (0-100).",
    )
    long_press: dict[str, Any] | None = Field(
        default=None,
        allow_template=True,
        description="Configuration for long press actions. Can include:"
        " `service`: The service to call on long press (e.g., 'light.turn_off')."
        " `service_data`: Data to pass to the service (e.g., {'brightness_pct': 10})."
        " `entity_id`: The entity ID to target (e.g., 'light.living_room'), overriding the button's entity_id if specified."
        " `target`: Target specification for the service call (e.g., {'entity_id': 'light.living_room'})."
        " `special_type`: Special action for long press (e.g., 'next-page', 'light-control')."
        " `special_type_data`: Data for the special type action (e.g., {'colors': ['#FF0000']})."
        " If not specified, the default service or special_type action is used for both short and long presses.",
    )

    @classmethod
    def from_yaml(
        cls: type[Button],
        yaml_str: str,
        encoding: str | None = None,
    ) -> Button:
        """Set the attributes from a YAML string."""
        data = safe_load_yaml(yaml_str, encoding=encoding)
        return cls(**data[0])

    @property
    def domain(self) -> str | None:
        """Return the domain of the entity."""
        if self.service is None:
            return None
        return self.service.split(".", 1)[0]

    def rendered_template_button(
        self,
        complete_state: StateDict,
    ) -> Button:
        """Return a button with the rendered text."""

        def render_value(val: Any) -> Any:
            """Recursively render templates in values."""
            if isinstance(val, dict):
                return {k: render_value(v) for k, v in val.items()}
            return _render_jinja(val, complete_state)

        dct = self.dict(exclude_unset=True)
        for key in self.templatable():
            if key not in dct:
                continue
            dct[key] = render_value(dct[key])
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

    def render_icon(  # noqa: PLR0912 PLR0915 C901
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
            if which == "ring":
                pct = _maybe_number(id_)
                assert isinstance(pct, (int, float)), f"Invalid ring percentage: {id_}"
                image = _draw_percentage_ring(pct, size)

        icon_convert_to_grayscale = False
        text = button.text
        text_color = button.text_color or "white"
        icon_mdi = button.icon_mdi

        if button.special_type == "next-page":
            if text is None:
                text = "Next\nPage"
            icon_mdi = button.icon_mdi or "chevron-right"
        elif button.special_type == "previous-page":
            if text is None:
                text = "Previous\nPage"
            icon_mdi = button.icon_mdi or "chevron-left"
        elif button.special_type == "go-to-page":
            page = button.special_type_data
            if text is None:
                text = f"Go to\nPage\n{page}"
            icon_mdi = button.icon_mdi or "book-open-page-variant"
        elif button.special_type == "close-page":
            if text is None:
                text = "Close\nPage"
            icon_mdi = button.icon_mdi or "arrow-u-left-bottom-bold"
        elif button.special_type == "turn-off":
            if text is None:
                text = "Turn off"
            icon_mdi = button.icon_mdi or "power"
        elif button.special_type == "reload":
            if text is None:
                text = "Reload\nconfig"
            icon_mdi = button.icon_mdi or "reload"
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

        if text is None:
            return image
        return _add_text_to_image(
            image=image,
            font_filename=font_filename,
            text_size=self.text_size,
            text=text,
            text_color=text_color if not key_pressed else "green",
            text_offset=self.text_offset,
        )

    @staticmethod
    def _validate_special_type_data(special_type: str, v: Any) -> Any:  # noqa: PLR0912
        if special_type == "go-to-page" and not isinstance(v, (int, str)):
            msg = "If special_type is go-to-page, special_type_data must be an int or str"
            raise AssertionError(msg)
        if special_type in {"next-page", "previous-page", "empty", "turn-off"} and v is not None:
            msg = f"special_type_data needs to be empty with {special_type=}"
            raise AssertionError(msg)

        if special_type == "light-control":
            if v is None:
                v = {}
            if not isinstance(v, dict):
                msg = f"With 'light-control', 'special_type_data' must be a dict, not '{v}'"
                raise AssertionError(msg)

            allowed_keys = {"colors", "colormap", "color_temp_kelvin", "brightnesses"}
            invalid_keys = v.keys() - allowed_keys
            if invalid_keys:
                msg = f"Invalid keys in 'special_type_data', only {allowed_keys} allowed"
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

            if "color_temp_kelvin" in v:
                for kelvin in v["color_temp_kelvin"]:
                    if not isinstance(kelvin, int):
                        msg = "All color_temp_kelvin must be integers"
                        raise AssertionError(msg)  # noqa: TRY004
                # Cast color_temp_kelvin to tuple (to make it hashable)
                v["color_temp_kelvin"] = tuple(v["color_temp_kelvin"])
            if "brightnesses" in v:
                for brightness in v["brightnesses"]:
                    if not isinstance(brightness, int):
                        msg = "All brightnesses must be integers"
                        raise AssertionError(msg)  # noqa: TRY004
                # Cast brightnesses to tuple (to make it hashable)
                v["brightnesses"] = tuple(v["brightnesses"])

        return v

    @validator("special_type_data")
    def _validate_special_type(
        cls: type[Button],
        v: Any,
        values: dict[str, Any],
    ) -> Any:
        """Validate the special_type_data."""
        special_type = values["special_type"]
        return cls._validate_special_type_data(special_type, v)

    @validator("long_press", pre=True)
    def _validate_long_press(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, dict):
            msg = "long_press must be a dictionary"
            raise TypeError(msg)
        allowed_keys = {
            "service",
            "service_data",
            "entity_id",
            "target",
            "special_type",
            "special_type_data",
        }
        invalid_keys = v.keys() - allowed_keys
        if invalid_keys:
            msg = f"Invalid keys in long_press: {invalid_keys}. Allowed: {allowed_keys}"
            raise AssertionError(msg)
        if "service" in v and not isinstance(v["service"], str):
            msg = "long_press.service must be a string"
            raise AssertionError(msg)
        if "service_data" in v and not isinstance(v["service_data"], dict):
            msg = "long_press.service_data must be a dictionary"
            raise AssertionError(msg)
        if "entity_id" in v and not isinstance(v["entity_id"], str):
            msg = "long_press.entity_id must be a string"
            raise AssertionError(msg)
        if "target" in v and not isinstance(v["target"], dict):
            msg = "long_press.target must be a dictionary"
            raise AssertionError(msg)
        if "special_type" in v:
            allowed_special_types = get_args(SpecialType)
            if v["special_type"] not in allowed_special_types:
                msg = f"long_press.special_type must be one of {allowed_special_types} (got {v['special_type']})"
                raise AssertionError(msg)
        if "special_type_data" in v and "special_type" not in v:
            msg = "long_press.special_type_data requires special_type to be set"
            raise AssertionError(msg)
        if "special_type" in v and "special_type_data" in v:
            cls._validate_special_type_data(v["special_type"], v["special_type_data"])

        return v

    @classmethod
    def templatable(cls: type[Button]) -> set[str]:
        """Return if an attribute is templatable, which is if the type-annotation is str."""
        schema = cls.schema()
        properties = schema["properties"]
        allowed_keys = {k for k, v in properties.items() if v["allow_template"]}
        return allowed_keys | {"long_press"}

    def maybe_start_or_cancel_timer(
        self,
        callback: Callable[[], None | Coroutine] | None = None,
    ) -> bool:
        """Start or cancel the timer."""
        if self.delay:
            if self._timer is None:
                assert isinstance(
                    self.delay,
                    (int, float),
                ), f"Invalid delay: {self.delay}"
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
        assert isinstance(self.delay, (int, float)), f"Invalid delay: {self.delay}"
        remaining = self._timer.remaining_time()
        pct = round(remaining / self.delay * 100)
        image = _draw_percentage_ring(pct, size)
        button = Button(
            text=f"{remaining:.0f}s\n{pct}%",
            text_color="white",
        )
        return button, image


class Dial(_ButtonDialBase, extra="forbid"):  # type: ignore[call-arg]
    """Dial configuration."""

    dial_event_type: str | None = Field(
        default=None,
        allow_template=True,
        description="The event type of the dial that will trigger the service."
        " Either `DialEventType.TURN` or `DialEventType.PUSH`.",
    )

    state_attribute: str | None = Field(
        default=None,
        allow_template=True,
        description="The attribute of the entity which gets used for the dial state.",
        # TODO: use this?
        # An attribute of an HA entity that the dial should control e.g., brightness for a light.
    )
    attributes: dict[str, float] | None = Field(
        default=None,
        allow_template=True,
        description="Sets the attributes of the dial."
        " `min`: The minimal value of the dial."
        " `max`: The maximal value of the dial."
        " `step`: the step size by which the value of the dial is increased by on an event.",
    )
    allow_touchscreen_events: bool = Field(
        default=False,
        allow_template=True,
        description="Whether events from the touchscreen are allowed, for example set the minimal value on `SHORT` and set maximal value on `LONG`.",
    )

    # vars for timer
    _timer: AsyncDelayedCallback | None = PrivateAttr(None)

    # Internal attributes for Dial
    _attributes: dict[str, float] = PrivateAttr(
        {"state": 0, "min": 0, "max": 100, "step": 1},
    )

    def update_attributes(self, data: dict[str, Any]) -> None:
        """Updates all home assistant entity attributes."""
        if self.attributes is None:
            self._attributes = data["attributes"]
        else:
            self._attributes = self.attributes

        if self.state_attribute is None:
            self._attributes.update({"state": float(data["state"])})
        else:
            try:
                if data["attributes"][self.state_attribute] is None:
                    self._attributes["state"] = 0
                else:
                    self._attributes["state"] = float(
                        data["attributes"][self.state_attribute],
                    )
            except KeyError:
                console.log(f"Could not find attribute {self.state_attribute}")
                self._attributes["state"] = 0

    def get_attributes(self) -> dict[str, float]:
        """Returns all home assistant entity attributes."""
        return self._attributes

    def increment_state(self, value: float) -> None:
        """Increments the value of the dial with checks for the minimal and maximal value."""
        num: float = self._attributes["state"] + value * self._attributes["step"]
        num = min(self._attributes["max"], num)
        num = max(self._attributes["min"], num)
        self._attributes["state"] = num

    def set_state(self, value: float) -> None:
        """Sets the value of the dial without checks for the minimal and maximal value."""
        self._attributes["state"] = value

    def rendered_template_dial(
        self,
        complete_state: StateDict,
    ) -> Dial:
        """Return a dial with the rendered text."""
        dct = self.dict(exclude_unset=True)
        for key in self.templatable():
            if key not in dct:
                continue
            val = dct[key]
            if isinstance(val, dict):
                for k, v in val.items():
                    val[k] = _render_jinja(v, complete_state, self)
            else:
                dct[key] = _render_jinja(val, complete_state, self)
        return Dial(**dct)

    # LCD/Touchscreen management
    def render_lcd_image(
        self,
        complete_state: StateDict,
        key: int,  # Key needs to be from sorted dials
        size: tuple[int, int],
        icon_mdi_margin: int = 0,
        font_filename: str = DEFAULT_FONT,
    ) -> Image.Image:
        """Render the image for the LCD."""
        try:
            image = None
            dial = self.rendered_template_dial(complete_state)

            if isinstance(dial.icon, str) and ":" in dial.icon:
                which, id_ = dial.icon.split(":", 1)
                if which == "spotify":
                    filename = _to_filename(dial.icon, ".jpeg")
                    image = _download_spotify_image(id_, filename).copy()
                elif which == "url":
                    filename = _url_to_filename(id_)
                    image = _download_image(id_, filename, size).copy()
                elif which == "ring":
                    pct = _maybe_number(id_)
                    assert isinstance(
                        pct,
                        (int, float),
                    ), f"Invalid ring percentage: {id_}"
                    image = _draw_percentage_ring(
                        percentage=pct,
                        size=size,
                        radius=40,
                    )

            icon_convert_to_grayscale = False
            text = dial.text
            text_color = dial.text_color or "white"

            assert dial.entity_id is not None
            if complete_state[dial.entity_id]["state"] == "off" and dial.icon_gray_when_off:
                icon_convert_to_grayscale = True

            if image is None:
                image = _init_icon(
                    icon_background_color=dial.icon_background_color,
                    icon_filename=dial.icon,
                    icon_mdi=dial.icon_mdi,
                    icon_mdi_margin=icon_mdi_margin,
                    icon_mdi_color=_named_to_hex(dial.icon_mdi_color or text_color),
                    size=size,
                ).copy()

            if icon_convert_to_grayscale:
                image = _convert_to_grayscale(image)

            if text is None:
                return image
            return _add_text_to_image(
                image=image,
                font_filename=font_filename,
                text_size=self.text_size,
                text=text,
                text_color=text_color,
                text_offset=self.text_offset,
            )

        except ValueError as e:
            console.log(e)
            warnings.warn(
                f"Failed to render icon for dial {key}",
                IconWarning,
                stacklevel=2,
            )
            return _generate_failed_icon(size=size)

    def start_or_restart_timer(
        self,
        callback: Callable[[], None | Coroutine] | None = None,
    ) -> bool:
        """Starts or restarts AsyncDelayedCallback timer."""
        if not self.delay:
            return False
        if self._timer is None:
            assert isinstance(
                self.delay,
                (int, float),
            ), f"Invalid delay: {self.delay}"
            self._timer = AsyncDelayedCallback(delay=self.delay, callback=callback)
        self._timer.start()
        return True


def _update_dial_descriptions() -> None:
    for _k, _v in Dial.__fields__.items():
        _v.field_info.description = (
            _v.field_info.description.replace("on the button", "above the dial")
            .replace("button", "dial")
            .replace("pressed", "rotated")
        )
        if _k == "delay":
            _v.field_info.description = (
                "The delay (in seconds) before the `service` is called."
                " This counts down from the specified time and collects the called turn events and"
                " sends the bundled value to Home Assistant after the dial hasn't been turned for the specified time in delay."
            )


_update_dial_descriptions()


def _to_filename(id_: str, suffix: str = "") -> Path:
    """Converts an id with ":" and "_" to a filename with optional suffix."""
    filename = ASSETS_PATH / id_.replace("/", "_").replace(":", "_")
    return filename.with_suffix(suffix)


def to_pandas_table(cls: type[BaseModel]) -> pd.DataFrame:
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
            "Description": info.description,
            "Default": code(info.default) if info.default is not Undefined else "",
            "Type": code(field._type_display()),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _pandas_to_rich_table(df: pd.DataFrame) -> Table:
    """Return a rich table from a pandas DataFrame."""
    table = Table()

    # Add the columns
    for column in df.columns:
        table.add_column(column)

    # Add the rows
    for _, row in df.iterrows():
        table.add_row(*row.astype(str).tolist())

    return table


class Page(BaseModel):
    """A page of buttons."""

    name: str = Field(description="The name of the page.")
    buttons: list[Button] = Field(
        default_factory=list,
        description="A list of buttons on the page.",
    )

    dials: list[Dial] = Field(
        default_factory=list,
        description="A list of dials on the page.",
    )

    _parent_page_index: int = PrivateAttr([])

    _dials_sorted: list[Dial] = PrivateAttr([])

    def sort_dials(self) -> list[tuple[Dial, Dial | None]]:
        """Sorts dials by dialEventType."""
        self._dials_sorted = []
        skip = False
        for index, dial in enumerate(self.dials):
            if index + 1 < len(self.dials):
                if skip:
                    skip = False
                    continue

                next_dial = self.dials[index + 1]
                if dial.dial_event_type != next_dial.dial_event_type:
                    self._dials_sorted.append((dial, next_dial))  # type: ignore[arg-type]
                    skip = True
                else:
                    self._dials_sorted.append((dial, None))  # type: ignore[arg-type]
            else:
                self._dials_sorted.append((dial, None))  # type: ignore[arg-type]
        return self._dials_sorted  # type: ignore[return-value]

    def get_sorted_key(self, dial: Dial) -> int | None:
        """Returns the integer key for a dial."""
        dial_list = self._dials_sorted
        for i in range(len(dial_list)):
            if dial in dial_list[i]:
                return i
        return None

    @classmethod
    def to_pandas_table(cls: type[Page]) -> pd.DataFrame:
        """Return a pandas DataFrame with the schema."""
        return to_pandas_table(cls)

    @classmethod
    def to_markdown_table(cls: type[Page]) -> str:
        """Return a markdown table with the schema."""
        return cls.to_pandas_table().to_markdown(index=False)


class Config(BaseModel):
    """Configuration file."""

    yaml_encoding: str | None = Field(
        default="utf-8",
        description="The encoding of the YAML file.",
    )
    pages: list[Page] = Field(
        default_factory=list,
        description="A list of `Page`s in the configuration.",
    )
    anonymous_pages: list[Page] = Field(
        default_factory=list,
        description="A list of anonymous Pages in the configuration."
        " These pages are hidden and not displayed when cycling through the pages."
        " They can only be reached using the `special_type: 'go-to-page'` button."
        " Designed for single use, these pages return to the previous page"
        " upon clicking a button.",
    )
    state_entity_id: str | None = Field(
        default=None,
        description="The entity ID to sync display state with. For"
        " example `input_boolean.streamdeck` or `binary_sensor.anyone_home`.",
    )
    brightness: int = Field(
        default=100,
        description="The default brightness of the Stream Deck (0-100).",
    )
    brightness_entity_id: str | None = Field(
        default=None,
        description="The entity ID to sync display brightness with (0-100). For"
        " example `input_number.streamdeck_brightness`.",
    )
    auto_reload: bool = Field(
        default=False,
        description="If True, the configuration YAML file will automatically"
        " be reloaded when it is modified.",
    )
    long_press_duration: float = Field(
        default=1.0,
        description="The duration (in seconds) for a long press.",
    )
    inactivity_time: float = Field(
        default=-1,
        description="Time in seconds to turn off the Stream Deck after inactivity. -1 to disable.",
    )
    _current_page_index: int = PrivateAttr(default=0)
    _parent_page_index: int = PrivateAttr(default=0)
    _is_on: bool = PrivateAttr(default=True)
    _detached_page: Page | None = PrivateAttr(default=None)
    _configuration_file: Path | None = PrivateAttr(default=None)
    _include_files: list[Path] = PrivateAttr(default_factory=list)
    _inactivity_task: asyncio.Task | None = PrivateAttr(default=None)

    @classmethod
    def load(
        cls: type[Config],
        fname: Path,
        yaml_encoding: str | None = None,
    ) -> Config:
        """Read the configuration file."""
        with fname.open() as f:
            data, include_files = safe_load_yaml(
                f,
                return_included_paths=True,
                encoding=yaml_encoding,
            )
            config = cls(**data)  # type: ignore[arg-type]
            config._configuration_file = fname
            config._include_files = include_files
            if not config.pages:
                msg = (
                    f"No pages defined in configuration file '{fname}'. "
                    "Please add at least one page with buttons."
                )
                raise ValueError(msg)
            config.current_page().sort_dials()
            return config

    def reload(self) -> None:
        """Reload the configuration file."""
        assert self._configuration_file is not None
        # Updates all public attributes
        new_config = self.load(
            self._configuration_file,
            yaml_encoding=self.yaml_encoding,
        )
        self.__dict__.update(new_config.__dict__)
        self._include_files = new_config._include_files
        # Set the private attributes we want to preserve
        if self._detached_page is not None:
            self._detached_page = self.to_page(self._detached_page.name)
            self.current_page().sort_dials()
        if self._current_page_index >= len(self.pages):
            # In case pages were removed, reset to the first page
            self._current_page_index = 0

    @classmethod
    def to_pandas_table(cls: type[Config]) -> pd.DataFrame:
        """Return a pandas DataFrame with the schema."""
        return to_pandas_table(cls)

    @classmethod
    def to_markdown_table(cls: type[Config]) -> str:
        """Return a markdown table with the schema."""
        return cls.to_pandas_table().to_markdown(index=False)

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
        self._parent_page_index = self._current_page_index
        self._current_page_index = self.next_page_index
        return self.pages[self._current_page_index]

    @property
    def next_page_index(self) -> int:
        """Return the next page index."""
        return (self._current_page_index + 1) % len(self.pages)

    @property
    def previous_page_index(self) -> int:
        """Return the previous page index."""
        return (self._current_page_index - 1) % len(self.pages)

    def previous_page(self) -> Page:
        """Go to the previous page."""
        self._parent_page_index = self._current_page_index
        self._current_page_index = self.previous_page_index
        return self.pages[self._current_page_index]

    def current_page(self) -> Page:
        """Return the current page."""
        if self._detached_page is not None:
            return self._detached_page
        return self.pages[self._current_page_index]

    def dial(self, key: int) -> Dial | None:
        """Gets Dial from key."""
        dials = self.current_page().dials
        if key < len(dials):
            return dials[key]
        return None

    def dial_sorted(self, key: int) -> tuple[Dial, Dial | None] | None:
        """Gets sorted dials by key."""
        dials = self.current_page()._dials_sorted
        if key < len(dials):
            return dials[key]
        return None

    def button(self, key: int) -> Button | None:
        """Return the button for a key."""
        buttons = self.current_page().buttons
        if key < len(buttons):
            return buttons[key]
        return None

    def to_page(self, page: int | str) -> Page:
        """Go to a page based on the page name or index."""
        self.close_detached_page()
        if isinstance(page, int):
            self._parent_page_index = self._current_page_index
            self._current_page_index = page
            return self.current_page()
        for i, p in enumerate(self.pages):
            if p.name == page:
                self._current_page_index = i
                return self.current_page()

        for p in self.anonymous_pages:
            if p.name == page:
                self._detached_page = p
                return p
        console.log(f"Could find page {page}, staying on current page")
        return self.current_page()

    def load_page_as_detached(self, page: Page) -> None:
        """Load a page as detached."""
        self._detached_page = page

    def close_detached_page(self) -> None:
        """Close the detached page."""
        self._detached_page = None

    def close_page(self) -> Page:
        """Close the current page."""
        self._detached_page = None
        self._current_page_index = self._parent_page_index
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
    percentage: float,
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


def _color_temp_kelvin_to_rgb(  # noqa: PLR0912
    colour_temperature: int,
) -> tuple[int, int, int]:
    """Converts from K to RGB.

    Algorithm courtesy of
    http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/.
    """
    # range check
    if colour_temperature < 1000:  # noqa: PLR2004
        colour_temperature = 1000
    elif colour_temperature > 40000:  # noqa: PLR2004
        colour_temperature = 40000

    tmp_internal = colour_temperature / 100.0

    # red
    if tmp_internal <= 66:  # noqa: PLR2004
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        if tmp_red < 0:
            red = 0
        elif tmp_red > 255:  # noqa: PLR2004
            red = 255
        else:
            red = int(tmp_red)

    # green
    if tmp_internal <= 66:  # noqa: PLR2004
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:  # noqa: PLR2004
            green = 255
        else:
            green = int(tmp_green)
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:  # noqa: PLR2004
            green = 255
        else:
            green = int(tmp_green)

    # blue
    if tmp_internal >= 66:  # noqa: PLR2004
        blue = 255
    elif tmp_internal <= 19:  # noqa: PLR2004
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        if tmp_blue < 0:
            blue = 0
        elif tmp_blue > 255:  # noqa: PLR2004
            blue = 255
        else:
            blue = int(tmp_blue)

    return red, green, blue


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
        rgb = tuple(round(x * 255) for x in colorsys.hsv_to_rgb(*hsv))
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
    deck_key_count: int,
    colors: tuple[str, ...] | None,
    color_temp_kelvin: tuple[int, ...] | None,
    colormap: str | None,
    brightnesses: tuple[int, ...] | None,
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
    buttons_color_temp_kelvin = [
        Button(
            icon_background_color=_rgb_to_hex(_color_temp_kelvin_to_rgb(kelvin)),
            service="light.turn_on",
            service_data={
                "entity_id": entity_id,
                "color_temp_kelvin": kelvin,
            },
        )
        for kelvin in (color_temp_kelvin or ())
    ]
    buttons_brightness = []
    for brightness in brightnesses if brightnesses is not None else [0, 33, 66, 100]:
        background_color = _scale_hex_color("#FFFFFF", brightness / 100)
        button = Button(
            icon_background_color=background_color,
            service="light.turn_on",
            text_color=_max_contrast_color(background_color),
            text=f"{brightness}%" if brightness > 0 else "OFF",
            service_data={
                "entity_id": entity_id,
                "brightness_pct": brightness,
            },
        )
        buttons_brightness.append(button)
    buttons_back = [Button(special_type="close-page")]
    number_of_buttons_except_close_and_empty = (
        len(buttons_colors)
        + len(buttons_color_temp_kelvin)
        + len(buttons_brightness)
        + len(buttons_back)
    )
    number_of_empty_buttons = deck_key_count - number_of_buttons_except_close_and_empty
    if number_of_empty_buttons > 0:
        buttons_empty = [Button(special_type="empty")] * number_of_empty_buttons
    else:
        console.log(
            f"""
            Too many buttons on light page. Not showing everything"
            Deck key count: {deck_key_count}
            Number of defined buttons: {number_of_buttons_except_close_and_empty}
            colors: {colors}
            color_temp_kelvin: {color_temp_kelvin}
            colormap: {colormap}
            brightnesses: {brightnesses}
            """,
        )
        buttons_empty = []

    return Page(
        name="Lights",
        buttons=buttons_colors
        + buttons_color_temp_kelvin
        + buttons_empty
        + buttons_brightness
        + buttons_back,
        dials=[],
    )


@asynccontextmanager
async def setup_ws(
    host: str,
    token: str,
    protocol: Literal["wss", "ws"],
    *,
    allow_weaker_ssl: bool = False,
) -> websockets.ClientConnection:
    """Set up the connection to Home Assistant."""
    uri = f"{protocol}://{host}/api/websocket"
    connect_args: dict[str, Any] = {"max_size": 10485760}  # limit size to 10 MiB
    if protocol == "wss":
        ssl_context = ssl.create_default_context()
        connect_args["ssl"] = ssl_context

    while True:
        try:
            async with websockets.connect(uri, **connect_args) as websocket:
                # Send an authentication message to Home Assistant
                auth_payload = {"type": "auth", "access_token": token}
                await websocket.send(json.dumps(auth_payload))

                # Wait for the authentication response
                auth_response = await websocket.recv()
                console.log(auth_response)
                console.log("Connected to Home Assistant")
                yield websocket
        except ConnectionResetError:  # noqa: PERF203
            # Connection was reset, retrying in 3 seconds
            console.print_exception(show_locals=True)
            console.log("Connection was reset, retrying in 3 seconds")
            if allow_weaker_ssl:
                ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")
                console.log("Using weaker SSL settings")
            await asyncio.sleep(5)


async def subscribe_state_changes(
    websocket: websockets.ClientConnection,
) -> None:
    """Subscribe to the state change events."""
    subscribe_payload = {
        "type": "subscribe_events",
        "event_type": "state_changed",
        "id": _next_id(),
    }
    await websocket.send(json.dumps(subscribe_payload))


def reset_inactivity_timer(
    config: Config,
    deck: StreamDeck,
) -> None:
    """Turn off the Stream Deck after inactivity."""

    async def turn_off_timer() -> None:
        if config.inactivity_time > 0:
            await asyncio.sleep(config.inactivity_time)
            console.log(
                f"Turning off Stream Deck due to inactivity after {config.inactivity_time} seconds",
            )
            turn_off(config, deck)

    if config._inactivity_task is not None:
        config._inactivity_task.cancel()

    if config.inactivity_time > 0:
        config._inactivity_task = asyncio.create_task(turn_off_timer())


async def handle_changes(
    websocket: websockets.ClientConnection,
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

    async def watch_configuration_file() -> None:
        """Watch for changes to the configuration file and reload config when it changes."""
        if config._configuration_file is None:
            console.log("[red bold] No configuration file to watch[/]")
            return

        def edit_time(fn: Path) -> float:
            return fn.stat().st_mtime if fn.exists() else 0

        last_modified_time = edit_time(config._configuration_file)
        while True:
            files = [config._configuration_file, *config._include_files]
            if config.auto_reload and any(edit_time(fn) > last_modified_time for fn in files):
                console.log("Configuration file has been modified, reloading")
                last_modified_time = max(edit_time(fn) for fn in files)
                try:
                    config.reload()
                    reset_inactivity_timer(config, deck)
                    deck.reset()
                    update_all_key_images(deck, config, complete_state)
                    update_all_dials(deck, config, complete_state)
                except Exception as e:  # noqa: BLE001
                    console.log(f"Error reloading configuration: {e}")

            await asyncio.sleep(1)

    # Run the websocket message processing and timer update tasks concurrently
    await asyncio.gather(
        process_websocket_messages(),
        call_update_timers(),
        watch_configuration_file(),
    )


def _keys(entity_id: str, buttons: list[Button] | list[Dial]) -> list[int]:
    """Get the key indices for an entity_id."""
    return [
        i
        for i, button in enumerate(buttons)
        if button.entity_id == entity_id  # type: ignore[attr-defined] # noqa: PLR1714
        or button.linked_entity == entity_id  # type: ignore[attr-defined]
    ]


def _update_state(
    complete_state: StateDict,
    data: dict[str, Any],
    config: Config,
    deck: StreamDeck,
) -> None:
    """Update the state dictionary and update the keys."""
    buttons = config.current_page().buttons
    dials = config.current_page().dials
    if data["type"] == "event":
        event_data = data["event"]
        if event_data["event_type"] == "state_changed":
            event_data = event_data["data"]
            eid = event_data["entity_id"]
            complete_state[eid] = event_data["new_state"]

            # Handle the brightness entity
            if eid == config.brightness_entity_id:
                _sync_brightness_from_entity(
                    config.brightness_entity_id,
                    complete_state,
                    config,
                    deck,
                )
                return

            # Handle the state entity (turning on/off display)
            if eid == config.state_entity_id:
                is_on = complete_state[config.state_entity_id]["state"] == "on"
                if is_on:
                    turn_on(config, deck, complete_state)
                else:
                    turn_off(config, deck)
                return

            keys_dials = _keys(eid, dials)
            for key in keys_dials:
                console.log(f"Updating dial {key} for {eid}")
                update_dial(
                    deck=deck,
                    key=key,
                    config=config,
                    complete_state=complete_state,
                    data=data,
                )

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
    attrs = complete_state.get(entity_id, {}).get("attributes", {})
    state_attr = attrs.get(attr)
    return _maybe_number(state_attr)


def _is_state_attr(
    entity_id: str,
    attr: str,
    value: Any,
    complete_state: StateDict,
) -> bool:
    """Check if the state attribute for an entity is a value."""
    return _state_attr(entity_id, attr, complete_state) == _maybe_number(value)


def _is_float(s: str) -> bool:
    try:
        float(s)
    except ValueError:
        return False
    else:
        return True


def _maybe_number(s: str, *, rounded: bool = False) -> int | str | float:
    """Convert a string to a number if possible."""
    if not isinstance(s, str):  # already a number or other type
        return s

    if _is_integer(s):
        num = int(s)
    elif _is_float(s):
        num = float(s)  # type: ignore[assignment]
    else:
        return s

    if rounded:
        return round(num)

    return num


def _is_integer(s: str) -> bool:
    try:
        int(s)
    except ValueError:
        return False
    else:
        return True


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
    state = _maybe_number(state, rounded=rounded)
    if with_unit:
        unit = entity_state.get("attributes", {}).get("unit_of_measurement")
        if unit:
            state = f"{state} {unit}"
    return state


def _is_state(
    entity_id: str,
    state: str,
    complete_state: StateDict,
) -> bool:
    """Check if the state for an entity is a value."""
    return _states(entity_id, complete_state=complete_state) == _maybe_number(state)


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


def _is_number_filter(value: Any | None) -> bool:
    """Check if a value is a number (int, float, or string representation of a number)."""
    if value is None:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            float(value)
        except ValueError:
            return False
        else:
            return True
    return False


def _round(num: float, digits: int) -> int | float:
    """Returns rounded value with number of digits."""
    return round(num, digits)


def _dial_value(dial: Dial | None) -> float:
    if dial is None:
        return 0
    try:
        attributes = dial.get_attributes()
        return float(attributes["state"])
    except KeyError:
        return 0


def _dial_attr(
    attr: str,
    dial: Dial | None,
) -> float:
    if dial is None:
        return 0
    try:
        assert attr is not None
        dial_attributes = dial.get_attributes()
        return dial_attributes[attr]
    except ValueError as e:
        console.log(
            f"Error while trying to get attribute {attr} from dial with error code {e}",
        )
        return 0


def _render_jinja(
    text: str,
    complete_state: StateDict,
    dial: Dial | None = None,
) -> str:
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
        env.filters["is_number"] = _is_number_filter
        template = env.from_string(text)
        return template.render(
            min=min,
            max=max,
            is_state_attr=ft.partial(_is_state_attr, complete_state=complete_state),
            state_attr=ft.partial(_state_attr, complete_state=complete_state),
            states=ft.partial(_states, complete_state=complete_state),
            is_state=ft.partial(_is_state, complete_state=complete_state),
            round=_round,
            dial_value=ft.partial(_dial_value, dial=dial),
            dial_attr=ft.partial(_dial_attr, dial=dial),
        ).strip()
    except jinja2.exceptions.TemplateError as err:
        console.print_exception(show_locals=True)
        console.log(f"Error rendering template: {err} with error type {type(err)}")
        return text


async def get_states(websocket: websockets.ClientConnection) -> dict[str, Any]:
    """Get the current state of all entities."""
    _id = _next_id()
    subscribe_payload = {"type": "get_states", "id": _id}
    await websocket.send(json.dumps(subscribe_payload))
    while True:
        data = json.loads(await websocket.recv())
        if data["type"] == "result":
            # Extract the state data from the response
            return {state["entity_id"]: state for state in data["result"]}


async def unsubscribe(websocket: websockets.ClientConnection, id_: int) -> None:
    """Unsubscribe from an event."""
    subscribe_payload = {
        "id": _next_id(),
        "type": "unsubscribe_events",
        "subscription": id_,
    }
    await websocket.send(json.dumps(subscribe_payload))


async def call_service(
    websocket: websockets.ClientConnection,
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
    hex_color = hex_color.removeprefix("#")

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
        etree.fromstring(svg_content)
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
        if icon.size != size:
            console.log(f"Resizing icon {icon_filename} to from {icon.size} to {size}")
            icon = icon.resize(size)
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


@ft.lru_cache(maxsize=1000)
def _generate_text_image(
    *,
    font_filename: str,
    text_size: int,
    text: str,
    text_color: str,
    text_offset: int = 0,
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
    """Render text onto a transparent image and return it for compositing."""
    if text_size == 0:
        console.log(f"Text size is 0, not drawing text: {text!r}")
        return Image.new("RGBA", size, (0, 0, 0, 0))

    text_image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_image)
    font = ImageFont.truetype(str(ASSETS_PATH / font_filename), text_size)
    draw.text(
        (size[0] / 2, size[1] / 2 + text_offset),
        text=text,
        font=font,
        anchor="ms",
        fill=text_color,
        align="center",
    )
    return text_image


def _add_text_to_image(
    image: Image.Image,
    *,
    font_filename: str,
    text_size: int,
    text: str,
    text_color: str,
    text_offset: int = 0,
) -> Image.Image:
    """Combine two images."""
    text_image = _generate_text_image(
        font_filename=font_filename,
        text_size=text_size,
        text=text,
        text_color=text_color,
        text_offset=text_offset,
        size=image.size,
    )
    return Image.alpha_composite(image.convert("RGBA"), text_image).convert("RGB")


@ft.lru_cache(maxsize=1)
def _generate_failed_icon(
    size: tuple[int, int] = (ICON_PIXELS, ICON_PIXELS),
) -> Image.Image:
    """Generate a red icon with 'rendering failed' text."""
    background_color = "red"
    text_color = "white"
    font_filename = DEFAULT_FONT
    text_size = int(min(size) * 0.15)  # Adjust font size based on the icon size
    icon = Image.new("RGB", size, background_color)
    return _add_text_to_image(
        image=icon,
        font_filename=font_filename,
        text_size=text_size,
        text="Rendering\nfailed",
        text_color=text_color,
    )


@ft.lru_cache(maxsize=1)
def _get_blank_image(size: tuple[int, int]) -> bytes:
    """Get or create a blank (black) JPEG image for the given size."""
    blank_image: Image.Image = Image.new("RGB", size, (0, 0, 0))
    img_bytes = io.BytesIO()
    blank_image.save(img_bytes, format="JPEG")
    return img_bytes.getvalue()


def _get_size_per_dial(deck: StreamDeck) -> tuple[int, int]:
    """Get the size of each dial's LCD region."""
    size_lcd: tuple[int, int] = deck.touchscreen_image_format()["size"]
    return (size_lcd[0] // deck.dial_count(), size_lcd[1])


def update_all_dials(
    deck: StreamDeck,
    config: Config,
    complete_state: StateDict,
) -> None:
    """Updates configured dials and clears unconfigured dial slots."""
    console.log("Called update_all_dials")

    # Track configured dial keys
    configured_keys: set[int] = set()

    # Update configured dials
    for key, current_dial in enumerate(config.current_page().dials):
        assert current_dial is not None
        if current_dial.entity_id is None:
            console.log(f"Dial {key} has no entity_id, skipping")
            continue
        dial_key: int | None = config.current_page().get_sorted_key(current_dial)
        if dial_key is None:
            console.log(f"Dial {key} has no valid dial_key, skipping")
            continue
        configured_keys.add(dial_key)
        update_dial(
            deck,
            key,
            config,
            complete_state,
            complete_state[current_dial.entity_id],
        )

    # Clear unconfigured dial slots
    num_physical: int = deck.dial_count()
    unconfigured_keys: set[int] = set(range(num_physical)) - configured_keys
    if unconfigured_keys:
        size_per_dial: tuple[int, int] = _get_size_per_dial(deck)
        lcd_image_bytes: bytes = _get_blank_image(size_per_dial)
        for dial_key in unconfigured_keys:
            dial_offset: int = dial_key * size_per_dial[0]
            deck.set_touchscreen_image(
                lcd_image_bytes,
                dial_offset,
                0,
                width=size_per_dial[0],
                height=size_per_dial[1],
            )
        console.log(f"Cleared unconfigured dial slots: {unconfigured_keys}")


def update_dial(
    deck: StreamDeck,
    key: int,
    config: Config,
    complete_state: StateDict,
    data: dict[str, Any] | None = None,
) -> None:
    """Update the dial."""
    dial = config.dial(key)
    assert dial is not None

    if dial.dial_event_type == "PUSH":
        return

    if data is not None:
        if "event" in data and "data" in data["event"]:
            event_data = data["event"]["data"]
            new_state = event_data["new_state"]
            dial.update_attributes(new_state)
        else:
            dial.update_attributes(data)

    size_per_dial = _get_size_per_dial(deck)
    dial_key = config.current_page().get_sorted_key(dial)
    assert dial_key is not None
    dial_offset = dial_key * size_per_dial[0]
    image = dial.render_lcd_image(
        complete_state=complete_state,
        size=size_per_dial,
        key=dial_key,
    )
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="JPEG")
    lcd_image_bytes = img_bytes.getvalue()
    deck.set_touchscreen_image(
        lcd_image_bytes,
        dial_offset,
        0,
        width=size_per_dial[0],
        height=size_per_dial[1],
    )


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

    def clear_image() -> None:
        deck.set_key_image(key, None)

    if button is None:
        clear_image()
        return
    if button.special_type == "empty":
        clear_image()
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


def turn_on(config: Config, deck: StreamDeck, complete_state: StateDict) -> None:
    """Turn on the Stream Deck and update all key images."""
    console.log(f"Calling turn_on, with {config._is_on=}")
    if config._is_on:
        return
    config._is_on = True
    update_all_key_images(deck, config, complete_state)
    update_all_dials(deck, config, complete_state)
    deck.set_brightness(config.brightness)


def turn_off(config: Config, deck: StreamDeck) -> None:
    """Turn off the Stream Deck."""
    console.log(f"Calling turn_off, with {config._is_on=}")
    if not config._is_on:
        return
    config._is_on = False
    # This resets all buttons except the turn-off button that
    # was just pressed, however, this doesn't matter with the
    # 0 brightness. Unless no button was pressed.
    deck.reset()
    deck.set_brightness(0)


async def _sync_input_boolean(
    state_entity_id: str | None,
    websocket: websockets.ClientConnection,
    state: Literal["on", "off"],
) -> None:
    """Sync the input boolean state with the Stream Deck."""
    if (state_entity_id is not None) and (state_entity_id.split(".")[0] == "input_boolean"):
        await call_service(
            websocket,
            f"input_boolean.turn_{state}",
            {},
            {"entity_id": state_entity_id},
        )


def _sync_brightness_from_entity(
    brightness_entity_id: str | None,
    complete_state: StateDict,
    config: Config,
    deck: StreamDeck,
) -> None:
    """Sync the brightness from a Home Assistant entity to the Stream Deck."""
    if brightness_entity_id is None:
        return
    if brightness_entity_id not in complete_state:
        console.log(f"Brightness entity {brightness_entity_id} not found in state")
        return
    try:
        brightness = int(float(complete_state[brightness_entity_id]["state"]))
    except (ValueError, TypeError):
        console.log(f"Invalid brightness state for {brightness_entity_id}")
        return
    if 0 <= brightness <= 100:  # noqa: PLR2004
        console.log(f"Setting brightness from {brightness_entity_id}: {brightness}%")
        config.brightness = brightness
        if config._is_on:
            deck.set_brightness(brightness)
    else:
        console.log(f"Invalid brightness value {brightness}, must be 0-100")


def _on_touchscreen_event_callback(
    websocket: websockets.ClientConnection,
    complete_state: StateDict,
    config: Config,
) -> Callable[
    [StreamDeck, TouchscreenEventType, dict[str, int]],
    Coroutine[StreamDeck, TouchscreenEventType, None],
]:
    async def touchscreen_event_callback(
        deck: StreamDeck,
        event_type: TouchscreenEventType,
        value: dict[str, int],
    ) -> None:
        console.log(f"Touchscreen event {event_type} called at value {value}")
        reset_inactivity_timer(config, deck)
        if event_type == TouchscreenEventType.DRAG:
            # go to next or previous page
            if value["x"] > value["x_out"]:
                console.log(f"Going to page {config.next_page_index}")
                config.to_page(config.next_page_index)

            else:
                console.log(f"Going to page {config.next_page_index}")
                config.to_page(config.previous_page_index)
            config.current_page().sort_dials()
            update_all_key_images(deck, config, complete_state)
            update_all_dials(deck, config, complete_state)
        else:
            # Short touch: Sets dial value to minimal value
            # Long touch: Sets dial to maximal value
            lcd_icon_size = deck.touchscreen_image_format()["size"][0] / deck.dial_count()
            icon_pos = value["x"] // lcd_icon_size
            dials = config.dial_sorted(int(icon_pos))
            assert dials is not None

            selected_dial = (
                dials[0] if dials[0].dial_event_type == DialEventType.TURN.name else dials[1]
            )
            assert selected_dial is not None

            if selected_dial.allow_touchscreen_events:
                if event_type == TouchscreenEventType.SHORT:
                    set_type = "min"
                elif event_type == TouchscreenEventType.LONG:
                    set_type = "max"
                selected_dial.set_state(selected_dial.get_attributes()[set_type])
                await handle_dial_event(
                    websocket,
                    complete_state,
                    config,
                    dials,
                    deck,
                    DialEventType.TURN,
                    0,
                    False,  # noqa: FBT003
                )

    return touchscreen_event_callback


async def handle_dial_event(
    websocket: websockets.ClientConnection,
    complete_state: StateDict,
    config: Config,
    dial: tuple[Dial, Dial | None],
    deck: StreamDeck,
    event_type: DialEventType,
    value: int,
    local_update: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Handles dial_event."""
    if not config._is_on:
        turn_on(config, deck, complete_state)
        await _sync_input_boolean(config.state_entity_id, websocket, "on")
        return

    if dial[0].dial_event_type == event_type.name:
        selected_dial = dial[0]
    elif dial[1].dial_event_type == event_type.name:  # type: ignore[union-attr]
        assert isinstance(dial[1], Dial)
        selected_dial = dial[1]
    else:
        console.log("Could not resolve event type for dial")
        return
    dial_num_sorted = config.current_page().get_sorted_key(selected_dial)
    assert selected_dial is not None

    if event_type == DialEventType.TURN:
        selected_dial.increment_state(value)
    elif value:
        return

    if selected_dial.service is not None:
        selected_dial = selected_dial.rendered_template_dial(complete_state)
        service_data = (
            {"entity_id": selected_dial.entity_id}
            if selected_dial.service_data is None
            else selected_dial.service_data
        )

    # Ensures the entity id is given to the service even if service_data is set
    if "entity_id" not in service_data:
        service_data["entity_id"] = selected_dial.entity_id

    assert selected_dial.service is not None
    if local_update:
        assert isinstance(dial_num_sorted, int)
        update_dial(deck, dial_num_sorted, config, complete_state)
        return
    console.log(
        f"Calling service {selected_dial.service} with data {selected_dial.service_data}",
    )
    await call_service(
        websocket,
        selected_dial.service,
        service_data,
        selected_dial.target,
    )


def _on_dial_event_callback(
    websocket: websockets.ClientConnection,
    complete_state: StateDict,
    config: Config,
) -> Callable[
    [StreamDeck, int, DialEventType, int],
    Coroutine[StreamDeck, int, None],
]:
    async def dial_event_callback(
        deck: StreamDeck,
        dial_num: int,
        event_type: DialEventType,
        value: int,
    ) -> None:
        console.log(
            f"Dial {dial_num} event {event_type} at value {value} has been called",
        )
        reset_inactivity_timer(config, deck)
        dial = config.dial_sorted(dial_num)
        assert dial is not None

        async def callback() -> None:
            await handle_dial_event(
                websocket,
                complete_state,
                config,
                dial,
                deck,
                event_type,
                0,
            )

        current_dial = config.dial(dial_num)
        assert isinstance(current_dial, Dial)
        if event_type == DialEventType.TURN and current_dial.start_or_restart_timer(
            callback,
        ):
            await handle_dial_event(
                websocket,
                complete_state,
                config,
                dial,
                deck,
                event_type,
                value,
                True,  # noqa: FBT003
            )
            return

        await handle_dial_event(
            websocket,
            complete_state,
            config,
            dial,
            deck,
            event_type,
            value,
        )

    return dial_event_callback


async def _handle_key_press(  # noqa: PLR0912, PLR0915
    websocket: websockets.ClientConnection,
    complete_state: StateDict,
    config: Config,
    button: Button,
    deck: StreamDeck,
    *,
    is_long_press: bool,
) -> None:
    if not config._is_on:
        turn_on(config, deck, complete_state)
        await _sync_input_boolean(config.state_entity_id, websocket, "on")
        return

    def update_all() -> None:
        config.current_page().sort_dials()
        update_all_key_images(deck, config, complete_state)
        update_all_dials(deck, config, complete_state)

    if is_long_press and button.long_press:
        entity_id = button.long_press.get("entity_id", button.entity_id)
        service = button.long_press.get("service")
        service_data = button.long_press.get("service_data")
        target = button.long_press.get("target", button.target)
        special_type = button.long_press.get("special_type")
        special_type_data = button.long_press.get("special_type_data")
    else:
        entity_id = button.entity_id
        service = button.service
        service_data = button.service_data
        target = button.target
        special_type = button.special_type
        special_type_data = button.special_type_data

    if special_type == "next-page":
        config.next_page()
        update_all()
    elif special_type == "previous-page":
        config.previous_page()
        update_all()
    elif special_type == "close-page":
        config.close_page()
        update_all()
    elif special_type == "go-to-page":
        assert isinstance(special_type_data, (str, int))
        config.to_page(special_type_data)  # type: ignore[arg-type]
        update_all()
        return  # to skip the _detached_page reset below
    elif special_type == "turn-off":
        turn_off(config, deck)
        await _sync_input_boolean(config.state_entity_id, websocket, "off")
    elif special_type == "light-control":
        assert isinstance(special_type_data, dict)
        page = _light_page(
            entity_id=entity_id,
            n_colors=9,
            colormap=special_type_data.get("colormap", None),
            colors=special_type_data.get("colors", None),
            color_temp_kelvin=special_type_data.get("color_temp_kelvin", None),
            brightnesses=special_type_data.get("brightnesses", None),
            deck_key_count=deck.key_count(),
        )
        config.load_page_as_detached(page)
        update_all()
        return  # to skip the _detached_page reset below
    elif special_type == "reload":
        config.reload()
        reset_inactivity_timer(config, deck)
        update_all()
        return
    elif service is not None:
        button = button.rendered_template_button(complete_state)
        # Re-extract values from rendered button to get template-rendered values
        if is_long_press and button.long_press:
            service = button.long_press.get("service") or button.service
            service_data = button.long_press.get("service_data")
            entity_id = button.long_press.get("entity_id", button.entity_id)
            target = button.long_press.get("target", button.target)
        else:
            service = button.service
            service_data = button.service_data
            entity_id = button.entity_id
            target = button.target
        if service_data is None:
            service_data = {}
            if entity_id is not None:
                service_data["entity_id"] = entity_id
        console.log(f"Calling service {service} with data {service_data}")
        assert service is not None  # for mypy
        await call_service(websocket, service, service_data, target)

    if config._detached_page:
        config.close_detached_page()
        update_all()


def _on_press_callback(
    websocket: websockets.ClientConnection,
    complete_state: StateDict,
    config: Config,
) -> Callable[[StreamDeck, int, bool], Coroutine[StreamDeck, int, None]]:
    press_start_times: dict[int, float] = {}

    async def key_change_callback(
        deck: StreamDeck,
        key: int,
        key_pressed: bool,  # noqa: FBT001
    ) -> None:
        console.log(f"Key {key} {'pressed' if key_pressed else 'released'}")
        reset_inactivity_timer(config, deck)

        button = config.button(key)
        assert button is not None
        if key_pressed:
            press_start_times[key] = time.time()
            console.log(
                f"Key {key} pressed, starting long press monitor with threshold {config.long_press_duration}s",
            )
            update_key_image(
                deck,
                key=key,
                config=config,
                complete_state=complete_state,
                key_pressed=True,
            )
            return

        # Key released
        press_duration = time.time() - press_start_times.pop(key)
        console.log(f"Key {key} released after {press_duration:.2f}s")
        update_key_image(
            deck,
            key=key,
            config=config,
            complete_state=complete_state,
            key_pressed=False,
        )
        cb = ft.partial(
            _try_handle_key_press,
            websocket=websocket,
            complete_state=complete_state,
            config=config,
            button=button,
            deck=deck,
            is_long_press=False,
        )
        if press_duration < config.long_press_duration:
            console.log(f"Handling short press for key {key}")
            if button.maybe_start_or_cancel_timer(cb):
                console.log(f"Timer started for key {key}, delaying short press")
            else:
                await cb(is_long_press=False)
        else:
            console.log(f"Handling long press for key {key}")
            await cb(is_long_press=True)

    return key_change_callback


async def _try_handle_key_press(
    websocket: websockets.ClientConnection,
    complete_state: StateDict,
    config: Config,
    button: Button,
    deck: StreamDeck,
    *,
    is_long_press: bool,
) -> None:
    try:
        await _handle_key_press(
            websocket,
            complete_state,
            config,
            button,
            deck,
            is_long_press=is_long_press,
        )
    except Exception as e:
        console.print_exception(show_locals=True)
        which = "long" if is_long_press else "short"
        console.log(f"Error in {which} press handling: {e}")
        raise


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
        svg_tree = etree.fromstring(svg_content)
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
        Image.open(io.BytesIO(png_content)) if png_content else Image.new("RGBA", size, fill_color)
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
        image = Image.open(filename)
        # To correctly size after getting from file
        return image.resize(size)
    image_content = _download(url)
    image = Image.open(io.BytesIO(image_content))
    if image.mode != "RGB":
        image = image.convert("RGB")
    if filename is not None:
        # If filename has no extension, add one based on the detected format
        if filename.suffix == "":
            # Determine format from the image, default to JPEG
            fmt = image.format if image.format else "JPEG"
            ext = fmt.lower()
            if ext == "jpeg":
                ext = "jpg"
            filename = filename.with_suffix(f".{ext}")
        image.save(filename)
    return image.resize(size)


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


async def _run_connection_session(
    host: str,
    token: str,
    protocol: Literal["wss", "ws"],
    config: Config,
    deck: StreamDeck,
    *,
    allow_weaker_ssl: bool = False,
) -> None:
    """Handles a single connection session with Home Assistant."""
    async with setup_ws(host, token, protocol, allow_weaker_ssl=allow_weaker_ssl) as websocket:
        try:
            complete_state = await get_states(websocket)

            # Sync brightness from HA entity if configured
            _sync_brightness_from_entity(
                config.brightness_entity_id,
                complete_state,
                config,
                deck,
            )

            # Turn on state entity boolean on home assistant
            await _sync_input_boolean(config.state_entity_id, websocket, "on")
            update_all_key_images(deck, config, complete_state)
            deck.set_key_callback_async(
                _on_press_callback(websocket, complete_state, config),
            )
            update_all_dials(deck, config, complete_state)
            if deck.dial_count() != 0:
                deck.set_dial_callback_async(
                    _on_dial_event_callback(websocket, complete_state, config),
                )
            if deck.is_visual():
                deck.set_touchscreen_callback_async(
                    _on_touchscreen_event_callback(websocket, complete_state, config),
                )

            await subscribe_state_changes(websocket)
            await handle_changes(websocket, complete_state, deck, config)
        finally:
            console.log("Cleaning up connection session...")
            await _sync_input_boolean(config.state_entity_id, websocket, "off")


async def run(
    deck: StreamDeck,
    host: str,
    token: str,
    protocol: Literal["wss", "ws"],
    config: Config,
    retry_attempts: int = 0,
    retry_delay: float = 0.0,
    *,
    allow_weaker_ssl: bool = False,
) -> None:
    """Main entry point for the Stream Deck integration, with retry logic."""
    deck.set_brightness(config.brightness)
    attempt = 0

    while retry_attempts < 0 or attempt <= retry_attempts:
        try:
            console.log(f"Attempting connection (attempt {attempt + 1})...")
            await _run_connection_session(
                host,
                token,
                protocol,
                config,
                deck,
                allow_weaker_ssl=allow_weaker_ssl,
            )
            console.log("Connection session ended cleanly.")
            break

        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.InvalidURI,
            websockets.exceptions.InvalidHandshake,
            OSError,  # Catches socket errors, ConnectionRefusedError, etc.
            asyncio.TimeoutError,
        ) as e:
            attempt += 1
            console.log(
                f"[WARNING] WebSocket connection failed: {type(e).__name__}: {e}",
            )
            if retry_attempts >= 0 and attempt > retry_attempts:
                console.log("[ERROR] Max retry attempts reached, giving up.")
                break
            console.log(
                f"[INFO] Retrying in {retry_delay} seconds... (attempt {attempt + 1})",
            )
            await asyncio.sleep(retry_delay)
        except Exception as e:  # noqa: BLE001
            console.log(
                f"[ERROR] An unexpected error occurred during connection/session: {type(e).__name__}: {e}",
            )
            console.print_exception(show_locals=True)
            break  # Exit loop on unexpected errors

    console.log("Exiting application. Resetting deck.")
    deck.reset()


def _rich_table_str(df: pd.DataFrame) -> str:
    table = _pandas_to_rich_table(df)
    console = Console(file=io.StringIO(), width=120)
    console.print(table)
    return console.file.getvalue()


# Define YAML node type
YamlNode = dict[str, Any] | list[Any] | str | int | float | bool | None


def _traverse_yaml(node: YamlNode, variables: dict[str, str]) -> YamlNode:
    """Substitute variables in YAML node."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                result = value
                for var, var_value in variables.items():
                    regex_format = rf"\$\{{{var}\}}"
                    result = re.sub(regex_format, str(var_value), result)
                node[key] = result
            else:
                node[key] = _traverse_yaml(value, variables)
        return node
    if isinstance(node, list):
        return [_traverse_yaml(item, variables) for item in node]
    if isinstance(node, str):
        result = node
        for var, var_value in variables.items():
            regex_format = rf"\$\{{{var}\}}"
            result = re.sub(regex_format, str(var_value), result)
        return result
    return node


def safe_load_yaml(
    f: TextIO | str,
    *,
    return_included_paths: bool = False,
    encoding: str | None = None,
) -> Any | tuple[Any, list]:
    """Load a YAML file."""
    included_files: list[Path] = []

    class IncludeLoader(yaml.SafeLoader):
        """YAML Loader with `!include` constructor."""

        def __init__(self, stream: Any) -> None:
            """Initialize IncludeLoader."""
            self._root = Path(stream.name).parent if hasattr(stream, "name") else Path.cwd()
            super().__init__(stream)

        def _load_include_file(self, filepath: Path) -> Any:
            """Load a YAML file for an !include directive."""
            with filepath.open(encoding=encoding) as include_file:
                return yaml.load(include_file, IncludeLoader)  # noqa: S506

        def include(self, node: yaml.nodes.Node) -> Any:
            """Include file referenced at node."""
            if isinstance(node.value, str):
                filepath = self._root / str(self.construct_scalar(node))  # type: ignore[arg-type]
                included_files.append(filepath)
                return self._load_include_file(filepath)
            mapping = self.construct_mapping(node, deep=True)  # type: ignore[arg-type]
            assert mapping is not None
            filepath = self._root / str(mapping["file"])
            included_files.append(filepath)
            variables = mapping.get("vars", {})

            loaded_data = self._load_include_file(filepath)
            assert loaded_data is not None
            if variables:
                _traverse_yaml(loaded_data, variables)
            return loaded_data

        def construct_sequence(  # type: ignore[override]
            self,
            node: yaml.SequenceNode,
            deep: bool = False,  # noqa: FBT001, FBT002
        ) -> Any:
            """Override sequence construction to flatten !include lists."""
            result = []
            for subnode in node.value:
                if isinstance(subnode, yaml.ScalarNode) and subnode.tag == "!include":
                    # Process !include directive
                    loaded_data = self.include(subnode)
                    if isinstance(loaded_data, list):
                        result.extend(loaded_data)
                    else:
                        result.append(loaded_data)
                else:
                    # Handle non-include items
                    constructed = self.construct_object(subnode, deep=deep)
                    if isinstance(constructed, list):
                        result.extend(constructed)
                    else:
                        result.append(constructed)
            return result

    IncludeLoader.add_constructor("!include", IncludeLoader.include)
    loaded_data = yaml.load(f, IncludeLoader)  # noqa: S506
    if return_included_paths:
        return loaded_data, included_files
    return loaded_data


def _help() -> str:
    try:
        return (
            f"See the configuration options below:\n\n"
            f"Config YAML options:\n{_rich_table_str(Config.to_pandas_table())}\n\n"
            f"Page YAML options:\n{_rich_table_str(Page.to_pandas_table())}\n\n"
            f"Button YAML options:\n{_rich_table_str(Button.to_pandas_table())}\n\n"
        )
    except ModuleNotFoundError:
        return ""


def _get_signal_handler(deck: StreamDeck) -> Callable[[int, FrameType | None], None]:
    def handler(signum: int, frame: FrameType | None) -> None:  # noqa: ARG001
        console.log(f"Signal caught: {signum=}")
        deck.reset()
        deck.close()
        console.log(f"Closed deck connection {deck=}")
        sys.exit(0)

    return handler


def main() -> None:
    """Start the Stream Deck integration."""
    import argparse
    import os

    from dotenv import load_dotenv

    load_dotenv()

    # Get the system default encoding
    system_encoding = locale.getpreferredencoding()
    yaml_encoding = os.getenv("YAML_ENCODING", system_encoding)

    parser = argparse.ArgumentParser(
        epilog=_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default=os.environ.get("HASS_HOST", "localhost"))
    parser.add_argument("--token", default=os.environ.get("HASS_TOKEN"))
    parser.add_argument(
        "--config",
        default=os.environ.get("STREAMDECK_CONFIG", DEFAULT_CONFIG),
        type=Path,
    )
    parser.add_argument(
        "--yaml-encoding",
        default=yaml_encoding,
        help=f"Specify encoding for YAML files (default is system encoding or from environment variable YAML_ENCODING (default: {yaml_encoding})",
    )
    parser.add_argument(
        "--protocol",
        default=os.environ.get("WEBSOCKET_PROTOCOL", "wss"),
        choices=["wss", "ws"],
    )
    parser.add_argument(
        "--connection-retry-attempts",
        type=int,
        default=int(os.getenv("CONNECTION_RETRY_ATTEMPTS", "0")),
        help="Maximum number of connection retry attempts (-1 for infinite)",
    )
    parser.add_argument(
        "--connection-retry-delay",
        type=float,
        default=float(os.getenv("CONNECTION_RETRY_DELAY", "0")),
        help="Delay between connection retry attempts in seconds",
    )
    parser.add_argument(
        "--allow-weaker-ssl",
        action="store_true",
        help="Allow less secure SSL (security level 1) for compatibility with slower hardware (e.g., RPi Zero).",
    )
    args = parser.parse_args()
    if os.getenv("ALLOW_WEAKER_SSL", "").lower().startswith(("y", "t", "1")):
        args.allow_weaker_ssl = True
    console.log(f"Using version {__version__} of the Home Assistant Stream Deck.")
    console.log(
        f"Starting Stream Deck integration with {args.host=}, {args.config=}, {args.protocol=}, {args.allow_weaker_ssl=}",
    )
    config = Config.load(args.config, yaml_encoding=args.yaml_encoding)

    deck = get_deck()
    handler = _get_signal_handler(deck)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    asyncio.run(
        run(
            deck=deck,
            host=args.host,
            token=args.token,
            protocol=args.protocol,
            config=config,
            retry_attempts=args.connection_retry_attempts,
            retry_delay=args.connection_retry_delay,
            allow_weaker_ssl=args.allow_weaker_ssl,
        ),
    )


if __name__ == "__main__":
    main()
