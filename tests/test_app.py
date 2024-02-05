"""Test Home Assistant Stream Deck YAML."""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import websockets
from dotenv import dotenv_values
from PIL import Image
from pydantic import ValidationError
from StreamDeck.Devices.StreamDeckOriginal import StreamDeckOriginal

from home_assistant_streamdeck_yaml import (
    ASSETS_PATH,
    DEFAULT_CONFIG,
    Button,
    Config,
    IconWarning,
    Page,
    _download_and_save_mdi,
    _download_spotify_image,
    _generate_uniform_hex_colors,
    _handle_key_press,
    _init_icon,
    _is_state,
    _is_state_attr,
    _keys,
    _light_page,
    _named_to_hex,
    _on_press_callback,
    _render_jinja,
    _states,
    _to_filename,
    _url_to_filename,
    get_states,
    setup_ws,
    update_key_image,
)

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
TEST_STATE_FILENAME = ROOT / "tests" / "state.json"
IS_CONNECTED_TO_HOMEASSISTANT = False
BUTTONS_PER_PAGE = 15


def test_load_config() -> None:
    """Test Config.load."""
    Config.load(DEFAULT_CONFIG)


def test_reload_config() -> None:
    """Test Config.load."""
    c = Config.load(DEFAULT_CONFIG)
    c.pages = []
    assert c.pages == []
    c.reload()
    assert c.pages != []


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
        "light-control": {
            "entity_id": "light.living_room_lights_z2m",
            "special_type": "light-control",
            "special_type_data": {
                "colors": [
                    "#FF0000",  # red
                    "#00FF00",  # green
                    "#0000FF",  # blue
                    "#FFFF00",  # yellow
                    "#FFC0CB",  # pink
                    "#800080",  # purple
                    "#FFA500",  # orange
                    "#00FFFF",  # cyan
                    "#FFD700",  # gold
                    "#008000",  # dark green
                ],
            },
        },
        "icon_from_url": {
            "icon": "url:https://www.nijho.lt/authors/admin/avatar.jpg",
            # Normally one would use `person.bas`, however, that state is not in the test JSON.
            "text": "{% if is_state('light.living_room_lights_z2m', 'on') %}Home{% else %}Away{% endif %}",
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
            "text_offset": 4,
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
        "grayscale_button": {
            "entity_id": "input_select.sleep_mode",
            "icon": "spotify:playlist/37i9dQZF1DXaRycgyh6kXP",
            "icon_gray_when_off": True,
        },
        "special_empty": {"special_type": "empty"},
        "special_goto_0": {"special_type": "go-to-page", "special_type_data": 0},
        "special_goto_home": {
            "special_type": "go-to-page",
            "special_type_data": "Home",
        },
        "special_prev_page": {"special_type": "previous-page"},
        "special_next_page": {"special_type": "next-page"},
        "turn_off": {"special_type": "turn-off"},
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
        "icon_from_url",
        "light-control",
        "special_empty",
        "turn_off",
        "special_goto_0",
        "special_goto_home",
        "special_prev_page",
        "special_next_page",
        "grayscale_button",
    ]

    return [Button(**button_dict[key]) for key in button_order]


@pytest.fixture()
def config(buttons: list[Button]) -> Config:
    """Config fixture."""
    page_1 = Page(buttons=buttons[:BUTTONS_PER_PAGE], name="Home")
    page_2 = Page(buttons=buttons[BUTTONS_PER_PAGE:], name="Second")
    return Config(pages=[page_1, page_2])


def test_named_to_hex() -> None:
    """Test named to hex conversion."""
    assert _named_to_hex("red") == "#ff0000"
    assert _named_to_hex("#ff0000") == "#ff0000"


def test_example_config_browsing_pages(config: Config) -> None:
    """Test example config browsing pages."""
    assert isinstance(config, Config)
    assert config._current_page_index == 0
    second_page = config.next_page()
    assert isinstance(second_page, Page)
    assert config._current_page_index == 1
    first_page = config.previous_page()
    assert isinstance(first_page, Page)
    assert config._current_page_index == 0
    assert len(first_page.buttons) == BUTTONS_PER_PAGE
    assert len(second_page.buttons) == 1  # update when adding more buttons
    second_page = config.to_page(1)
    assert isinstance(second_page, Page)
    assert config._current_page_index == 1
    first_page = config.to_page(first_page.name)
    assert config._current_page_index == 0
    assert config.button(0) == first_page.buttons[0]


@pytest.mark.skipif(
    not IS_CONNECTED_TO_HOMEASSISTANT,
    reason="Not connected to Home Assistant",
)
async def test_websocket_connection(buttons: list[Button]) -> None:
    """Test websocket connection."""
    config = dotenv_values(ROOT / ".env")
    async with setup_ws(
        config["HASS_HOST"],
        config["HASS_TOKEN"],
        config["WEBSOCKET_PROTOCOL"],
    ) as websocket:
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
    rendered_buttons = [
        button.rendered_template_button(state) for button in first_page.buttons
    ]

    b = rendered_buttons[0]  # LIGHT
    assert b.domain == "light"
    icon = b.render_icon(state)
    assert isinstance(icon, Image.Image)

    b = rendered_buttons[1]  # VOLUME_DOWN
    assert b.entity_id in state
    entity_state = state[b.entity_id]
    attrs = entity_state["attributes"]
    volume = attrs["volume_level"]
    assert b.text == f"{int(100 * volume)}%"
    assert b.service_data is not None
    assert float(b.service_data["volume_level"]) == volume - 0.05

    b = rendered_buttons[3]  # SCRIPT_WITH_TEXT_AND_ICON
    icon = b.render_icon(state)
    assert isinstance(icon, Image.Image)

    b = rendered_buttons[4]  # INPUT_SELECT_WITH_TEMPLATE
    assert b.text == "Sleep off"

    b = rendered_buttons[6]  # SPOTIFY_PLAYLIST
    icon = b.render_icon(state)
    assert b.icon is not None
    # render_icon should create a file
    filename = _to_filename(b.icon, ".jpeg")
    assert Path(filename).exists()

    b = rendered_buttons[14]  # SPECIAL_NEXT_PAGE
    assert b.domain is None

    b = rendered_buttons[0]  # LIGHT
    assert b.entity_id is not None
    assert _keys(b.entity_id, page.buttons) == [0, 8]


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
    _init_icon(
        icon_mdi="phone",
        icon_mdi_margin=1,
        icon_mdi_color="#ffbb00",
        size=(100, 100),
    )
    _init_icon(size=(100, 100))


@pytest.fixture()
def mock_deck() -> Mock:
    """Mocks a StreamDeck."""
    deck_mock = Mock(spec=StreamDeckOriginal)

    deck_mock.KEY_PIXEL_WIDTH = StreamDeckOriginal.KEY_PIXEL_WIDTH
    deck_mock.KEY_PIXEL_HEIGHT = StreamDeckOriginal.KEY_PIXEL_HEIGHT
    deck_mock.KEY_FLIP = StreamDeckOriginal.KEY_FLIP
    deck_mock.KEY_ROTATION = StreamDeckOriginal.KEY_ROTATION
    deck_mock.KEY_IMAGE_FORMAT = StreamDeckOriginal.KEY_IMAGE_FORMAT

    deck_mock.key_image_format.return_value = {
        "size": (deck_mock.KEY_PIXEL_WIDTH, deck_mock.KEY_PIXEL_HEIGHT),
        "format": deck_mock.KEY_IMAGE_FORMAT,
        "flip": deck_mock.KEY_FLIP,
        "rotation": deck_mock.KEY_ROTATION,
    }

    deck_mock.key_count.return_value = 15

    # Add the context manager methods
    deck_mock.__enter__ = Mock(return_value=deck_mock)
    deck_mock.__exit__ = Mock(return_value=False)

    return deck_mock


def test_update_key_image(
    mock_deck: Mock,
    config: Config,
    state: dict[str, dict[str, Any]],
) -> None:
    """Test update_key_image with MockDeck."""
    update_key_image(mock_deck, key=0, config=config, complete_state=state)
    page = config.current_page()
    assert config._current_page_index == 0
    for key, _ in enumerate(page.buttons):
        update_key_image(mock_deck, key=key, config=config, complete_state=state)

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
    page = _light_page(
        entity_id="light.bedroom",
        n_colors=10,
        colormap="hsv",
        colors=None,
        color_temp_kelvin=None,
    )
    buttons = page.buttons
    assert len(buttons) == BUTTONS_PER_PAGE
    assert buttons[0].icon_background_color is not None

    page = _light_page(
        entity_id="light.bedroom",
        n_colors=10,
        colormap=None,
        colors=None,
        color_temp_kelvin=None,
    )
    buttons = page.buttons
    assert len(buttons) == BUTTONS_PER_PAGE
    assert buttons[0].icon_background_color is not None

    hex_colors = (
        "#FF0000",  # red
        "#00FF00",  # green
        "#0000FF",  # blue
        "#FFFF00",  # yellow
        "#FFC0CB",  # pink
        "#800080",  # purple
        "#FFA500",  # orange
        "#00FFFF",  # cyan
        "#FFD700",  # gold
        "#008000",  # dark green
    )

    page = _light_page(
        entity_id="light.bedroom",
        n_colors=10,
        colormap=None,
        colors=hex_colors,
        color_temp_kelvin=None,
    )
    buttons = page.buttons


def test_url_to_filename() -> None:
    """Test url_to_filename."""
    url = "https://www.example.com/path/to/file.html"
    expected_filename = ASSETS_PATH / "www_example_com-1f8a388e.html"
    assert str(_url_to_filename(url)) == str(expected_filename)


def test_not_enough_buttons() -> None:
    """Test not enough buttons."""
    page = Page(
        buttons=[
            Button(
                entity_id="light.bedroom",
                icon="mdi:lightbulb",
                icon_background_color="#000000",
            ),
        ],
        name="test",
    )
    config = Config(pages=[page])
    assert config.button(2) is None


def test_generate_uniform_hex_colors() -> None:
    """Test _generate_uniform_hex_colors."""
    assert _generate_uniform_hex_colors(3) == ("#ffffff", "#000000", "#808080")
    n = 10
    assert len(_generate_uniform_hex_colors(n)) == n
    hex_str_length = 7
    assert all(
        isinstance(color, str) and len(color) == hex_str_length and color[0] == "#"
        for color in _generate_uniform_hex_colors(20)
    )


@pytest.fixture()
def websocket_mock() -> Mock:
    """Mock websocket client protocol."""
    return Mock(spec=websockets.WebSocketClientProtocol)


async def test_handle_key_press_toggle_light(
    mock_deck: Mock,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
    config: Config,
) -> None:
    """Test handle_key_press toggle light."""
    button = config.button(0)
    assert button is not None
    await _handle_key_press(websocket_mock, state, config, button, mock_deck)

    websocket_mock.send.assert_called_once()
    send_call_args = websocket_mock.send.call_args.args[0]
    payload = json.loads(send_call_args)

    assert payload["type"] == "call_service"
    assert payload["domain"] == "light"
    assert payload["service"] == "toggle"
    assert payload["service_data"] == {"entity_id": "light.living_room_lights_z2m"}


async def test_handle_key_press_next_page(
    websocket_mock: Mock,
    mock_deck: Mock,
    state: dict[str, dict[str, Any]],
    config: Config,
) -> None:
    """Test handle_key_press next page."""
    button = config.button(14)
    assert button is not None
    await _handle_key_press(websocket_mock, state, config, button, mock_deck)

    # No service should be called
    websocket_mock.send.assert_not_called()

    # Ensure that the next_page method is called
    assert config._current_page_index == 1


async def test_button_with_target(
    websocket_mock: Mock,
    mock_deck: Mock,
) -> None:
    """Test button with target."""
    button = Button(
        service="media_player.join",
        service_data={
            "group_members": ["media_player.2", "media_player.3", "media_player.4"],
        },
        target={"entity_id": "media_player.1"},
    )
    config = Config(pages=[Page(buttons=[button], name="test")])
    _button = config.button(0)
    assert _button is not None
    assert _button.service == "media_player.join"
    await _handle_key_press(websocket_mock, {}, config, _button, mock_deck)
    # Check that the send method was called with the correct payload
    called_payload = json.loads(websocket_mock.send.call_args.args[0])
    expected_payload = {
        "id": called_payload["id"],  # Use the called id to match it
        "type": "call_service",
        "domain": "media_player",
        "service": "join",
        "service_data": {
            "group_members": [
                "media_player.2",
                "media_player.3",
                "media_player.4",
            ],
        },
        "target": {
            "entity_id": "media_player.1",
        },
    }

    assert called_payload == expected_payload


@pytest.mark.parametrize(
    ("template", "state", "expected_output"),
    [
        # Test 1: Activate a scene
        # No jinja template to test
        # Test 2: Toggle a cover
        (
            """
            {% if is_state('cover.garage_door', 'open') %}
            garage-open
            {% else %}
            garage-lock
            {% endif %}
            """,
            {"cover.garage_door": {"state": "open"}},
            "garage-open",
        ),
        (
            """
            {% if is_state('cover.garage_door', 'open') %}
            garage-open
            {% else %}
            garage-lock
            {% endif %}
            """,
            {"cover.garage_door": {"state": "closed"}},
            "garage-lock",
        ),
        # Test 3: Start or stop the vacuum robot (already provided)
        (
            """
            {% if is_state('vacuum.cleaning_robot', 'docked') %}
            vacuum.start
            {% else %}
            vacuum.return_to_base
            {% endif %}
            """,
            {"vacuum.cleaning_robot": {"state": "docked"}},
            "vacuum.start",
        ),
        (
            """
            {% if is_state('vacuum.cleaning_robot', 'docked') %}
            vacuum.start
            {% else %}
            vacuum.return_to_base
            {% endif %}
            """,
            {"vacuum.cleaning_robot": {"state": "cleaning"}},
            "vacuum.return_to_base",
        ),
        # Test 4: Mute/unmute a media player
        (
            """
        {% if is_state_attr('media_player.kef_ls50', 'is_volume_muted', true) %}
        false
        {% else %}
        true
        {% endif %}
        """,
            {"media_player.kef_ls50": {"attributes": {"is_volume_muted": True}}},
            "false",
        ),
        (
            """
            {% if is_state_attr('media_player.living_room_speaker', 'is_volume_muted', true) %}
            volume-off
            {% else %}
            volume-high
            {% endif %}
            """,
            {
                "media_player.living_room_speaker": {
                    "attributes": {"is_volume_muted": True},
                },
            },
            "volume-off",
        ),
        (
            """
            {% if is_state_attr('media_player.living_room_speaker', 'is_volume_muted', true) %}
            volume-off
            {% else %}
            volume-high
            {% endif %}
            """,
            {
                "media_player.living_room_speaker": {
                    "attributes": {"is_volume_muted": False},
                },
            },
            "volume-high",
        ),
        # Test 5: Control the brightness of a light
        (
            """
            {% set current_brightness = state_attr('light.living_room_lights', 'brightness') %}
            {% set brightness_pct = (current_brightness / 255) * 100 %}
            {{ brightness_pct | round }}%
            """,
            {"light.living_room_lights": {"attributes": {"brightness": 128}}},
            "50.0%",
        ),
        # Test 6: Toggle a fan
        (
            """
            {% if is_state('fan.bedroom_fan', 'on') %}
            fan
            {% else %}
            fan-off
            {% endif %}
            """,
            {"fan.bedroom_fan": {"state": "on"}},
            "fan",
        ),
        (
            """
            {% if is_state('fan.bedroom_fan', 'on') %}
            fan
            {% else %}
            fan-off
            {% endif %}
            """,
            {"fan.bedroom_fan": {"state": "off"}},
            "fan-off",
        ),
        # Test 7: Lock/unlock a door (cont.)
        (
            """
            {% if is_state('lock.front_door', 'unlocked') %}
            door-open
            {% else %}
            door-closed
            {% endif %}
            """,
            {"lock.front_door": {"state": "unlocked"}},
            "door-open",
        ),
        (
            """
            {% if is_state('lock.front_door', 'unlocked') %}
            door-open
            {% else %}
            door-closed
            {% endif %}
            """,
            {"lock.front_door": {"state": "locked"}},
            "door-closed",
        ),
        # Test 8: Arm/disarm an alarm system
        (
            """
            {% if is_state('alarm_control_panel.home_alarm', 'armed_away') %}
            alarm_control_panel.alarm_disarm
            {% else %}
            alarm_control_panel.alarm_arm_away
            {% endif %}
            """,
            {"alarm_control_panel.home_alarm": {"state": "armed_away"}},
            "alarm_control_panel.alarm_disarm",
        ),
        (
            """
            {% if is_state('alarm_control_panel.home_alarm', 'armed_away') %}
            alarm_control_panel.alarm_disarm
            {% else %}
            alarm_control_panel.alarm_arm_away
            {% endif %}
            """,
            {"alarm_control_panel.home_alarm": {"state": "disarmed"}},
            "alarm_control_panel.alarm_arm_away",
        ),
        # Test 9: Set an alarm time for the next day
        (
            """
            {{ '07:00:00' if states('input_datetime.alarm_time') != '07:00:00' else '08:00:00' }}
            """,
            {"input_datetime.alarm_time": {"state": "07:00:00"}},
            "08:00:00",
        ),
        (
            """
            {{ '07:00:00' if states('input_datetime.alarm_time') != '07:00:00' else '08:00:00' }}
            """,
            {"input_datetime.alarm_time": {"state": "08:00:00"}},
            "07:00:00",
        ),
        # Test 10: Control a media player (e.g., pause/play or skip tracks)
        (
            """
            {% if is_state('media_player.living_room_speaker', 'playing') %}
            pause
            {% else %}
            play
            {% endif %}
            """,
            {"media_player.living_room_speaker": {"state": "playing"}},
            "pause",
        ),
        (
            """
            {% if is_state('media_player.living_room_speaker', 'playing') %}
            pause
            {% else %}
            play
            {% endif %}
            """,
            {"media_player.living_room_speaker": {"state": "paused"}},
            "play",
        ),
        # Test 11: Set a specific color for a light
        (
            """
            {% if is_state('light.living_room_light', 'on') %}
            lightbulb-on
            {% else %}
            lightbulb-off
            {% endif %}
            """,
            {"light.living_room_light": {"state": "on"}},
            "lightbulb-on",
        ),
        (
            """
            {% if is_state('light.living_room_light', 'on') %}
            lightbulb-on
            {% else %}
            lightbulb-off
            {% endif %}
            """,
            {"light.living_room_light": {"state": "off"}},
            "lightbulb-off",
        ),
        # Test 12: Adjust the thermostat to a specific temperature
        # No jinja template to test
        # Test 13: Trigger a script to send a notification to your mobile device
        # No jinja template to test
        # Test 14: Toggle day/night mode (using an input_boolean)
        (
            """
            {% if is_state('input_boolean.day_night_mode', 'on') %}
            weather-night
            {% else %}
            weather-sunny
            {% endif %}
            """,
            {"input_boolean.day_night_mode": {"state": "on"}},
            "weather-night",
        ),
        (
            """
            {% if is_state('input_boolean.day_night_mode', 'on') %}
            weather-night
            {% else %}
            weather-sunny
            {% endif %}
            """,
            {"input_boolean.day_night_mode": {"state": "off"}},
            "weather-sunny",
        ),
        # Test 15: Control a TV (e.g., turn on/off or change input source)
        # No jinja template to test
        # Test 16: Control a group of lights (e.g., turn on/off or change color)
        (
            """
            {% if is_state('group.living_room_lights', 'on') %}
            lightbulb-group
            {% else %}
            lightbulb-group-off
            {% endif %}
            """,
            {"group.living_room_lights": {"state": "on"}},
            "lightbulb-group",
        ),
        (
            """
            {% if is_state('group.living_room_lights', 'on') %}
            lightbulb-group
            {% else %}
            lightbulb-group-off
            {% endif %}
            """,
            {"group.living_room_lights": {"state": "off"}},
            "lightbulb-group-off",
        ),
        # Test 17: Trigger a doorbell or camera announcement
        (
            """
            {{ 17 if state_attr('climate.living_room', 'temperature') >= 22 else 22 }}
            """,
            {"climate.living_room": {"attributes": {"temperature": 22}}},
            "17",
        ),
        (
            """
            Set
            {{ '17°C' if state_attr('climate.living_room', 'temperature') >= 22 else '22°C' }}
            ({{ state_attr('climate.living_room', 'temperature') }}°C now)
            """,
            {"climate.living_room": {"attributes": {"temperature": 22}}},
            "Set\n17°C\n(22°C now)",
        ),
        # Test 18: Enable/disable a sleep timer (using an input_boolean)
        (
            """
            {% if is_state('input_boolean.sleep_timer', 'on') %}
            timer
            {% else %}
            timer-off
            {% endif %}
            """,
            {"input_boolean.sleep_timer": {"state": "on"}},
            "timer",
        ),
        (
            """
            {% if is_state('input_boolean.sleep_timer', 'on') %}
            timer
            {% else %}
            timer-off
            {% endif %}
            """,
            {"input_boolean.sleep_timer": {"state": "off"}},
            "timer-off",
        ),
        # Test 19: Retrieve weather information and display it on the button
        # No jinja template to test
        # Test 20: Toggle Wi-Fi on/off (using a switch)
        (
            """
            {% if is_state('switch.wifi_switch', 'on') %}
            wifi
            {% else %}
            wifi-off
            {% endif %}
            """,
            {"switch.wifi_switch": {"state": "on"}},
            "wifi",
        ),
        (
            """
            {% if is_state('switch.wifi_switch', 'on') %}
            wifi
            {% else %}
            wifi-off
            {% endif %}
            """,
            {"switch.wifi_switch": {"state": "off"}},
            "wifi-off",
        ),
    ],
)
def test_render_jinja2_from_examples_readme(
    template: str,
    state: dict[str, dict[str, Any]],
    expected_output: str,
) -> None:
    """Test _render_jinja for volume control."""
    assert _render_jinja(textwrap.dedent(template), state) == textwrap.dedent(
        expected_output,
    )


def test_render_jinja2_from_my_config_and_example_config() -> None:
    """Test _render_jinja for volume control."""
    template_volume_1 = textwrap.dedent(
        """
        {{ max(state_attr("media_player.kef_ls50", "volume_level") - 0.05, 0) }}
        """,
    )
    template_volume_2 = textwrap.dedent(
        """
            {{ (state_attr("media_player.kef_ls50", "volume_level") - 0.05) | max(0) }}
            """,
    )
    state_volume_1 = {
        "media_player.kef_ls50": {"attributes": {"volume_level": 0.5}},
    }
    state_volume_2 = {
        "media_player.kef_ls50": {"attributes": {"volume_level": 0.03}},
    }

    for template in [template_volume_1, template_volume_2]:
        assert float(_render_jinja(template, state_volume_1)) == 0.5 - 0.05
        assert float(_render_jinja(template, state_volume_2)) == 0

    template_volume_pct = textwrap.dedent(
        """
        {{ (100 * state_attr("media_player.kef_ls50", "volume_level")) | int }}%
        """,
    )
    state_volume_pct_1 = {
        "media_player.kef_ls50": {"attributes": {"volume_level": 0.5}},
    }
    state_volume_pct_2 = {
        "media_player.kef_ls50": {"attributes": {"volume_level": 0.75}},
    }

    assert _render_jinja(template_volume_pct, state_volume_pct_1) == "50%"
    assert _render_jinja(template_volume_pct, state_volume_pct_2) == "75%"

    entity_id = "light.living_room_lights"
    state = {entity_id: {"state": "off"}}
    assert _render_jinja("{{ states('" + entity_id + "') }}", state) == "off"

    template_volume_down_1 = textwrap.dedent(
        """
        {{ max(state_attr("media_player.kef_ls50", "volume_level") - 0.05, 0) }}
        """,
    )
    template_volume_down_2 = textwrap.dedent(
        """
        {{ (state_attr("media_player.kef_ls50", "volume_level") - 0.05) | max(0) }}
        """,
    )
    template_volume_up_1 = textwrap.dedent(
        """
        {{ min(state_attr("media_player.kef_ls50", "volume_level") + 0.05, 1) }}
        """,
    )
    template_volume_up_2 = textwrap.dedent(
        """
        {{ (state_attr("media_player.kef_ls50", "volume_level") + 0.05) | min(1) }}
        """,
    )
    state_volume = {
        "media_player.kef_ls50": {"attributes": {"volume_level": 0.5}},
    }
    for template_volume_down in [template_volume_down_1, template_volume_down_2]:
        assert float(_render_jinja(template_volume_down, state_volume)) == 0.5 - 0.05
    for template_volume_up in [template_volume_up_1, template_volume_up_2]:
        assert float(_render_jinja(template_volume_up, state_volume)) == 0.5 + 0.05

    template_brightness = textwrap.dedent(
        """
        {% set current_brightness = state_attr('light.living_room_lights', 'brightness') %}
        {% set next_brightness = (current_brightness + 25.5) % 255 %}
        {{ min(next_brightness, 255) | int }}
        """,
    )

    state_brightness = {
        "light.living_room_lights": {"attributes": {"brightness": 100}},
    }

    assert int(_render_jinja(template_brightness, state_brightness)) == int(
        (100 + 25.5) % 255,
    )

    template_str = textwrap.dedent(
        """
        {% set current_brightness = 10 %}
        {{ current_brightness | min(255) | int }}
        """,
    )
    assert int(_render_jinja(template_str, {})) == 10  # noqa: PLR2004


def test_icon_failed_icon() -> None:
    """Test icon function with failed icon."""
    button = Button(icon_mdi="non-existing-icon-yolo")

    # Test that ValueError is raised when rendering the icon
    with pytest.raises(ValueError, match="404"):
        button.render_icon({})

    # Test that IconWarning is issued when trying to render the icon
    with pytest.warns(IconWarning):
        button.try_render_icon({})

    icon = button.try_render_icon({}, size=(100, 100))
    assert icon is not None
    assert isinstance(icon, Image.Image)
    assert icon.size == (100, 100)


async def test_delay() -> None:
    """Test the delay."""
    button = Button(delay=0.1)
    assert not button.is_sleeping()
    assert button.maybe_start_or_cancel_timer()
    await asyncio.sleep(0)  # TODO: figure out why this is needed
    assert button._timer is not None
    assert button._timer.is_sleeping
    assert button.is_sleeping()
    _ = button.render_icon({})
    await asyncio.sleep(0.1)
    assert not button.is_sleeping()


def test_to_markdown_table() -> None:
    """Test to_markdown_table for docs."""
    table = Button.to_markdown_table()
    assert isinstance(table, str)


async def test_anonymous_page(
    mock_deck: Mock,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
) -> None:
    """Test that the anonymous page works."""
    home = Page(
        name="home",
        buttons=[Button(special_type="go-to-page", special_type_data="anon")],
    )
    anon = Page(
        name="anon",
        buttons=[Button(text="yolo"), Button(text="foo", delay=0.1)],
    )
    config = Config(pages=[home], anonymous_pages=[anon])
    assert config._current_page_index == 0
    assert config._detached_page is None
    assert config.to_page("anon") == anon
    assert config._detached_page is not None
    assert config.current_page() == anon
    button = config.button(0)
    assert button.text == "yolo"
    press = _on_press_callback(websocket_mock, state, config)
    # Click the button
    await press(mock_deck, 0, key_pressed=True)
    # Should now be the button on the first page
    button = config.button(0)
    assert button.special_type == "go-to-page"
    # Back to anon page
    assert config.to_page("anon") == anon
    # Click the delay button
    button = config.button(1)
    assert button.text == "foo"
    await press(mock_deck, 1, key_pressed=True)
    # Should now still be the button because of the delay
    assert button.text == "foo"
    assert config._detached_page is not None
    assert config.current_page() == anon
    with patch("home_assistant_streamdeck_yaml.update_all_key_images") as mock:
        await asyncio.sleep(0.15)  # longer than delay should then switch to home
        mock.assert_called_once()
    assert config._detached_page is None
    assert config.current_page() == home
    # Should now be the button on the first page
    button = config.button(0)
    assert button.special_type == "go-to-page"
