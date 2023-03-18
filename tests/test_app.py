"""Test Home Assistant Stream Deck YAML."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError
from StreamDeck.Devices.StreamDeckOriginal import StreamDeckOriginal

from home_assistant_streamdeck_yaml import (
    DEFAULT_CONFIG,
    Button,
    Config,
    Page,
    _download_and_save_mdi,
    _init_icon,
    _keys,
    _named_to_hex,
    _to_filename,
    get_states,
    read_config,
    setup_ws,
    update_key_image,
)

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
TEST_STATE_FILENAME = ROOT / "tests" / "state.json"
IS_CONNECTED_TO_HOMEASSISTANT = False


def load_defaults() -> tuple[Config, dict[str, dict[str, Any]]]:
    """Default config and state."""
    with TEST_STATE_FILENAME.open("r") as f:
        state = json.load(f)
    config = read_config(DEFAULT_CONFIG)
    return config, state


def test_named_to_hex() -> None:
    """Test named to hex conversion."""
    assert _named_to_hex("red") == "#ff0000"
    assert _named_to_hex("#ff0000") == "#ff0000"


def test_example_config_browsing_pages() -> None:
    """Test example config browsing pages."""
    config = read_config(DEFAULT_CONFIG)
    assert isinstance(config, Config)
    assert config.current_page_index == 0
    second_page = config.next_page()
    assert isinstance(second_page, Page)
    assert config.current_page_index == 1
    first_page = config.previous_page()
    assert isinstance(first_page, Page)
    assert config.current_page_index == 0
    buttons_per_page = 15
    assert len(first_page.buttons) == buttons_per_page
    assert len(second_page.buttons) == buttons_per_page
    second_page = config.to_page(1)
    assert isinstance(second_page, Page)
    assert config.current_page_index == 1
    first_page = config.to_page(first_page.name)
    assert config.current_page_index == 0
    assert config.button(0) == first_page.buttons[0]


@pytest.mark.skipif(
    not IS_CONNECTED_TO_HOMEASSISTANT,
    reason="Not connected to Home Assistant",
)
async def test_websocket_connection() -> None:
    """Test websocket connection."""
    config = dotenv_values(ROOT / ".env")
    async with setup_ws(config["HASS_HOST"], config["HASS_TOKEN"]) as websocket:
        complete_state = await get_states(websocket)
        save_and_extract_relevant_state(complete_state)
        websocket.close()


def save_and_extract_relevant_state(state: dict[str, dict[str, Any]]) -> None:
    """Save and extract relevant state."""
    config = read_config(DEFAULT_CONFIG)
    condensed_state = {}
    for page in config.pages:
        for button in page.buttons:
            if button.entity_id in state:
                condensed_state[button.entity_id] = state[button.entity_id]
    with TEST_STATE_FILENAME.open("w") as f:
        json.dump(condensed_state, f, indent=4)


LIGHT = {
    "entity_id": "light.living_room_lights_z2m",
    "service": "light.toggle",
    "text": "Living room\nlights\n",
}
VOLUME_DOWN = {
    "entity_id": "media_player.kef_ls50",
    "service": "media_player.volume_set",
    "service_data": {
        "volume_level": '{{ max(state_attr("media_player.kef_ls50", "volume_level") - 0.05, 0) }}',
        "entity_id": "media_player.kef_ls50",
    },
    "text": '{{ (100 * state_attr("media_player.kef_ls50", "volume_level")) | int }}%',
    "text_size": 16,
    "icon_mdi": "volume-minus",
}
SCRIPT_WITH_TEXT = {
    "service": "script.reset_adaptive_lighting",
    "text": "Reset\nadaptive\nlighting\n",
}
SCRIPT_WITH_TEXT_AND_ICON = {
    "service": "script.turn_off_everything",
    "text": "ALL OFF",
    "icon": "night_sky.png",
}
INPUT_SELECT_WITH_TEMPLATE = {
    "entity_id": "input_select.sleep_mode",
    "service": "input_select.select_previous",
    "text": 'Sleep {{ states("input_select.sleep_mode") }}',
    "icon_mdi": "power-sleep",
}

SCRIPT_WITH_ICON = {
    "service": "script.start_fireplace_netflix",
    "icon": "fireplace.png",
}
SPOTIFY_PLAYLIST = {
    "service": "script.start_spotify",
    "service_data": {
        "playlist": "37i9dQZF1DXaRycgyh6kXP",
        "source": "KEF LS50",
    },
    "icon": "spotify:playlist/37i9dQZF1DXaRycgyh6kXP",
}
SPECIAL_EMPTY = {"special_type": "empty"}
SPECIAL_GOTO_0 = {"special_type": "go-to-page", "special_type_data": 0}
SPECIAL_GOTO_HOME = {"special_type": "go-to-page", "special_type_data": "Home"}
SPECIAL_PREV_PAGE = {"special_type": "previous-page"}
SPECIAL_NEXT_PAGE = {"special_type": "next-page"}
BUTTONS = [
    LIGHT,
    VOLUME_DOWN,
    SCRIPT_WITH_TEXT,
    SCRIPT_WITH_TEXT_AND_ICON,
    INPUT_SELECT_WITH_TEMPLATE,
    SCRIPT_WITH_ICON,
    SPOTIFY_PLAYLIST,
    SPECIAL_EMPTY,
    SPECIAL_EMPTY,
    SPECIAL_EMPTY,
    SPECIAL_EMPTY,
    SPECIAL_GOTO_0,
    SPECIAL_GOTO_HOME,
    SPECIAL_PREV_PAGE,
    SPECIAL_NEXT_PAGE,
]


def test_buttons() -> None:
    """Test buttons."""
    with TEST_STATE_FILENAME.open("r") as f:
        state = json.load(f)
    buttons = BUTTONS
    buttons_per_page = 15
    assert len(buttons) == buttons_per_page
    page = Page(name="Home", buttons=buttons)
    config = Config(pages=[page])
    first_page = config.to_page(0)
    rendered_buttons = [button.rendered_button(state) for button in first_page.buttons]

    b = rendered_buttons[0]  # LIGHT
    assert b.domain == "light"
    assert b.render_icon() is None

    b = rendered_buttons[1]  # VOLUME_DOWN
    volume = state[b.entity_id]["attributes"]["volume_level"]
    assert b.text == f"{int(100 * volume)}%"
    assert b.service_data is not None
    assert float(b.service_data["volume_level"]) == volume - 0.05

    b = rendered_buttons[3]  # SCRIPT_WITH_TEXT_AND_ICON
    assert b.render_icon() == b.icon

    b = rendered_buttons[4]  # INPUT_SELECT_WITH_TEMPLATE
    assert b.text == "Sleep off"

    b = rendered_buttons[6]  # SPOTIFY_PLAYLIST
    icon = b.render_icon()
    assert b.icon is not None
    filename = _to_filename(b.icon, ".jpeg")
    assert icon == str(filename.absolute())
    assert Path(filename).exists()

    b = rendered_buttons[14]  # SPECIAL_NEXT_PAGE
    assert b.domain is None

    assert _keys(LIGHT["entity_id"], page.buttons) == [0]


def test_validate_special_type() -> None:
    """Test validation of special type buttons."""
    with pytest.raises(ValidationError):
        Button(**SPECIAL_NEXT_PAGE, special_type_data="Yo")
    with pytest.raises(ValidationError):
        Button(**dict(SPECIAL_GOTO_0, special_type_data=[]))


def test_download_and_save_mdi() -> None:
    """Test whether function downloads MDI correctly."""
    # might be cached
    filename = _download_and_save_mdi("phone")
    assert filename.exists()

    # is cached
    filename = _download_and_save_mdi("phone")
    assert filename.exists()
    filename.unlink()

    # downloads again
    filename = _download_and_save_mdi("phone")
    assert filename.exists()
    filename.unlink()


def test_init_icon() -> None:
    """Test init icon."""
    _init_icon(icon_filename="xbox.png")
    _init_icon(icon_filename="xbox.png", icon_convert_to_grayscale=True)
    _init_icon(
        icon_mdi="phone",
        icon_mdi_margin=1,
        icon_mdi_color="#ffbb00",
        size=(100, 100),
    )
    _init_icon(size=(100, 100))


class MockDeck:
    """Mocks a StreamDeck."""

    KEY_PIXEL_WIDTH = StreamDeckOriginal.KEY_PIXEL_WIDTH
    KEY_PIXEL_HEIGHT = StreamDeckOriginal.KEY_PIXEL_HEIGHT
    KEY_FLIP = StreamDeckOriginal.KEY_FLIP
    KEY_ROTATION = StreamDeckOriginal.KEY_ROTATION
    KEY_IMAGE_FORMAT = StreamDeckOriginal.KEY_IMAGE_FORMAT

    def key_image_format(self) -> dict[str, Any]:
        """Same as original device."""
        return {
            "size": (self.KEY_PIXEL_WIDTH, self.KEY_PIXEL_HEIGHT),
            "format": self.KEY_IMAGE_FORMAT,
            "flip": self.KEY_FLIP,
            "rotation": self.KEY_ROTATION,
        }

    def set_key_image(self, key: int, image: memoryview) -> None:
        """Mock set_key_image."""

    def __enter__(self) -> MockDeck:
        """Mock context manager."""
        return self

    def __exit__(self, *exc: Any) -> bool:  # type: ignore[exit-return]
        """Mock context manager."""
        return False


def test_update_key_image() -> None:
    """Test update_key_image with MockDeck."""
    deck = MockDeck()
    config, state = load_defaults()
    update_key_image(deck, key=0, config=config, complete_state=state)
