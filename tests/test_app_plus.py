"""Test App Home_assistant_streamdeck_yaml for Streamdeck plus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import websockets
from PIL import Image
from StreamDeck.Devices.StreamDeck import DialEventType, TouchscreenEventType
from StreamDeck.Devices.StreamDeckPlus import StreamDeckPlus

from home_assistant_streamdeck_yaml import (
    Button,
    Config,
    Dial,
    Page,
    _get_blank_image,
    _get_size_per_dial,
    _on_dial_event_callback,
    _on_touchscreen_event_callback,
    _update_state,
    update_all_dials,
    update_dial,
)

ROOT = Path(__file__).parent.parent
TEST_STATE_FILENAME = ROOT / "tests" / "state_plus.json"


# TESTS FOR STREAM DECK PLUS
@pytest.fixture
def websocket_mock() -> Mock:
    """Mock websocket client connection."""
    return Mock(spec=websockets.ClientConnection)


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
def dial_dict() -> dict[str, dict[str, Any]]:
    """Returns Config dictionary for streamdeck plus."""
    return {
        "number_value": {
            "entity_id": "input_number.streamdeck",
            "service": "input_number.set_value",
            "service_data": {"value": "{{ dial_value() }}"},
            "icon_mdi": "television",
            "dial_event_type": "TURN",
            "attributes": {"min": 0, "max": 100, "step": 1},
            "allow_touchscreen_events": True,
        },
        "input_number": {
            "entity_id": "input_number.streamdeck",
            "service": "input_number.set_value",
            "service_data": {"value": 0},
            "dial_event_type": "PUSH",
        },
        "icon_mdi": {
            "entity_id": "input_number.streamdeck",
            "service": "input_number.set_value",
            "service_data": {"value": "{{ dial_value() }}"},
            "icon_mdi": "home",
            "text": "Hello World",
            "dial_event_type": "TURN",
        },
        "spotify_icon": {
            "entity_id": "input_number.streamdeck",
            "service": "input_number.set_value",
            "service_data": {"value": "{{ dial_value() }}"},
            "icon": "spotify:playlist/37i9dQZF1DXaRycgyh6kXP",
            "dial_event_type": "TURN",
        },
    }


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


@pytest.fixture
def dials(dial_dict: dict[str, dict[str, Any]]) -> list[Dial]:
    """Order of dials for page."""
    dial_order = [
        "number_value",
        "input_number",
        "icon_mdi",
        "spotify_icon",
    ]

    return [Dial(**dial_dict[key]) for key in dial_order]


def test_dials(dials: list[Dial], state: dict[str, dict[str, Any]]) -> None:
    """Tests setup of pages with dials and rendering of image."""
    page = Page(name="Home", dials=dials)
    config = Config(pages=[page])
    first_page = config.to_page(0)

    # test dial sorting
    sorted_dials = first_page.sort_dials()
    assert sorted_dials is not None
    for i in range(len(sorted_dials)):
        assert sorted_dials[i] == config.dial_sorted(i)

    # change number value TURN event
    d = first_page.dials[0]
    # check domain type
    assert d.entity_id is not None
    # check image rendering
    sorted_key = first_page.get_sorted_key(d)
    print(d)
    assert isinstance(sorted_key, int)
    d = d.rendered_template_dial(state)
    icon = d.render_lcd_image(state, sorted_key, (200, 100))
    assert isinstance(icon, Image.Image)
    # check dial_value() jinja rendering
    assert d.service_data is not None
    assert isinstance(float(d.service_data["value"]), float)

    d = first_page.dials[1]
    assert d.service_data is not None
    assert d.dial_event_type == "PUSH"

    d = first_page.dials[2]
    # check icon rendering for mdi icons
    sorted_key = first_page.get_sorted_key(d)
    assert isinstance(sorted_key, int)
    d = d.rendered_template_dial(state)
    icon = d.render_lcd_image(state, sorted_key, (200, 100))
    assert isinstance(icon, Image.Image)
    assert d.text is not None
    assert d.dial_event_type == "TURN"

    d = first_page.dials[3]
    sorted_key = first_page.get_sorted_key(d)
    assert isinstance(sorted_key, int)
    d = d.rendered_template_dial(state)
    icon = d.render_lcd_image(state, sorted_key, (200, 100))
    assert isinstance(icon, Image.Image)
    assert d.dial_event_type == "TURN"


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

    config.current_page().sort_dials()
    dial = config.dial(0)
    assert dial is not None
    dial = dial.rendered_template_dial(state)
    assert dial.entity_id == "input_number.streamdeck"
    assert dial.service == "input_number.set_value"

    # gets attributes of dial and checks if state is correct
    update_dial(mock_deck_plus, 0, config, state)
    dial_val = dial.get_attributes()
    assert isinstance(dial_val, dict)
    dial_state = dial_val["state"]
    assert dial_state is not None
    # Fires dial event and increments state by 1
    config.current_page().sort_dials()

    dial_event = _on_dial_event_callback(websocket_mock, state, config)
    await dial_event(mock_deck_plus, 0, DialEventType.TURN, 1)
    # Test update state
    _update_state(state, state_change_msg, config, mock_deck_plus)
    # Check if state changed for input_number
    assert float(state["input_number.streamdeck"]["state"]) == dial_state + 1

    # test update attributes
    dial.update_attributes(state_change_msg["event"]["data"]["new_state"])
    updated_attributes = dial.get_attributes()
    assert updated_attributes["max"] == 100  # noqa: PLR2004
    assert updated_attributes["step"] == 1
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
    config.current_page().sort_dials()
    dial = config.dial(0)
    assert dial is not None

    touch_event = _on_touchscreen_event_callback(websocket_mock, state, config)
    await touch_event(
        mock_deck_plus,
        TouchscreenEventType.LONG,
        {
            "x": 100,
            "y": 50,
        },
    )
    attributes = dial.get_attributes()
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
    attributes = dial.get_attributes()
    assert attributes["state"] == attributes["min"]

    # Check if disabling touchscreen events works
    dial = config.dial(3)
    assert dial is not None
    assert dial.allow_touchscreen_events is not True

    touch_event = _on_touchscreen_event_callback(websocket_mock, state, config)
    await touch_event(
        mock_deck_plus,
        TouchscreenEventType.SHORT,
        {
            "x": 300,
            "y": 50,
        },
    )
    attributes = dial.get_attributes()
    assert attributes["state"] is not attributes["min"]


def test_update_all_dials_partial_and_no_dials(mock_deck_plus: Mock) -> None:  # noqa: PLR0915
    """Test updating partial dials and clearing unconfigured dial slots."""
    # Create dials programmatically for input_number entities
    dial_number1 = Dial(
        entity_id="input_number.streamdeck1",
        service="input_number.set_value",
        service_data={"value": "{{ dial_value() }}"},
        dial_event_type="TURN",
        text="Number 1",
        attributes={"min": 0, "max": 100, "step": 1},
    )
    dial_number2 = Dial(
        entity_id="input_number.streamdeck2",
        service="input_number.set_value",
        service_data={"value": "{{ dial_value() }}"},
        dial_event_type="TURN",
        text="Number 2",
        attributes={"min": 0, "max": 100, "step": 1},
    )

    # Create pages with different dial counts
    one_dial_page = Page(name="OneDial", dials=[dial_number1])
    two_dials_page = Page(name="TwoDials", dials=[dial_number1, dial_number2])
    no_dials_page = Page(name="NoDials", dials=[])

    # Create config with pages
    config = Config(pages=[one_dial_page, two_dials_page, no_dials_page])

    # Mock state with attributes and numeric states
    complete_state: dict[str, Any] = {
        "input_number.streamdeck1": {
            "state": 50.0,
            "attributes": {
                "friendly_name": "StreamDeck Number 1",
                "min": 0,
                "max": 100,
                "step": 1,
            },
        },
        "input_number.streamdeck2": {
            "state": 75.0,
            "attributes": {
                "friendly_name": "StreamDeck Number 2",
                "min": 0,
                "max": 100,
                "step": 1,
            },
        },
    }

    # Get size per dial and real blank image bytes
    size_per_dial: tuple[int, int] = _get_size_per_dial(mock_deck_plus)
    blank_image_bytes: bytes = _get_blank_image(size_per_dial)

    # Mock Dial.render_lcd_image
    def mock_render_lcd_image(
        self: Any,  # noqa: ARG001
        complete_state: dict[str, Any],  # noqa: ARG001
        size: tuple[int, int],
        key: int,  # noqa: ARG001
    ) -> Image.Image:
        return Image.new("RGB", size, (255, 255, 255))  # White image for updates

    with (
        patch("home_assistant_streamdeck_yaml.Dial.render_lcd_image", mock_render_lcd_image),
        patch("home_assistant_streamdeck_yaml._get_blank_image") as mock_get_blank_image,
    ):
        # Set the patched _get_blank_image to use the real implementation
        mock_get_blank_image.side_effect = _get_blank_image

        # Get the number of dials from the mock
        dial_count: int = mock_deck_plus.dial_count()

        # Test OneDial page (1 dial, clear remaining slots)
        config.to_page("OneDial")
        config.current_page().sort_dials()
        update_all_dials(mock_deck_plus, config, complete_state)
        assert (
            mock_deck_plus.set_touchscreen_image.call_count == dial_count
        )  # 1 update + (dial_count-1) clears
        assert mock_get_blank_image.call_count == 1  # Called once for unconfigured slots
        mock_get_blank_image.assert_called_with(size_per_dial)
        # Verify update call for dial_key=0
        assert any(
            call.args[1] == 0  # x_pos=0 for dial_key=0
            and call.args[2] == 0  # y_pos=0
            and call.kwargs["width"] == size_per_dial[0]
            and call.kwargs["height"] == size_per_dial[1]
            and len(call.args[0]) > 0  # Non-blank image
            for call in mock_deck_plus.set_touchscreen_image.call_args_list
        )
        # Verify clearing calls for unconfigured slots (dial_key=1 to dial_count-1)
        configured_keys = {0}  # OneDial has dial_key=0
        unconfigured_keys = set(range(dial_count)) - configured_keys
        for dial_key in unconfigured_keys:
            x_offset = dial_key * size_per_dial[0]
            assert any(
                call.args[1] == x_offset
                and call.args[2] == 0
                and call.kwargs["width"] == size_per_dial[0]
                and call.kwargs["height"] == size_per_dial[1]
                and call.args[0] == blank_image_bytes
                for call in mock_deck_plus.set_touchscreen_image.call_args_list
            )
        mock_get_blank_image.reset_mock()
        mock_deck_plus.set_touchscreen_image.reset_mock()

        # Test TwoDials page (2 dials, clear remaining slots)
        config.to_page("TwoDials")
        config.current_page().sort_dials()
        update_all_dials(mock_deck_plus, config, complete_state)
        assert (
            mock_deck_plus.set_touchscreen_image.call_count == dial_count
        )  # 2 updates + (dial_count-2) clears
        assert mock_get_blank_image.call_count == 1  # Called once for unconfigured slots
        mock_get_blank_image.assert_called_with(size_per_dial)
        for dial_key in [0, 1]:
            x_offset = dial_key * size_per_dial[0]
            assert any(
                call.args[1] == x_offset
                and call.args[2] == 0
                and call.kwargs["width"] == size_per_dial[0]
                and call.kwargs["height"] == size_per_dial[1]
                and len(call.args[0]) > 0
                for call in mock_deck_plus.set_touchscreen_image.call_args_list
            )
        configured_keys = {0, 1}  # TwoDials has dial_key=0,1
        unconfigured_keys = set(range(dial_count)) - configured_keys
        for dial_key in unconfigured_keys:
            x_offset = dial_key * size_per_dial[0]
            assert any(
                call.args[1] == x_offset
                and call.args[2] == 0
                and call.kwargs["width"] == size_per_dial[0]
                and call.kwargs["height"] == size_per_dial[1]
                and call.args[0] == blank_image_bytes
                for call in mock_deck_plus.set_touchscreen_image.call_args_list
            )
        mock_get_blank_image.reset_mock()
        mock_deck_plus.set_touchscreen_image.reset_mock()

        # Test NoDials page (clear all slots)
        config.to_page("NoDials")
        config.current_page().sort_dials()
        update_all_dials(mock_deck_plus, config, complete_state)
        assert mock_deck_plus.set_touchscreen_image.call_count == dial_count  # dial_count clears
        assert mock_get_blank_image.call_count == 1  # Called once for all slots
        mock_get_blank_image.assert_called_with(size_per_dial)
        configured_keys = set()  # NoDials has no dials
        unconfigured_keys = set(range(dial_count)) - configured_keys
        for dial_key in unconfigured_keys:
            x_offset = dial_key * size_per_dial[0]
            assert any(
                call.args[1] == x_offset
                and call.args[2] == 0
                and call.kwargs["width"] == size_per_dial[0]
                and call.kwargs["height"] == size_per_dial[1]
                and call.args[0] == blank_image_bytes
                for call in mock_deck_plus.set_touchscreen_image.call_args_list
            )


def test_get_size_per_dial(mock_deck_plus: Mock) -> None:
    """Test that _get_size_per_dial() works properly."""
    assert _get_size_per_dial(mock_deck_plus) == (
        StreamDeckPlus.TOUCHSCREEN_PIXEL_WIDTH / mock_deck_plus.dial_count(),
        StreamDeckPlus.TOUCHSCREEN_PIXEL_HEIGHT,
    )
