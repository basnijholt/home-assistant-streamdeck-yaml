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
    _download_spotify_image,
    _init_icon,
    _is_state,
    _is_state_attr,
    _keys,
    _light_page,
    _named_to_hex,
    _states,
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
BUTTONS_PER_PAGE = 15


def test_read_config() -> None:
    """Test read_config."""
    read_config(DEFAULT_CONFIG)


@pytest.fixture()
def state() -> dict[str, dict[str, Any]]:
    """State fixture."""
    with TEST_STATE_FILENAME.open("r") as f:
        return json.load(f)


@pytest.fixture()
def button_dict() -> dict[str, dict[str, Any]]:
    """Different button configurations."""
    return {
        "light": {
            "entity_id": "light.living_room_lights_z2m",
            "service": "light.toggle",
            "text": "Living room\nlights\n",
        },
        "volume_down": {
            "entity_id": "media_player.kef_ls50",
            "service": "media_player.volume_set",
            "service_data": {
                "volume_level": '{{ max(state_attr("media_player.kef_ls50", "volume_level") - 0.05, 0) }}',
                "entity_id": "media_player.kef_ls50",
            },
            "text": '{{ (100 * state_attr("media_player.kef_ls50", "volume_level")) | int }}%',
            "text_size": 16,
            "icon_mdi": "volume-minus",
        },
        "script_with_text": {
            "service": "script.reset_adaptive_lighting",
            "text": "Reset\nadaptive\nlighting\n",
        },
        "script_with_text_and_icon": {
            "service": "script.turn_off_everything",
            "text": "ALL OFF",
            "icon": "night_sky.png",
        },
        "input_select_with_template": {
            "entity_id": "input_select.sleep_mode",
            "service": "input_select.select_previous",
            "text": 'Sleep {{ states("input_select.sleep_mode") }}',
            "icon_mdi": "power-sleep",
        },
        "script_with_icon": {
            "service": "script.start_fireplace_netflix",
            "icon": "fireplace.png",
        },
        "spotify_playlist": {
            "service": "script.start_spotify",
            "service_data": {
                "playlist": "37i9dQZF1DXaRycgyh6kXP",
                "source": "KEF LS50",
            },
            "icon": "spotify:playlist/37i9dQZF1DXaRycgyh6kXP",
        },
        "special_empty": {"special_type": "empty"},
        "special_goto_0": {"special_type": "go-to-page", "special_type_data": 0},
        "special_goto_home": {
            "special_type": "go-to-page",
            "special_type_data": "Home",
        },
        "special_prev_page": {"special_type": "previous-page"},
        "special_next_page": {"special_type": "next-page"},
    }


@pytest.fixture()
def buttons(button_dict: dict[str, dict[str, Any]]) -> list[Button]:
    """List of `Button`s."""
    button_order = [
        "light",
        "volume_down",
        "script_with_text",
        "script_with_text_and_icon",
        "input_select_with_template",
        "script_with_icon",
        "spotify_playlist",
        "special_empty",
        "special_empty",
        "special_empty",
        "special_empty",
        "special_goto_0",
        "special_goto_home",
        "special_prev_page",
        "special_next_page",
    ]

    assert len(button_order) == BUTTONS_PER_PAGE
    return [Button(**button_dict[key]) for key in button_order]


@pytest.fixture()
def config(buttons: list[Button]) -> Config:
    """Config fixture."""
    page_1 = Page(buttons=buttons, name="Home")
    page_2 = Page(buttons=buttons[::-1], name="Second")
    return Config(pages=[page_1, page_2])


def test_named_to_hex() -> None:
    """Test named to hex conversion."""
    assert _named_to_hex("red") == "#ff0000"
    assert _named_to_hex("#ff0000") == "#ff0000"


def test_example_config_browsing_pages(config: Config) -> None:
    """Test example config browsing pages."""
    assert isinstance(config, Config)
    assert config.current_page_index == 0
    second_page = config.next_page()
    assert isinstance(second_page, Page)
    assert config.current_page_index == 1
    first_page = config.previous_page()
    assert isinstance(first_page, Page)
    assert config.current_page_index == 0
    assert len(first_page.buttons) == BUTTONS_PER_PAGE
    assert len(second_page.buttons) == BUTTONS_PER_PAGE
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
async def test_websocket_connection(buttons: list[Button]) -> None:
    """Test websocket connection."""
    config = dotenv_values(ROOT / ".env")
    async with setup_ws(config["HASS_HOST"], config["HASS_TOKEN"]) as websocket:
        complete_state = await get_states(websocket)
        save_and_extract_relevant_state(buttons, complete_state)
        websocket.close()


def save_and_extract_relevant_state(
    buttons: list[Button],
    state: dict[str, dict[str, Any]],
) -> None:
    """Save and extract relevant state."""
    condensed_state = {}
    for button in buttons:
        if button.entity_id in state:
            condensed_state[button.entity_id] = state[button.entity_id]
    with TEST_STATE_FILENAME.open("w") as f:
        json.dump(condensed_state, f, indent=4)


def test_buttons(buttons: list[Button], state: dict[str, dict[str, Any]]) -> None:
    """Test buttons."""
    page = Page(name="Home", buttons=buttons)
    config = Config(pages=[page])
    first_page = config.to_page(0)
    rendered_buttons = [button.rendered_button(state) for button in first_page.buttons]

    b = rendered_buttons[0]  # LIGHT
    assert b.domain == "light"
    assert b.render_icon() is None

    b = rendered_buttons[1]  # VOLUME_DOWN
    assert b.entity_id in state
    entity_state = state[b.entity_id]
    attrs = entity_state["attributes"]
    volume = attrs["volume_level"]
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

    b = rendered_buttons[0]  # LIGHT
    assert b.entity_id is not None
    assert _keys(b.entity_id, page.buttons) == [0]


def test_validate_special_type(button_dict: dict[str, dict[str, Any]]) -> None:
    """Test validation of special type buttons."""
    with pytest.raises(ValidationError):
        Button(**button_dict["special_next_page"], special_type_data="Yo")
    with pytest.raises(ValidationError):
        Button(**dict(button_dict["special_goto_0"], special_type_data=[]))


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

    def reset(self) -> None:
        """Mock reset."""


def test_update_key_image(config: Config, state: dict[str, dict[str, Any]]) -> None:
    """Test update_key_image with MockDeck."""
    deck = MockDeck()
    update_key_image(deck, key=0, config=config, complete_state=state)
    page = config.current_page()
    assert config.current_page_index == 0
    for key, _ in enumerate(page.buttons):
        update_key_image(deck, key=key, config=config, complete_state=state)

    key_empty = next(
        (i for i, b in enumerate(page.buttons) if b.special_type == "empty"),
    )
    assert key_empty is not None


def test_download_spotify_image() -> None:
    """Test download_spotify_image."""
    icon = "playlist/37i9dQZF1DXaRycgyh6kXP"
    filename = _to_filename(icon, ".jpeg")
    _download_spotify_image(icon, filename)
    assert filename.exists()


def test_is_state_attr(state: dict[str, dict[str, Any]]) -> None:
    """Test is_state_attr jinja template function."""
    for entity_id, e_state in state.items():
        if attrs := e_state.get("attributes"):
            for attr, value in attrs.items():
                _is_state_attr(
                    entity_id=entity_id,
                    attr=attr,
                    value=value,
                    complete_state=state,
                )


def test_states(state: dict[str, dict[str, Any]]) -> None:
    """Test states jinja template function."""
    for entity_id, e_state in state.items():
        if current_state := e_state.get("state"):
            assert _states(entity_id=entity_id, complete_state=state) == current_state

    assert _states(entity_id="domain.does_not_exist", complete_state=state) is None


def test_is_state(state: dict[str, dict[str, Any]]) -> None:
    """Test is_state jinja template function."""
    for entity_id, e_state in state.items():
        if current_state := e_state.get("state"):
            assert _is_state(
                entity_id=entity_id,
                state=current_state,
                complete_state=state,
            )


def test_light_page() -> None:
    """Test light page."""
    page = _light_page(entity_id="light.bedroom")
    buttons = page.buttons
    assert len(buttons) == BUTTONS_PER_PAGE
    assert buttons[0].icon_background_color is not None
