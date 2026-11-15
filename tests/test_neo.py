"""Test the touch keys and the info screen of the Stream Deck Neo."""

from __future__ import annotations

import copy
import functools as ft
import io
from typing import Any
from unittest.mock import MagicMock, Mock, call

import pytest
import websockets
from PIL import Image
from StreamDeck.Devices.StreamDeckNeo import StreamDeckNeo
from StreamDeck.Devices.StreamDeckOriginal import StreamDeckOriginal

from home_assistant_streamdeck_yaml import (
    Button,
    Config,
    Page,
    _led_rgb,
    _on_press_callback,
    _render_info_screen_image,
    _update_state,
    update_all_key_images,
    update_info_screen,
)

PLAYER = "media_player.living_room"


def _spy(deck: Any, *names: str) -> None:
    for name in names:
        setattr(deck, name, MagicMock(wraps=getattr(deck, name)))


@pytest.fixture
def neo() -> StreamDeckNeo:
    """A Stream Deck Neo on a mocked HID transport; the device class checks indices itself."""
    deck = StreamDeckNeo(Mock())
    _spy(deck, "set_key_image", "set_key_color", "set_screen_image")
    return deck


@pytest.fixture
def original() -> StreamDeckOriginal:
    """A Stream Deck Original (no touch keys, no info screen) on a mocked HID transport."""
    deck = StreamDeckOriginal(Mock())
    _spy(deck, "set_key_image")
    return deck


@pytest.fixture
def state() -> dict[str, dict[str, Any]]:
    """A media player that plays."""
    return {
        PLAYER: {
            "entity_id": PLAYER,
            "state": "playing",
            "attributes": {"media_title": "Song", "media_artist": "Artist"},
        },
    }


@pytest.fixture
def websocket_mock() -> Mock:
    """Mock websocket client connection."""
    return Mock(spec=websockets.ClientConnection)


def _neo_page(name: str = "music", **page_kwargs: Any) -> Page:
    led = "{{ 'green' if is_state('" + PLAYER + "', 'playing') else 'off' }}"
    buttons = [Button(text=str(i)) for i in range(8)]
    buttons += [
        Button(entity_id=PLAYER, service="media_player.media_previous_track", led_color=led),
        Button(
            entity_id=PLAYER,
            service="media_player.media_next_track",
            led_color=led,
            long_press={"service": "media_player.media_play_pause"},
        ),
    ]
    return Page(name=name, buttons=buttons, **page_kwargs)


def _state_changed(current: dict[str, dict[str, Any]], entity_id: str, **new: Any) -> dict:
    new_state = copy.deepcopy(current.get(entity_id, {"entity_id": entity_id, "attributes": {}}))
    attributes = new.pop("attributes", {})
    new_state.update(new)
    new_state["attributes"].update(attributes)
    return {
        "type": "event",
        "event": {
            "event_type": "state_changed",
            "data": {"entity_id": entity_id, "new_state": new_state},
        },
    }


def test_touch_keys_get_led_colors_not_images(
    neo: StreamDeckNeo,
    state: dict[str, dict[str, Any]],
) -> None:
    """Buttons 9 and 10 drive the touch-key LEDs; no key image is sent past key 7."""
    config = Config(pages=[_neo_page()])
    update_all_key_images(neo, config, state)
    assert [c.args[0] for c in neo.set_key_image.call_args_list] == list(range(8))
    assert neo.set_key_color.call_args_list == [call(8, 0, 128, 0), call(9, 0, 128, 0)]


def test_touch_key_led_follows_state(
    neo: StreamDeckNeo,
    state: dict[str, dict[str, Any]],
) -> None:
    """A state change of the button's entity re-renders the LED only."""
    config = Config(pages=[_neo_page()])
    _update_state(state, _state_changed(state, PLAYER, state="paused"), config, neo)
    assert neo.set_key_color.call_args_list == [call(8, 0, 0, 0), call(9, 0, 0, 0)]
    neo.set_key_image.assert_not_called()


def test_touch_key_without_led_color_or_button_is_off(
    neo: StreamDeckNeo,
    state: dict[str, dict[str, Any]],
) -> None:
    """A touch key without `led_color`, or without a button, is switched off."""
    buttons = [Button(text=str(i)) for i in range(8)] + [Button(service="script.x")]
    config = Config(pages=[Page(name="p", buttons=buttons)])
    update_all_key_images(neo, config, state)
    assert neo.set_key_color.call_args_list == [call(8, 0, 0, 0), call(9, 0, 0, 0)]


async def test_touch_key_press_calls_service(
    neo: StreamDeckNeo,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Touch keys 8 and 9 run their button's action; long press works as for keys."""
    config = Config(pages=[_neo_page()], long_press_duration=1.0)
    calls: list[tuple[str, dict]] = []

    async def fake_call_service(_ws: Any, service: str, data: dict, _target: Any) -> None:
        calls.append((service, data))

    monkeypatch.setattr("home_assistant_streamdeck_yaml.call_service", fake_call_service)
    press = ft.partial(_on_press_callback(websocket_mock, state, config), neo)

    await press(8, True)  # noqa: FBT003
    await press(8, False)  # noqa: FBT003
    await press(9, True)  # noqa: FBT003
    await press(9, False)  # noqa: FBT003
    times = iter([100.0, 102.0])
    monkeypatch.setattr("home_assistant_streamdeck_yaml.time.time", lambda: next(times))
    await press(9, True)  # noqa: FBT003
    await press(9, False)  # noqa: FBT003

    assert calls == [
        ("media_player.media_previous_track", {"entity_id": PLAYER}),
        ("media_player.media_next_track", {"entity_id": PLAYER}),
        ("media_player.media_play_pause", {"entity_id": PLAYER}),
    ]
    assert all(c.args[0] < neo.key_count() for c in neo.set_key_image.call_args_list)


async def test_key_without_button_is_ignored(
    neo: StreamDeckNeo,
    websocket_mock: Mock,
    state: dict[str, dict[str, Any]],
) -> None:
    """Pressing a key that has no button on the page neither raises nor calls anything."""
    config = Config(pages=[Page(name="p", buttons=[Button(service="script.x")])])
    press = ft.partial(_on_press_callback(websocket_mock, state, config), neo)
    for key in (3, 8, 9):
        await press(key, True)  # noqa: FBT003
        await press(key, False)  # noqa: FBT003
    websocket_mock.send.assert_not_called()


def test_info_screen_on_page_switch_and_state_change(
    neo: StreamDeckNeo,
    state: dict[str, dict[str, Any]],
) -> None:
    """The info text renders on page display and when `info_entity_id` changes its text."""
    info = (
        "{% if is_state('" + PLAYER + "', 'playing') %}"
        "{{ state_attr('" + PLAYER + "', 'media_title') }}\n"
        "{{ state_attr('" + PLAYER + "', 'media_artist') }}"
        "{% else %}{{ states('" + PLAYER + "') }}{% endif %}"
    )
    music = _neo_page(info_text=info, info_entity_id=PLAYER)
    blank = Page(name="blank", buttons=[])
    config = Config(pages=[music, blank])

    update_all_key_images(neo, config, state)
    assert neo.set_screen_image.call_count == 1
    assert config._info_screen_text == "Song\nArtist"
    jpeg = neo.set_screen_image.call_args.args[0]
    assert Image.open(io.BytesIO(jpeg)).size == (248, 58)

    # Same text (e.g., only the media position changed): no write
    event = _state_changed(state, PLAYER, attributes={"media_position": 12})
    _update_state(state, event, config, neo)
    assert neo.set_screen_image.call_count == 1

    # Another entity: no write
    _update_state(state, _state_changed(state, "light.other", state="on"), config, neo)
    assert neo.set_screen_image.call_count == 1

    _update_state(state, _state_changed(state, PLAYER, state="paused"), config, neo)
    assert neo.set_screen_image.call_count == 2  # noqa: PLR2004
    assert config._info_screen_text == "paused"

    # A page without info_text blanks the screen
    config.next_page()
    update_all_key_images(neo, config, state)
    assert neo.set_screen_image.call_count == 3  # noqa: PLR2004
    assert config._info_screen_text == ""


def test_deck_without_touch_keys_or_screen_is_unaffected(
    original: StreamDeckOriginal,
    state: dict[str, dict[str, Any]],
) -> None:
    """On a deck without info screen and touch keys nothing new is written."""
    original.set_screen_image = MagicMock()
    original.set_key_color = MagicMock()
    page = Page(
        name="p",
        buttons=[Button(text=str(i)) for i in range(16)],
        info_text="hello",
        info_entity_id=PLAYER,
    )
    config = Config(pages=[page])
    update_all_key_images(original, config, state)
    update_info_screen(original, config, state)
    assert [c.args[0] for c in original.set_key_image.call_args_list] == list(range(15))
    original.set_screen_image.assert_not_called()
    original.set_key_color.assert_not_called()


def test_render_info_screen_image() -> None:
    """Text is drawn white on black; long lines are shortened instead of overflowing."""
    size = (248, 58)
    assert _render_info_screen_image("", size).getbbox() is None
    image = _render_info_screen_image("A very long title " * 10 + "\nartist", size)
    assert image.size == size
    assert image.getbbox() is not None


@pytest.mark.parametrize(
    ("color", "rgb"),
    [
        (None, (0, 0, 0)),
        ("", (0, 0, 0)),
        ("off", (0, 0, 0)),
        ("green", (0, 128, 0)),
        ("#FF8000", (255, 128, 0)),
    ],
)
def test_led_rgb(color: str | None, rgb: tuple[int, int, int]) -> None:
    """Named and hex colors map to RGB; empty and `off` are black."""
    assert _led_rgb(color) == rgb


def test_invalid_led_color_turns_led_off(
    neo: StreamDeckNeo,
    state: dict[str, dict[str, Any]],
) -> None:
    """An invalid color is logged and the LED is switched off."""
    buttons = [Button() for _ in range(8)] + [Button(led_color="not-a-color")]
    config = Config(pages=[Page(name="p", buttons=buttons)])
    update_all_key_images(neo, config, state)
    assert call(8, 0, 0, 0) in neo.set_key_color.call_args_list
