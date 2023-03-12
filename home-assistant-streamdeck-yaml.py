import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import rich
import websockets
import yaml
from jinja2 import Template
from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Devices import StreamDeck

ASSETS_PATH = Path(__file__).parent / "assets"


_ID_COUNTER = 0


def next_id():
    global _ID_COUNTER
    _ID_COUNTER += 1
    return _ID_COUNTER


@asynccontextmanager
async def setup_ws(host: str, token: str) -> websockets.WebSocketClientProtocol:
    """Set up the connection to Home Assistant."""
    uri = f"wss://{host}/api/websocket"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                # Send an authentication message to Home Assistant
                auth_payload = {"type": "auth", "access_token": token}
                await websocket.send(json.dumps(auth_payload))

                # Wait for the authentication response
                auth_response = await websocket.recv()
                rich.print(auth_response)
                rich.print("Connected to Home Assistant")
                yield websocket
        except ConnectionResetError:
            # Connection was reset, retrying in 5 seconds
            rich.print("Connection was reset, retrying in 5 seconds")
            await asyncio.sleep(5)


async def subscribe_state_changes(
    websocket: websockets.WebSocketClientProtocol,
) -> None:
    """Subscribe to the state change events."""
    subscribe_payload = {
        "type": "subscribe_events",
        "event_type": "state_changed",
        "id": next_id(),
    }
    await websocket.send(json.dumps(subscribe_payload))


async def handle_state_changes(
    websocket: websockets.WebSocketClientProtocol,
    state: dict[str, Any],
    deck: StreamDeck,
    buttons: list[dict[str, Any]],
) -> None:
    """Handle state changes."""
    # Wait for the state change events
    while True:
        data = json.loads(await websocket.recv())
        _update_state(state, data, buttons, deck)


def _key(entity_id: str, buttons) -> int | None:
    """Get the key index for an entity_id."""
    for i, button in enumerate(buttons):
        if button.get("entity") == entity_id:
            return i
    return None


def _update_state(
    state: dict[str, Any],
    data: dict[str, Any],
    buttons: list[dict[str, Any]],
    deck: StreamDeck,
):
    """Update the state dictionary and update the keys."""
    if data["type"] == "event":
        event_data = data["event"]
        if event_data["event_type"] == "state_changed":
            event_data = event_data["data"]
            eid = event_data["entity_id"]
            state[eid] = event_data["new_state"]
            key = _key(eid, buttons)
            if key is None:
                return
            rich.print(f"Updating key {key} for {eid}")
            update_key_image(deck, key, buttons[key], state, False)


def _render_jinja(text: str, data: dict[str, Any]) -> str:
    """Render a Jinja template."""
    template = Template(text)
    return template.render(**data)


async def get_states(websocket):
    # Subscribe to the state change events for a specific entity
    _id = next_id()
    subscribe_payload = {
        "type": "get_states",
        "id": _id,
    }
    await websocket.send(json.dumps(subscribe_payload))
    while True:
        data = json.loads(await websocket.recv())
        if data["type"] == "result":
            # Extract the state data from the response
            state_dict = {state["entity_id"]: state for state in data["result"]}
            rich.print(state_dict)
            await unsubscribe(websocket, _id)
            return state_dict


async def unsubscribe(websocket: websockets.WebSocketClientProtocol, id: str):
    ...
    # Subscribe to the state change events for a specific entity
    subscribe_payload = {
        "id": next_id(),
        "type": "unsubscribe_events",
        "subscription": id,
    }
    await websocket.send(json.dumps(subscribe_payload))


async def call_service(websocket, domain, service, data):
    # Subscribe to the state change events for a specific entity
    subscribe_payload = {
        "id": next_id(),
        "type": "call_service",
        "domain": domain,
        "service": service,
        "service_data": data,
    }
    await websocket.send(json.dumps(subscribe_payload))


def render_key_image(
    deck,
    *,
    text_color: str = "white",
    icon_filename: str | None = None,
    font_filename: str = "Roboto-Regular.ttf",
    label_text: str = "",
):
    # Resize the source image asset to best-fit the dimensions of a single key,
    # leaving a margin at the bottom so that we can draw the key title
    # afterwards.
    if icon_filename is not None:
        icon = Image.open(ASSETS_PATH / icon_filename)
    else:  # Open white image
        icon = Image.new("RGB", (deck.KEY_PIXEL_WIDTH, deck.KEY_PIXEL_HEIGHT), "black")

    image = PILHelper.create_scaled_image(deck, icon, margins=[0, 0, 0, 0])

    # Load a custom TrueType font and use it to overlay the key index, draw key
    # label onto the image a few pixels from the bottom of the key.
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ASSETS_PATH / font_filename), 12)
    draw.text(
        (image.width / 2, image.height / 2),
        text=label_text,
        font=font,
        anchor="ms",
        fill=text_color,
        # Center
        align="center",
    )

    return PILHelper.to_native_format(deck, image)


def update_key_image(deck, key, button, state, key_pressed: bool = False):
    if button.get("entity") in state:
        state = state[button["entity"]]
        text = _render_jinja(button["text"], data={"state": state})
        if "text_color" in button:
            text_color = _render_jinja(button["text_color"], data={"state": state})
        else:
            if state["state"] == "on":
                text_color = "orangered"
            else:
                text_color = "white"
    else:
        text = button.get("text", "")
        text_color = button.get("text_color", "white")
    image = render_key_image(
        deck,
        label_text=text,
        text_color=text_color if not key_pressed else "green",
        icon_filename=button.get("icon"),
    )
    with deck:
        deck.set_key_image(key, image)


def get_deck():
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
        raise RuntimeError("No Stream Deck found")
    print(f"Found {deck.key_count()} keys, {deck=}")
    return deck


def read_config(fname: str):
    with open(fname) as f:
        return yaml.safe_load(f)


async def main(host, token, config):
    deck = get_deck()
    buttons = config  # TODO: make it work with multiple decks
    async with setup_ws(host, token) as websocket:
        state = await get_states(websocket)
        for key in range(deck.key_count()):
            update_key_image(deck, key, buttons[key], state, False)
        deck.set_key_callback_async(on_press_callback(websocket, state, buttons))
        deck.set_brightness(100)
        await subscribe_state_changes(websocket)
        await handle_state_changes(websocket, state, deck, buttons)


def on_press_callback(websocket, state, buttons):
    async def key_change_callback(deck, key, key_pressed):
        print(f"Key {key} {'pressed' if key_pressed else 'released'}")
        button = buttons[key]
        update_key_image(deck, key, button, state, key_pressed)
        if key_pressed:
            data = {"entity_id": button["entity"]} if "entity" in button else {}
            await call_service(websocket, *button["service"].split("."), data)

    return key_change_callback


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--token", default=None)
    parser.add_argument("--config", default="streamdeck-config.yaml")
    args = parser.parse_args()
    config = read_config(args.config)
    asyncio.run(main(host=args.host, token=args.token, config=config))
