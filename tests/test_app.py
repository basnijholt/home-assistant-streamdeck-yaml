"""Test Home Assistant Stream Deck YAML."""

from __future__ import annotations

import asyncio
import functools as ft
import json
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import websockets
from dotenv import dotenv_values
from PIL import Image
from pydantic import ValidationError
from StreamDeck.Devices.StreamDeckOriginal import StreamDeckOriginal
from websockets.exceptions import ConnectionClosedError  # noqa: F401

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
    reset_inactivity_timer,
    run,
    setup_ws,
    update_all_key_images,
    update_key_image,
)

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
TEST_STATE_FILENAME = ROOT / "tests" / "state.json"
IS_CONNECTED_TO_HOMEASSISTANT = False
BUTTONS_PER_PAGE = 15
DEFAULT_CONFIG_ENCODING = "utf-8"


def test_load_config() -> None:
    """Test Config.load."""
    Config.load(DEFAULT_CONFIG, yaml_encoding=DEFAULT_CONFIG_ENCODING)


def test_reload_config() -> None:
    """Test Config.load."""
    c = Config.load(DEFAULT_CONFIG, yaml_encoding=DEFAULT_CONFIG_ENCODING)
    c.pages = []
    assert c.pages == []
    c.reload()
    assert c.pages != []


def test_load_config_no_pages_raises_error(tmp_path: Path) -> None:
    """Test that loading a config with no pages raises ValueError.

    Regression test for #280 - previously raised IndexError.
    """
    config_file = tmp_path / "empty_config.yaml"
    config_file.write_text("pages: []")

    with pytest.raises(ValueError, match="No pages defined"):
        Config.load(config_file, yaml_encoding=DEFAULT_CONFIG_ENCODING)


@pytest.fixture
def state() -> dict[str, dict[str, Any]]:
    """State fixture."""
    with TEST_STATE_FILENAME.open("r") as f:
        return json.load(f)


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
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


def test_example_close_pages(config: Config) -> None:
    """Test example config close pages."""
    assert isinstance(config, Config)
    assert config._current_page_index == 0
    second_page = config.next_page()
    assert isinstance(second_page, Page)
    assert config._current_page_index == 1
    config.close_page()
    assert config._current_page_index == 0


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
    rendered_buttons = [button.rendered_template_button(state) for button in first_page.buttons]

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


def test_long_press_target_allowed() -> None:
    """Test that 'target' is allowed in long_press configuration.

    Regression test: Previously 'target' was missing from allowed_keys in
    _validate_long_press, causing ValidationError when using target in long_press.
    """
    # This should NOT raise ValidationError - target is a valid key
    button = Button(
        service="light.turn_on",
        long_press={
            "service": "light.turn_off",
            "target": {"entity_id": "light.living_room"},
        },
    )
    assert button.long_press is not None
    assert button.long_press["target"] == {"entity_id": "light.living_room"}

    # Test with all valid long_press keys together
    button2 = Button(
        entity_id="light.bedroom",
        service="light.toggle",
        long_press={
            "service": "light.turn_off",
            "service_data": {"brightness": 50},
            "entity_id": "light.kitchen",
            "target": {"area_id": "living_room"},
            "special_type": "go-to-page",
            "special_type_data": "settings",
        },
    )
    assert button2.long_press is not None
    assert button2.long_press["target"] == {"area_id": "living_room"}


def test_long_press_target_validation() -> None:
    """Test that long_press.target must be a dictionary.

    Regression test: Validates that target type checking was added.
    """
    with pytest.raises(ValidationError, match=r"long_press\.target must be a dictionary"):
        Button(
            service="light.turn_on",
            long_press={
                "service": "light.turn_off",
                "target": "light.living_room",  # Wrong type - should be dict
            },
        )


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


@pytest.fixture
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
    deck_mock.dial_count.return_value = 0

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
        n_colors=9,
        colormap="hsv",
        colors=None,
        color_temp_kelvin=None,
        brightnesses=None,
        deck_key_count=BUTTONS_PER_PAGE,
    )
    buttons = page.buttons
    assert len(buttons) == BUTTONS_PER_PAGE
    assert buttons[0].icon_background_color is not None

    page = _light_page(
        entity_id="light.bedroom",
        n_colors=9,
        colormap=None,
        colors=None,
        color_temp_kelvin=None,
        brightnesses=None,
        deck_key_count=BUTTONS_PER_PAGE,
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
        n_colors=9,
        colormap=None,
        colors=hex_colors,
        color_temp_kelvin=None,
        brightnesses=None,
        deck_key_count=BUTTONS_PER_PAGE,
    )
    buttons = page.buttons

    # Check that we fill the page with buttons to have close-page in the same position
    page = _light_page(
        entity_id="light.bedroom",
        n_colors=0,
        colormap=None,
        colors=None,
        color_temp_kelvin=None,
        brightnesses=(0, 100),
        deck_key_count=BUTTONS_PER_PAGE,
    )
    buttons = page.buttons
    assert len(buttons) == BUTTONS_PER_PAGE


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


@pytest.fixture
def websocket_mock() -> Mock:
    """Mock websocket client connection."""
    return Mock(spec=websockets.ClientConnection)


async def test_handle_key_press_toggle_light(
    mock_deck: Mock,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
    config: Config,
) -> None:
    """Test handle_key_press toggle light."""
    button = config.button(0)
    assert button is not None
    await _handle_key_press(
        websocket_mock,
        state,
        config,
        button,
        mock_deck,
        is_long_press=False,
    )

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
    await _handle_key_press(
        websocket_mock,
        state,
        config,
        button,
        mock_deck,
        is_long_press=False,
    )

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
    await _handle_key_press(
        websocket_mock,
        {},
        config,
        _button,
        mock_deck,
        is_long_press=False,
    )
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
        # Test is_number filter
        (
            """
            {% if state_attr('sensor.temp1', 'temperature') | is_number %}
            {{ state_attr('sensor.temp1', 'temperature') }}°C
            {% else %}
            {{ state_attr('sensor.temp1', 'temperature') }}
            {% endif %}
            """,
            {"sensor.temp1": {"attributes": {"temperature": "unavailable"}}},
            "unavailable",
        ),
        # Test is_number filter
        (
            """
            {% if state_attr('sensor.temp1', 'temperature') | is_number %}
            {{ state_attr('sensor.temp1', 'temperature') }}°C
            {% else %}
            {{ state_attr('sensor.temp1', 'temperature') }}
            {% endif %}
            """,
            {"sensor.temp1": {"attributes": {"temperature": 3.2}}},
            "3.2°C",
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


async def test_long_press(
    mock_deck: Mock,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
) -> None:
    """Test long press."""
    # Use a higher threshold to account for icon rendering time
    long_press_threshold = 2.0
    short_press_time = 0.0
    assert short_press_time < long_press_threshold
    long_press_time = long_press_threshold + 0.5
    assert long_press_time > long_press_threshold

    home = Page(
        name="home",
        buttons=[
            Button(
                special_type="go-to-page",
                special_type_data="short",
                long_press={"special_type": "go-to-page", "special_type_data": "long"},
            ),
            Button(special_type="go-to-page", special_type_data="short"),
        ],
    )
    short = Page(
        name="short",
        buttons=[
            Button(text="short", special_type="go-to-page", special_type_data="home"),
        ],
    )
    long = Page(
        name="long",
        buttons=[
            Button(text="long", special_type="go-to-page", special_type_data="home"),
        ],
    )
    config = Config(pages=[home, short, long], long_press_duration=long_press_threshold)
    assert config._current_page_index == 0
    assert config.current_page() == home

    press_event = ft.partial(_on_press_callback(websocket_mock, state, config), mock_deck)

    async def press(key: int) -> None:
        await press_event(key, True)  # noqa: FBT003

    async def release(key: int) -> None:
        await press_event(key, False)  # noqa: FBT003

    async def press_and_release(key: int, seconds: float) -> None:
        await press(key)
        await asyncio.sleep(seconds)
        await release(key)

    await press_and_release(0, short_press_time)
    assert config.current_page() == short
    await press_and_release(0, short_press_time)
    assert config.current_page() == home
    await press_and_release(0, long_press_time)
    assert config.current_page() == long
    await press_and_release(0, short_press_time)
    assert config.current_page() == home
    await press_and_release(1, long_press_time)
    # uses `short` action because no long action is configured
    assert config.current_page() == short

    # NOTE: A potential future enhancement would be to trigger the long press action
    # automatically when the threshold is reached (without waiting for release).
    # This would require background monitoring and is not currently implemented -
    # the long press action only triggers on key release.


async def test_long_press_template_rendering(
    mock_deck: Mock,
    websocket_mock: Mock,
) -> None:
    """Test that templates in long_press are rendered before calling service.

    Regression test: Previously, values were extracted from long_press BEFORE
    rendered_template_button() was called, so templates weren't rendered.
    """
    state = {
        "light.living_room": {"state": "on", "attributes": {"brightness": 200}},
    }
    button = Button(
        entity_id="light.living_room",
        service="light.turn_on",
        long_press={
            "service": "light.turn_on",
            "service_data": {
                "entity_id": "light.living_room",
                # Template that should be rendered to "78" (200 * 100 / 255 ≈ 78)
                "brightness_pct": '{{ (state_attr("light.living_room", "brightness") * 100 / 255) | int }}',
            },
        },
    )
    config = Config(pages=[Page(name="test", buttons=[button])])

    await _handle_key_press(
        websocket_mock,
        state,
        config,
        button,
        mock_deck,
        is_long_press=True,
    )

    # Verify call_service was called
    websocket_mock.send.assert_called_once()
    send_call_args = websocket_mock.send.call_args.args[0]
    payload = json.loads(send_call_args)

    # The template should have been rendered to the actual value
    assert payload["type"] == "call_service"
    assert payload["domain"] == "light"
    assert payload["service"] == "turn_on"
    # Critical assertion: template must be rendered, not passed as raw string
    assert payload["service_data"]["brightness_pct"] == "78", (
        "Template in long_press.service_data was not rendered! "
        f"Got: {payload['service_data']['brightness_pct']}"
    )


async def test_long_press_service_from_rendered_button(
    mock_deck: Mock,
    websocket_mock: Mock,
) -> None:
    """Test that long_press.service template is rendered.

    Regression test: Ensures service name templates are also rendered.
    """
    state = {
        "input_select.action": {"state": "turn_off", "attributes": {}},
    }
    button = Button(
        entity_id="light.living_room",
        service="light.turn_on",
        long_press={
            # Template that should render to "light.turn_off"
            "service": '{{ "light." ~ states("input_select.action") }}',
            "service_data": {"entity_id": "light.living_room"},
        },
    )
    config = Config(pages=[Page(name="test", buttons=[button])])

    await _handle_key_press(
        websocket_mock,
        state,
        config,
        button,
        mock_deck,
        is_long_press=True,
    )

    websocket_mock.send.assert_called_once()
    payload = json.loads(websocket_mock.send.call_args.args[0])

    # The service template should have been rendered
    assert payload["domain"] == "light"
    assert payload["service"] == "turn_off", (
        "Template in long_press.service was not rendered! "
        f"Got domain.service: {payload['domain']}.{payload['service']}"
    )


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
        buttons=[
            Button(text="yolo"),
            Button(text="foo", delay=0.1),
            Button(special_type="close-page"),
        ],
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

    # We need to have a release otherwise it will be timing for a long press
    async def press_and_release(key: int) -> None:
        await press(mock_deck, key, key_pressed=True)
        await press(mock_deck, key, key_pressed=False)

    # Click the button
    await press_and_release(0)
    # Should now be the button on the first page
    button = config.button(0)
    assert button.special_type == "go-to-page"
    # Back to anon page
    assert config.to_page("anon") == anon
    # Click the delay button
    button = config.button(1)
    assert button.text == "foo"
    await press_and_release(1)
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

    # Test load_page_as_detached and close_detached_page methods
    assert config.current_page() == home
    config.load_page_as_detached(anon)
    assert config.current_page() == anon
    config.close_detached_page()
    assert config.current_page() == home

    # Back to anon page to test that the close button works properly
    assert config.to_page("anon") == anon
    await press_and_release(2)  # close page button
    assert config._detached_page is None
    assert config.current_page() == home

    # Test that to_page closes a detached page
    config.load_page_as_detached(anon)
    assert config.current_page() == anon
    config.to_page(home.name)
    assert config.current_page() == home
    assert config._detached_page is None


async def test_retry_logic_called_correct_number_of_times() -> None:
    """Test retry logic in run function."""
    # Config for the test
    config = Config()

    retry_attemps = 2

    # Patch setup_ws to simulate a network failure, and patch asyncio.sleep to avoid delays
    with (
        patch(
            "home_assistant_streamdeck_yaml.setup_ws",
            side_effect=OSError("Network is down"),
        ) as mock_setup_ws,
        patch("asyncio.sleep", return_value=None) as mock_sleep,
    ):
        mock_deck = Mock()

        # Run the function with retry_attempts = 2 to simulate retry logic
        await run(
            deck=mock_deck,
            host="localhost",
            token="",
            protocol="ws",
            config=config,
            retry_attempts=retry_attemps,
            retry_delay=0,
        )

        # Check that setup_ws was called 3 times (1 initial try + 2 retries)
        assert mock_setup_ws.call_count == retry_attemps + 1

        # Check that asyncio.sleep was called the same number of times as retries
        assert mock_sleep.call_count == retry_attemps


async def test_run_exits_immediately_on_zero_retries() -> None:
    """Test that run exits immediately when retry_attempts is set to 0."""
    config = Config()

    with (
        patch(
            "home_assistant_streamdeck_yaml.setup_ws",
            side_effect=OSError("Network is down"),
        ) as mock_setup_ws,
    ):
        mock_deck = Mock()

        # No exception should be raised, and run should return immediately
        await run(
            deck=mock_deck,
            host="localhost",
            token="",
            protocol="ws",
            config=config,
            retry_attempts=0,
            retry_delay=0,
        )

        # If setup_ws is called once, it means the retry logic did not retry
        assert mock_setup_ws.call_count == 1


def test_page_switch_clears_unused_keys(state: dict[str, dict[str, Any]]) -> None:
    """Test that switching pages clears unused keys."""
    # Setup pages: page1 has 2 buttons, page2 has only 1
    page1 = Page(name="Page1", buttons=[Button(text="Btn1"), Button(text="Btn2")])
    page2 = Page(name="Page2", buttons=[Button(text="Btn1 Only")])
    config = Config(pages=[page1, page2])

    # Patch dependencies: PILHelper for image conversion and DeviceManager to avoid needing a real deck
    with (
        patch(
            "home_assistant_streamdeck_yaml.PILHelper.to_native_format",
            return_value="mock_image_data",
        ),
        patch("home_assistant_streamdeck_yaml.DeviceManager") as mock_device_manager,
    ):
        # Configure the mock StreamDeck instance
        mock_deck_instance = mock_device_manager().enumerate()[0]
        mock_deck_instance.key_count.return_value = 2
        mock_deck_instance.key_image_format.return_value = {"size": (72, 72)}
        # Use MagicMock to easily track calls to set_key_image
        mock_deck_instance.set_key_image = MagicMock()

        # Start on the first page (page1)
        assert config._current_page_index == 0

        # Simulate switching to the second page (page2) which has fewer buttons
        config.to_page(1)
        assert config._current_page_index == 1

        # Trigger the image update process for the current page
        # This function should now handle clearing keys not defined on page2
        update_all_key_images(mock_deck_instance, config, state)

        # Verify that set_key_image was called correctly:
        # - Key 0 should receive the image for the button on page2.
        # - Key 1, which had a button on page1 but not page2, should be cleared (sent None).
        expected_calls = [
            call(0, "mock_image_data"),
            call(1, None),
        ]
        mock_deck_instance.set_key_image.assert_has_calls(
            expected_calls,
            any_order=False,
        )
        # Ensure exactly these two calls were made for the 2-key mock deck
        assert mock_deck_instance.set_key_image.call_count == 2  # noqa: PLR2004


def test_empty_text_button() -> None:
    """Test that text='' explicitly shows no text, while text=None shows default.

    Regression test for PR #142 - Allow empty text with "".
    """
    # Test the text field storage behavior
    button_default = Button()
    assert button_default.text is None, "Default text should be None"

    button_empty = Button(text="")
    assert button_empty.text == "", "Empty string text should be preserved"

    button_custom = Button(text="Custom")
    assert button_custom.text == "Custom", "Custom text should be preserved"

    # Verify all special types support empty text field
    special_types = [
        "next-page",
        "previous-page",
        "go-to-page",
        "close-page",
        "turn-off",
        "reload",
    ]
    for special_type in special_types:
        special_type_data = "test" if special_type == "go-to-page" else None

        # Default text (text=None)
        btn = Button(special_type=special_type, special_type_data=special_type_data)
        assert btn.text is None, f"{special_type}: text should be None by default"

        # Explicit empty text (text="")
        btn_empty = Button(
            special_type=special_type,
            special_type_data=special_type_data,
            text="",
        )
        assert btn_empty.text == "", f"{special_type}: text='' should be preserved"


def test_empty_text_render(state: dict[str, dict[str, Any]]) -> None:
    """Test that render_icon handles empty text correctly for special types.

    This verifies that text='' results in no text, while text=None uses defaults.
    """
    # Button without special_type - uses text field directly
    button_none = Button()
    button_none_rendered = button_none.rendered_template_button(state)
    assert button_none_rendered.text is None

    button_empty = Button(text="")
    button_empty_rendered = button_empty.rendered_template_button(state)
    assert button_empty_rendered.text == ""

    button_text = Button(text="Hello")
    button_text_rendered = button_text.rendered_template_button(state)
    assert button_text_rendered.text == "Hello"


def test_brightness_entity_id(mock_deck: Mock) -> None:
    """Test brightness_entity_id syncs brightness from Home Assistant entity.

    Tests the brightness_entity_id feature from PR #173.
    """
    from home_assistant_streamdeck_yaml import _sync_brightness_from_entity

    # Test basic config with brightness_entity_id
    config = Config(brightness_entity_id="input_number.streamdeck_brightness")
    assert config.brightness_entity_id == "input_number.streamdeck_brightness"
    assert config.brightness == 100  # noqa: PLR2004

    # Test _sync_brightness_from_entity with valid brightness
    state = {"input_number.streamdeck_brightness": {"state": "75"}}
    config._is_on = True
    _sync_brightness_from_entity(
        "input_number.streamdeck_brightness",
        state,
        config,
        mock_deck,
    )
    assert config.brightness == 75  # noqa: PLR2004
    mock_deck.set_brightness.assert_called_with(75)

    # Test with float value (HA sometimes returns floats)
    mock_deck.reset_mock()
    state = {"input_number.streamdeck_brightness": {"state": "50.0"}}
    _sync_brightness_from_entity(
        "input_number.streamdeck_brightness",
        state,
        config,
        mock_deck,
    )
    assert config.brightness == 50  # noqa: PLR2004
    mock_deck.set_brightness.assert_called_with(50)

    # Test with invalid brightness (out of range)
    mock_deck.reset_mock()
    state = {"input_number.streamdeck_brightness": {"state": "150"}}
    _sync_brightness_from_entity(
        "input_number.streamdeck_brightness",
        state,
        config,
        mock_deck,
    )
    # Should not change brightness when out of range
    mock_deck.set_brightness.assert_not_called()

    # Test with missing entity
    mock_deck.reset_mock()
    _sync_brightness_from_entity(
        "input_number.nonexistent",
        {},
        config,
        mock_deck,
    )
    mock_deck.set_brightness.assert_not_called()

    # Test with None brightness_entity_id
    mock_deck.reset_mock()
    _sync_brightness_from_entity(None, state, config, mock_deck)
    mock_deck.set_brightness.assert_not_called()

    # Test when deck is off (should update config but not call set_brightness)
    mock_deck.reset_mock()
    config._is_on = False
    state = {"input_number.streamdeck_brightness": {"state": "25"}}
    _sync_brightness_from_entity(
        "input_number.streamdeck_brightness",
        state,
        config,
        mock_deck,
    )
    assert config.brightness == 25  # noqa: PLR2004
    mock_deck.set_brightness.assert_not_called()  # Don't set when off


async def test_inactivity_timer_config() -> None:
    """Test inactivity_time config field.

    Tests the inactivity timer feature from PR #193.
    """
    # Test default value (disabled)
    config = Config()
    assert config.inactivity_time == -1  # Disabled by default

    # Test custom value
    config = Config(inactivity_time=30)
    assert config.inactivity_time == 30  # noqa: PLR2004

    # Test zero (edge case - should not trigger timer)
    config = Config(inactivity_time=0)
    assert config.inactivity_time == 0


async def test_inactivity_timer_basic(mock_deck: Mock) -> None:
    """Test basic inactivity timer behavior.

    Tests the reset_inactivity_timer function from PR #193.
    """
    # Test with timer disabled (default)
    config = Config(inactivity_time=-1)
    config._is_on = True
    reset_inactivity_timer(config, mock_deck)
    # No task should be created when disabled
    assert config._inactivity_task is None

    # Test with timer enabled
    config = Config(inactivity_time=0.1)  # Very short for testing
    config._is_on = True
    reset_inactivity_timer(config, mock_deck)
    # Task should be created
    assert config._inactivity_task is not None
    assert not config._inactivity_task.done()

    # Cancel the task to clean up
    config._inactivity_task.cancel()


async def test_inactivity_timer_cancels_previous(mock_deck: Mock) -> None:
    """Test that resetting the timer cancels the previous timer.

    Regression test for PR #193 - ensures timer is properly reset on activity.
    """
    config = Config(inactivity_time=10)  # Long enough to not complete
    config._is_on = True

    # Start first timer
    reset_inactivity_timer(config, mock_deck)
    first_task = config._inactivity_task
    assert first_task is not None

    # Reset timer (simulating user activity)
    reset_inactivity_timer(config, mock_deck)
    second_task = config._inactivity_task

    # Give event loop a chance to process the cancellation
    await asyncio.sleep(0)

    # First task should be cancelled or done (cancel was called on it)
    assert first_task.cancelled() or first_task.done()
    # Second task should be different and running
    assert second_task is not first_task
    assert second_task is not None
    assert not second_task.done()

    # Clean up
    second_task.cancel()


async def test_inactivity_timer_turns_off_deck(mock_deck: Mock) -> None:
    """Test that the timer actually turns off the deck after inactivity.

    Integration test for PR #193.
    """
    config = Config(inactivity_time=0.05)  # 50ms for fast testing
    config._is_on = True

    reset_inactivity_timer(config, mock_deck)

    # Wait for timer to complete
    await asyncio.sleep(0.1)

    # Deck should be turned off
    assert config._is_on is False
    mock_deck.reset.assert_called()
    mock_deck.set_brightness.assert_called_with(0)
