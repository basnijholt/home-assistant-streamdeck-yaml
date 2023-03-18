"""Test Home Assistant Stream Deck YAML."""

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
TEST_STATE_FILENAME = ROOT / "tests" / "state.json"
IS_CONNECTED_TO_HOMEASSISTANT = True

sd = importlib.import_module("home-assistant-streamdeck-yaml")


def test_named_to_hex() -> None:
    """Test named to hex conversion."""
    assert sd._named_to_hex("red") == "#ff0000"
    assert sd._named_to_hex("#ff0000") == "#ff0000"


def test_example_config_browsing_pages() -> None:
    """Test example config browsing pages."""
    config = sd.read_config(sd.DEFAULT_CONFIG)
    assert isinstance(config, sd.Config)
    assert config.current_page_index == 0
    second_page = config.next_page()
    assert isinstance(second_page, sd.Page)
    assert config.current_page_index == 1
    first_page = config.previous_page()
    assert isinstance(first_page, sd.Page)
    assert config.current_page_index == 0
    buttons_per_page = 15
    assert len(first_page.buttons) == buttons_per_page
    assert len(second_page.buttons) == buttons_per_page
    second_page = config.to_page(1)
    assert isinstance(second_page, sd.Page)
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
    async with sd.setup_ws(config["HASS_HOST"], config["HASS_TOKEN"]) as websocket:
        complete_state = await sd.get_states(websocket)
        save_and_extract_relevant_state(complete_state)
        websocket.close()


def save_and_extract_relevant_state(state: dict[str, dict[str, Any]]) -> None:
    """Save and extract relevant state."""
    config = sd.read_config(sd.DEFAULT_CONFIG)
    condensed_state = {}
    for page in config.pages:
        for button in page.buttons:
            if button.entity_id in state:
                condensed_state[button.entity_id] = state[button.entity_id]
    with TEST_STATE_FILENAME.open("w") as f:
        json.dump(condensed_state, f, indent=4)
