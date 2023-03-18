"""Test Home Assistant Stream Deck YAML."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values

from home_assistant_streamdeck_yaml import (
    DEFAULT_CONFIG,
    Config,
    Page,
    _named_to_hex,
    get_states,
    read_config,
    setup_ws,
)

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
TEST_STATE_FILENAME = ROOT / "tests" / "state.json"
IS_CONNECTED_TO_HOMEASSISTANT = False


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


@pytest.mark.skipif(
    not IS_CONNECTED_TO_HOMEASSISTANT,
    reason="Not connected to Home Assistant",
)
@pytest.mark.asyncio()
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


def test_buttons() -> None:
    """Test buttons."""
    with TEST_STATE_FILENAME.open("r") as f:
        state = json.load(f)

    buttons = [
        {
            "entity_id": "light.living_room_lights_z2m",
            "service": "light.toggle",
            "text": "Living room\nlights\n",
        },
        {
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
        {
            "service": "script.reset_adaptive_lighting",
            "text": "Reset\nadaptive\nlighting\n",
        },
        {
            "service": "script.turn_off_everything",
            "text": "ALL OFF",
            "icon": "night_sky.png",
        },
        {
            "entity_id": "input_select.sleep_mode",
            "service": "input_select.select_previous",
            "text": 'Sleep {{ states("input_select.sleep_mode") }}',
            "icon_mdi": "power-sleep",
        },
        {"service": "script.start_fireplace_netflix", "icon": "fireplace.png"},
        {
            "service": "script.start_spotify",
            "service_data": {
                "playlist": "37i9dQZF1DXaRycgyh6kXP",
                "source": "KEF LS50",
            },
            "icon": "spotify:playlist/37i9dQZF1DXaRycgyh6kXP",
        },
        {"special_type": "empty"},
        {"special_type": "empty"},
        {"special_type": "empty"},
        {"special_type": "empty"},
        {"special_type": "go-to-page", "special_type_data": 0},
        {"special_type": "go-to-page", "special_type_data": "Home"},
        {"special_type": "previous-page"},
        {"special_type": "next-page"},
    ]
    buttons_per_page = 15
    assert len(buttons) == buttons_per_page
    page = Page(name="Home", buttons=buttons)
    config = Config(pages=[page])
    first_page = config.to_page(0)
    for button in first_page.buttons:
        button.rendered_button(state)
