"""Test App Home_assistant_streamdeck_yaml for Streamdeck plus."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from unittest.mock import Mock

import pytest
import websockets
from PIL import Image
from StreamDeck.Devices.StreamDeck import DialEventType
from StreamDeck.Devices.StreamDeckPlus import StreamDeckPlus

from home_assistant_streamdeck_yaml import (
    Button,
    Config,
    Dial,
    DialPushConfig,
    DialTurnConfig,
    Page,
    StateDict,
    TouchscreenEventType,
    TurnProperties,
    _on_dial_event_callback,
    _on_touchscreen_event_callback,
    _update_state,
    safe_load_yaml,
    update_dial_lcd,
)

ROOT = Path(__file__).parent.parent
TEST_STATE_FILENAME = ROOT / "tests" / "state_plus.json"


# TESTS FOR STREAM DECK PLUS
@pytest.fixture
def websocket_mock() -> Mock:
    """Mock websocket client protocol."""
    return Mock(spec=websockets.WebSocketClientProtocol)


@pytest.fixture
def state() -> dict[str, dict[str, Any]]:
    """State fixture."""
    with TEST_STATE_FILENAME.open("r") as f:
        return json.load(f)


@pytest.fixture
def mock_deck_plus() -> Mock:
    """Mocks a StreamDeck Plus."""
    deck_mock = Mock(spec=StreamDeckPlus)

    deck_mock.KEY_PIXEL_WIDTH = StreamDeckPlus.KEY_PIXEL_WIDTH
    deck_mock.KEY_PIXEL_HEIGHT = StreamDeckPlus.KEY_PIXEL_HEIGHT
    deck_mock.KEY_FLIP = StreamDeckPlus.KEY_FLIP
    deck_mock.KEY_ROTATION = StreamDeckPlus.KEY_ROTATION
    deck_mock.KEY_IMAGE_FORMAT = StreamDeckPlus.KEY_IMAGE_FORMAT

    deck_mock.key_image_format.return_value = {
        "size": (deck_mock.KEY_PIXEL_WIDTH, deck_mock.KEY_PIXEL_HEIGHT),
        "format": deck_mock.KEY_IMAGE_FORMAT,
        "flip": deck_mock.KEY_FLIP,
        "rotation": deck_mock.KEY_ROTATION,
    }

    deck_mock.TOUCHSCREEN_PIXEL_WIDTH = StreamDeckPlus.TOUCHSCREEN_PIXEL_WIDTH
    deck_mock.TOUCHSCREEN_PIXEL_HEIGHT = StreamDeckPlus.TOUCHSCREEN_PIXEL_HEIGHT
    deck_mock.TOUCHSCREEN_IMAGE_FORMAT = StreamDeckPlus.TOUCHSCREEN_IMAGE_FORMAT
    deck_mock.TOUCHSCREEN_FLIP = StreamDeckPlus.TOUCHSCREEN_FLIP
    deck_mock.TOUCHSCREEN_ROTATION = StreamDeckPlus.TOUCHSCREEN_ROTATION

    deck_mock.touchscreen_image_format.return_value = {
        "size": (deck_mock.TOUCHSCREEN_PIXEL_WIDTH, deck_mock.TOUCHSCREEN_PIXEL_HEIGHT),
        "format": deck_mock.TOUCHSCREEN_IMAGE_FORMAT,
        "flip": deck_mock.TOUCHSCREEN_FLIP,
        "rotation": deck_mock.TOUCHSCREEN_ROTATION,
    }

    deck_mock.key_count.return_value = 8
    deck_mock.dial_count.return_value = 4

    deck_mock.__enter__ = Mock(return_value=deck_mock)
    deck_mock.__exit__ = Mock(return_value=False)

    return deck_mock


@pytest.fixture
def dial_yaml_config() -> str:
    """Returns YAML configuration for StreamDeck Plus dials."""
    yaml_file = Path(__file__).parent / "dial_config.yaml"
    with yaml_file.open("r") as f:
        return f.read()


@pytest.fixture
def dials(dial_yaml_config: str) -> list[Dial]:
    """Order of dials for page."""
    dial_configs = safe_load_yaml(dial_yaml_config, return_included_paths=False)
    assert isinstance(dial_configs, list)
    return [Dial(**config) for config in dial_configs]


@pytest.fixture
def state_change_msg() -> dict[str, Any]:
    """Message for state change."""
    return {
        "type": "event",
        "event": {
            "event_type": "state_changed",
            "data": {
                "entity_id": "input_number.streamdeck",
                "old_state": {
                    "entity_id": "input_number.streamdeck",
                    "state": "0",
                    "attributes": {
                        "initial": None,
                        "editable": True,
                        "min": 0,
                        "max": 100,
                        "step": 1,
                        "mode": "slider",
                        "friendly_name": "StreamDeck",
                    },
                    "last_changed": "2024-04-03T14:05:05.526890+00:00",
                    "last_updated": "2024-04-03T14:05:05.526890+00:00",
                },
                "new_state": {
                    "entity_id": "input_number.streamdeck",
                    "state": 1,
                    "attributes": {
                        "initial": None,
                        "editable": True,
                        "min": 0,
                        "max": 200,
                        "step": 5,
                        "mode": "slider",
                        "friendly_name": "StreamDeck",
                    },
                    "last_changed": "2024-04-03T14:05:05.526890+00:00",
                    "last_updated": "2024-04-03T14:05:05.526890+00:00",
                },
            },
        },
    }


def test_dials(dials: list[Dial], state: dict[str, dict[str, Any]]) -> None:
    """Tests setup of pages with dials and rendering of image."""
    page = Page(name="Home", dials=dials)
    config = Config(pages=[page])
    first_page = config.to_page(0)

    key = 0
    # change number value TURN event
    d = first_page.dials[key]
    turn_state = 50.0
    d.set_turn_state(turn_state)
    # check domain type
    assert d.entity_id is not None
    # check image rendering
    d = d.rendered_template_dial(state)
    icon = d.render_lcd_image(state, key, (200, 100))
    assert isinstance(icon, Image.Image)
    # check dial_value Jinja rendering
    assert d.turn is not None
    assert d.turn.service_data is not None
    assert isinstance(float(d.turn.service_data["value"]), float)
    assert float(d.turn.service_data["value"]) == turn_state  # Verify rendered state

    d = first_page.dials[1]
    assert d.push is not None
    assert d.push.service_data is not None

    key = 2
    d = first_page.dials[key]
    # check icon rendering for mdi icons
    d = d.rendered_template_dial(state)
    icon = d.render_lcd_image(state, key, (200, 100))
    assert isinstance(icon, Image.Image)
    assert d.text is not None
    assert d.turn is not None

    key = 3
    d = first_page.dials[key]
    d = d.rendered_template_dial(state)
    icon = d.render_lcd_image(state, key, (200, 100))
    assert isinstance(icon, Image.Image)
    assert d.turn is not None


async def test_streamdeck_plus(
    mock_deck_plus: Mock,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
    dials: list[Dial],
    state_change_msg: dict[str, dict[str, Any]],
) -> None:
    """Tests dials, buttons and pages on streamdeck plus with state change."""
    home = Page(
        name="home",
        buttons=[
            Button(special_type="go-to-page", special_type_data="page_1"),
            Button(special_type="go-to-page", special_type_data="page_anon"),
        ],
    )

    page_1 = Page(
        name="page_1",
        dials=dials,
    )

    page_anon = Page(name="page_anon", dials=dials)
    config = Config(pages=[home, page_1], anonymous_pages=[page_anon])
    assert config._current_page_index == 0
    assert config.to_page("page_1") == page_1
    assert config.current_page() == page_1

    dial = config.dial(0)
    assert dial is not None
    dial = dial.rendered_template_dial(state)
    assert dial.entity_id == "input_number.streamdeck"
    assert dial.turn is not None
    assert dial.turn.service == "input_number.set_value"

    # set TurnProperties as a TurnProperties object
    dial.turn.properties = TurnProperties(
        min=0,
        max=100,
        step=1,
        state=0.0,
        service_attribute="value",
    )

    # gets attributes of dial and checks if state is correct
    update_dial_lcd(mock_deck_plus, 0, config, state)
    dial_val = {
        "min": dial.turn.properties.min,
        "max": dial.turn.properties.max,
        "step": dial.turn.properties.step,
        "state": dial.turn.properties.state,
    }
    assert isinstance(dial_val, dict)
    dial_state = dial_val["state"]
    assert dial_state is not None
    # Fires dial event and increments state by 1

    dial_event = _on_dial_event_callback(websocket_mock, state, config)
    await dial_event(mock_deck_plus, 0, DialEventType.TURN, 1)
    # Test update state
    _update_state(state, state_change_msg, config, mock_deck_plus)
    # Check if state changed for input_number
    assert float(state["input_number.streamdeck"]["state"]) == dial_state + 1

    # test update attributes
    turn_max_property = 200
    dial.turn.properties.max = turn_max_property
    turn_step_property = 5
    dial.turn.properties.step = turn_step_property
    updated_attributes = {
        "min": dial.turn.properties.min,
        "max": dial.turn.properties.max,
        "step": dial.turn.properties.step,
    }
    assert updated_attributes["max"] == turn_max_property
    assert updated_attributes["step"] == turn_step_property
    assert updated_attributes["min"] == 0


async def test_touchscreen(
    mock_deck_plus: Mock,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
    dials: list[Dial],
) -> None:
    """Test touchscreen events for dial."""
    home = Page(
        name="home",
        buttons=[
            Button(special_type="go-to-page", special_type_data="page_1"),
            Button(special_type="go-to-page", special_type_data="page_anon"),
        ],
    )

    page_1 = Page(
        name="page_1",
        dials=dials,
    )

    page_anon = Page(name="page_anon", dials=dials)
    config = Config(pages=[home, page_1], anonymous_pages=[page_anon])
    assert config._current_page_index == 0
    assert config.current_page() == home

    # Check if you can change page using Touchscreen.
    touch_event = _on_touchscreen_event_callback(websocket_mock, state, config)
    await touch_event(
        mock_deck_plus,
        TouchscreenEventType.DRAG,
        {
            "x": 0,
            "y": 0,
            "x_out": 100,
            "y_out": 0,
        },
    )

    assert config.current_page() == page_1
    # Check if you can set max using touchscreen.
    dial = config.dial(0)
    assert dial is not None
    assert dial.turn is not None
    dial.turn.properties = Mock()
    dial.turn.properties.min = 0
    dial.turn.properties.max = 100
    dial.turn.properties.step = 1
    dial.turn.properties.state = 0.0
    dial.turn.properties.service_attribute = "value"

    touch_event = _on_touchscreen_event_callback(websocket_mock, state, config)
    await touch_event(
        mock_deck_plus,
        TouchscreenEventType.LONG,
        {
            "x": 100,
            "y": 50,
        },
    )
    attributes = {
        "min": dial.turn.properties.min,
        "max": dial.turn.properties.max,
        "state": dial.turn.properties.state,
    }
    assert attributes["state"] == attributes["max"]

    # Check if you can set min using touchscreen.
    touch_event = _on_touchscreen_event_callback(websocket_mock, state, config)
    await touch_event(
        mock_deck_plus,
        TouchscreenEventType.SHORT,
        {
            "x": 100,
            "y": 50,
        },
    )
    attributes = {
        "min": dial.turn.properties.min,
        "max": dial.turn.properties.max,
        "state": dial.turn.properties.state,
    }
    assert attributes["state"] == attributes["min"]

    # Check if disabling touchscreen events works
    dial = config.dial(3)
    assert dial is not None
    assert dial.turn is not None
    assert dial.allow_touchscreen_events is not True
    dial.turn.properties = Mock()
    dial.turn.properties.min = 0
    dial.turn.properties.max = 100
    dial.turn.properties.state = 50.0
    dial.turn.properties.service_attribute = "value"

    touch_event = _on_touchscreen_event_callback(websocket_mock, state, config)
    await touch_event(
        mock_deck_plus,
        TouchscreenEventType.SHORT,
        {
            "x": 300,
            "y": 50,
        },
    )
    attributes = {
        "min": dial.turn.properties.min,
        "max": dial.turn.properties.max,
        "state": dial.turn.properties.state,
    }
    assert attributes["state"] is not attributes["min"]


async def test_dial_updates_with_state(
    state: StateDict,
) -> None:
    """Test that the dial updates properly with Home Assistant state changes."""
    # Setup configuration with a page containing dials
    entity_id = "input_number.streamdeck"
    start_state = 50.0
    end_state = 100.0
    dial = Dial(
        entity_id=entity_id,
        turn=DialTurnConfig(
            properties=TurnProperties(
                min=0,
                max=100,
                step=1,
                state=start_state,
            ),
        ),
    )
    assert dial.turn is not None
    assert dial.turn.properties.state == start_state
    state[entity_id]["state"] = end_state
    dial.sync_with_ha_state(state)
    assert dial.turn.properties.state == end_state


async def test_dial_updates_with_state_change(
    mock_deck_plus: Mock,
    state: StateDict,
    state_change_msg: dict[str, dict[str, Any]],
) -> None:
    """Test that the dial updates properly with Home Assistant state changes."""
    # Setup configuration with a page containing dials
    start_state = 50.0
    dial_config = Dial(
        entity_id="input_number.streamdeck",
        turn=DialTurnConfig(
            properties=TurnProperties(
                min=0,
                max=100,
                step=1,
                state=start_state,
            ),
        ),
    )
    page = Page(name="Home", dials=[dial_config])
    config = Config(pages=[page])
    assert config._current_page_index == 0
    assert config.current_page() == page

    # Get the first dial and set its properties
    dial = config.dial(0)
    assert dial is not None
    dial = dial.rendered_template_dial(state)
    assert dial is not None
    assert dial.turn is not None
    assert dial.entity_id == "input_number.streamdeck"

    # Verify initial state
    assert dial.turn.properties.state == start_state

    # Simulate a state change from Home Assistant
    print(
        f"Simulating state change from Home Assistant \n{state=},\n state_change_msg={state_change_msg})",
    )
    _update_state(state, state_change_msg, config, mock_deck_plus)
    print(f"State after update: {state=}")
    # Verify that the dial's state has been updated
    updated_state = float(state["input_number.streamdeck"]["state"])
    dial = config.dial(0)
    assert dial is not None
    assert dial.turn is not None
    assert dial.turn.properties.state == updated_state
    assert updated_state == 1.0  # Based on the `state_change_msg` fixture


async def test_restart_timer() -> None:
    """Test the delay."""
    delay = 0.1
    delay_delta = 0.02
    assert delay > delay_delta
    less_than_delay = max(0, delay - delay_delta)
    turn = DialTurnConfig(delay=0.1)
    assert not turn.is_sleeping()
    assert turn.start_or_restart_timer()
    await asyncio.sleep(0)  # TODO: figure out why this is needed
    assert turn._timer is not None
    assert turn._timer.is_sleeping
    assert turn.is_sleeping()
    await asyncio.sleep(less_than_delay)  # Sleep for less than the delay
    assert turn.start_or_restart_timer()  # Restart the timer
    await asyncio.sleep(less_than_delay)  # Sleep for less than the delay
    assert turn.is_sleeping()
    await asyncio.sleep(delay_delta)
    assert not turn.is_sleeping()


def test_legacy_dial_conversion() -> None:  # noqa: PLR0915
    """Test conversion of LegacyDial configurations to Dial instances."""
    # Test case 1: Both TURN and PUSH configs, TURN has most attributes
    legacy_dials = [
        {
            "entity_id": "light.living_room",
            "dial_event_type": "DialEventType.TURN",
            "text": "Brightness",
            "icon": "brightness.png",
            "text_color": "#FFFFFF",
            "icon_mdi": "lightbulb",
            "state_attribute": "brightness",
            "attributes": {"min": 0.0, "max": 100.0, "step": 5.0},
            "service": "light.turn_on",
            "service_data": {"entity_id": "light.living_room", "brightness": 50},
        },
        {
            "entity_id": "light.living_room",
            "dial_event_type": "DialEventType.PUSH",
            "text": "Toggle",  # Should be ignored
            "icon": "toggle.png",  # Should be ignored
            "service": "light.toggle",
            "service_data": {"entity_id": "light.living_room"},
        },
    ]
    dials = Dial.from_legacy_dials(legacy_dials)
    assert len(dials) == 1, "Expected one consolidated Dial instance"
    dial = dials[0]
    assert dial.entity_id == "light.living_room"
    assert dial.text == "Brightness", "Expected TURN text to take precedence"
    assert dial.icon == "brightness.png", "Expected TURN icon to take precedence"
    assert dial.text_color == "#FFFFFF"
    assert dial.icon_mdi == "lightbulb"
    assert isinstance(dial.turn, DialTurnConfig)
    assert dial.turn.properties.service_attribute == "brightness"
    assert dial.turn.properties.min == 0.0
    assert dial.turn.properties.max == 100.0  # noqa: PLR2004
    assert dial.turn.properties.step == 5.0  # noqa: PLR2004
    assert dial.turn.service == "light.turn_on"
    assert dial.turn.service_data == {"entity_id": "light.living_room", "brightness": 50}
    assert isinstance(dial.push, DialPushConfig)
    assert dial.push.service == "light.toggle"
    assert dial.push.service_data == {"entity_id": "light.living_room"}

    # Test case 2: Only PUSH config, attributes should be used
    legacy_dials = [
        {
            "entity_id": "switch.kitchen",
            "dial_event_type": "DialEventType.PUSH",
            "text": "Toggle Switch",
            "icon": "switch.png",
            "text_color": "#000000",
            "icon_mdi": "power",
            "service": "switch.toggle",
            "service_data": {"entity_id": "switch.kitchen"},
        },
    ]
    dials = Dial.from_legacy_dials(legacy_dials)
    assert len(dials) == 1
    dial = dials[0]
    assert dial.entity_id == "switch.kitchen"
    assert dial.text == "Toggle Switch"
    assert dial.icon == "switch.png"
    assert dial.text_color == "#000000"
    assert dial.icon_mdi == "power"
    assert dial.turn is None
    assert isinstance(dial.push, DialPushConfig)
    assert dial.push.service == "switch.toggle"
    assert dial.push.service_data == {"entity_id": "switch.kitchen"}

    # Test case 3: TURN with missing attributes, PUSH provides some
    legacy_dials = [
        {
            "entity_id": "fan.bedroom",
            "dial_event_type": "DialEventType.TURN",
            "state_attribute": "speed",
            "attributes": {"min": 0.0, "max": 100.0, "step": 10.0},
            "service": "fan.set_speed",
        },
        {
            "entity_id": "fan.bedroom",
            "dial_event_type": "DialEventType.PUSH",
            "text": "Fan Toggle",
            "icon": "fan.png",
            "service": "fan.toggle",
        },
    ]
    dials = Dial.from_legacy_dials(legacy_dials)
    assert len(dials) == 1
    dial = dials[0]
    assert dial.entity_id == "fan.bedroom"
    assert dial.text == "Fan Toggle", "Expected PUSH text as fallback"
    assert dial.icon == "fan.png", "Expected PUSH icon as fallback"
    assert dial.text_color is None
    assert dial.icon_mdi is None
    assert isinstance(dial.turn, DialTurnConfig)
    assert dial.turn.properties.service_attribute == "speed"
    assert dial.turn.properties.min == 0.0
    assert dial.turn.properties.max == 100.0  # noqa: PLR2004
    assert dial.turn.properties.step == 10.0  # noqa: PLR2004
    assert dial.turn.service == "fan.set_speed"
    assert isinstance(dial.push, DialPushConfig)
    assert dial.push.service == "fan.toggle"

    # Test case 4: Multiple entity_ids
    legacy_dials = [
        {
            "entity_id": "light.living_room",
            "dial_event_type": "DialEventType.TURN",
            "text": "Brightness",
            "icon": "brightness.png",
            "state_attribute": "brightness",
            "attributes": {"min": 0.0, "max": 100.0, "step": 5.0},
        },
        {
            "entity_id": "switch.kitchen",
            "dial_event_type": "DialEventType.PUSH",
            "text": "Toggle Switch",
            "icon": "switch.png",
            "service": "switch.toggle",
        },
    ]
    dials = Dial.from_legacy_dials(legacy_dials)
    assert len(dials) == len(legacy_dials), "Expected two separate Dial instances"
    light_dial = next(d for d in dials if d.entity_id == "light.living_room")
    switch_dial = next(d for d in dials if d.entity_id == "switch.kitchen")
    assert light_dial.text == "Brightness"
    assert light_dial.icon == "brightness.png"
    assert isinstance(light_dial.turn, DialTurnConfig)
    assert light_dial.push is None
    assert switch_dial.text == "Toggle Switch"
    assert switch_dial.icon == "switch.png"
    assert switch_dial.turn is None
    assert isinstance(switch_dial.push, DialPushConfig)

    # Test case 5: Missing critical attributes
    legacy_dials = [
        {
            "entity_id": "sensor.temperature",
            "dial_event_type": "DialEventType.TURN",
            "state_attribute": "value",
            "attributes": {"min": 0.0, "max": 50.0, "step": 1.0},
        },
    ]
    dials = Dial.from_legacy_dials(legacy_dials)
    assert len(dials) == 1
    dial = dials[0]
    assert dial.entity_id == "sensor.temperature"
    assert dial.text == "", "Expected default empty text"
    assert dial.icon is None, "Expected no icon"
    assert dial.text_color is None
    assert dial.icon_mdi is None
    assert isinstance(dial.turn, DialTurnConfig)
    assert dial.turn.properties.service_attribute == "value"
    assert dial.push is None

    # Test case 6: Invalid LegacyDial entry
    legacy_dials = [
        {
            "entity_id": "invalid.device",
            "dial_event_type": "DialEventType.INVALID",  # Invalid event type
        },
    ]
    dials = Dial.from_legacy_dials(legacy_dials)
    assert len(dials) == 0, "Expected no valid Dial instances from invalid input"


def test_old_config_parsing() -> None:
    """Test parsing an old YAML config with a basic LegacyDial and no buttons."""
    # Define a simple old YAML config with one LegacyDial
    min_attr = 0.0
    max_attr = 100.0
    step_attr = 5.0
    old_yaml = f"""
    pages:
      - name: Main
        dials:
          - entity_id: light.living_room
            dial_event_type: DialEventType.TURN
            service: light.turn_on
            state_attribute: brightness
            attributes:
              min: {min_attr}
              max: {max_attr}
              step: {step_attr}
    """

    # Write YAML to a temporary file
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        temp_file.write(old_yaml)
        temp_file_path = Path(temp_file.name)

    try:
        # Load the config
        config = Config.load(temp_file_path, yaml_encoding="utf-8")

        # Validate the resulting Config object
        assert isinstance(config, Config), "Expected a Config instance"
        assert len(config.pages) == 1, "Expected one page"
        assert len(config.anonymous_pages) == 0, "Expected no anonymous pages"

        # Validate the page
        page = config.pages[0]
        assert isinstance(page, Page), "Expected a Page instance"
        assert page.name == "Main", "Expected page name 'Main'"
        assert len(page.buttons) == 0, "Expected no buttons"
        assert len(page.dials) == 1, "Expected one dial"

        # Validate the dial
        dial = page.dials[0]

        # Validate turn configuration
        assert isinstance(dial.turn, DialTurnConfig), "Expected a DialTurnConfig"
        assert dial.turn.service == "light.turn_on", "Expected correct service"
        assert dial.turn.properties.service_attribute == "brightness", (
            "Expected correct state_attribute"
        )
        assert dial.turn.properties.min == min_attr, f"Expected min {min_attr}"
        assert dial.turn.properties.max == max_attr, f"Expected max {max_attr}"
        assert dial.turn.properties.step == step_attr, f"Expected step {step_attr}"
        assert dial.turn.properties.state == 0.0, "Expected default state 0.0"

        # Validate no push configuration
        assert dial.push is None, "Expected no push configuration"

    finally:
        # Clean up temporary file
        temp_file_path.unlink()
