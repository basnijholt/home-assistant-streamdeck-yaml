"""Integration tests for TCPTransportDevice using an in-memory socketpair.

Used in place of a real TCP connection, scripted with bytes captured live
from the user's actual Network Dock + Stream Deck+ (tests/fixtures).
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Callable

from StreamDeck.Devices.StreamDeck import ControlType
from StreamDeck.Devices.StreamDeckPlus import StreamDeckPlus

from streamdeck_tcp import cora
from streamdeck_tcp.device import TCPTransportDevice, _disable_nagle

FIXTURES = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "cora_live_capture.json").read_text(),
)


def test_disable_nagle_sets_tcp_nodelay_on_real_tcp_socket() -> None:
    """Nagle's algorithm must be off -- it silently added the network-transport latency a user noticed live."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    client = socket.create_connection(listener.getsockname())
    try:
        _disable_nagle(client)
        assert client.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY) != 0
    finally:
        client.close()
        listener.close()


def test_disable_nagle_is_a_noop_on_non_tcp_socket() -> None:
    """Must not raise on the AF_UNIX socketpair this test suite uses as a TCP stand-in."""
    sock_a, sock_b = socket.socketpair()
    try:
        _disable_nagle(sock_a)  # no TCP_NODELAY on AF_UNIX -- should be swallowed, not raised
    finally:
        sock_a.close()
        sock_b.close()


class ScriptedConnector:
    """Test double for `socket.create_connection`.

    Each call returns one end of an in-memory socketpair, while a
    background thread plays the other end according to the next script in
    order.
    """

    def __init__(self, *scripts: Callable[[socket.socket], None]) -> None:
        """Store the ordered per-connection scripts to play."""
        self._scripts = list(scripts)
        self._threads: list[threading.Thread] = []

    def __call__(self, address: object, timeout: float | None = None) -> socket.socket:  # noqa: ARG002
        """Match `socket.create_connection`'s call signature; play the next script."""
        script = self._scripts.pop(0)
        ours, theirs = socket.socketpair()
        thread = threading.Thread(target=script, args=(theirs,), daemon=True)
        thread.start()
        self._threads.append(thread)
        return ours

    def join_all(self) -> None:
        """Wait for all scripted background threads to finish."""
        for thread in self._threads:
            thread.join(timeout=2.0)


def play_dock() -> Callable[[socket.socket], None]:
    """Script the dock's own port-5343 connection: unsolicited keepalive, then device2Info."""

    def script(sock: socket.socket) -> None:
        sock.sendall(bytes.fromhex(FIXTURES["dock_first_bytes"]))  # unsolicited keepalive
        request = sock.recv(4096)
        result = cora.decode_message(request)
        assert result is not None
        message, _ = result
        assert message.payload == bytes([0x03, 0x1C])
        response = cora.CoraMessage(
            flags=cora.FLAG_NONE,
            hid_op=message.hid_op,
            message_id=message.message_id,
            payload=bytes.fromhex(FIXTURES["device2info_full_message_payload"]),
        )
        sock.sendall(cora.encode_message(response))
        sock.close()

    return script


def play_deck_serial_query() -> Callable[[socket.socket], None]:
    """Script the deck's own connection: respond to a 0x06 serial-number GET_REPORT query."""

    def script(sock: socket.socket) -> None:
        request = sock.recv(4096)
        result = cora.decode_message(request)
        assert result is not None
        message, _ = result
        assert message.payload == bytes([0x06])
        response = cora.CoraMessage(
            flags=cora.FLAG_VERBATIM | cora.FLAG_RESULT,
            hid_op=message.hid_op,
            message_id=message.message_id,
            payload=bytes.fromhex(FIXTURES["serial_report_full_payload"]),
        )
        sock.sendall(cora.encode_message(response))
        time.sleep(0.3)  # keep the socket open so the reader thread doesn't error on close

    return script


def test_open_populates_identity_and_read_feature_returns_correct_serial() -> None:
    """open() populates vendor/product IDs and read_feature() returns the real serial number."""
    connector = ScriptedConnector(play_dock(), play_deck_serial_query())
    device = TCPTransportDevice("192.0.2.1", connect=connector)
    device.open()
    try:
        assert device.vendor_id() == 4057  # noqa: PLR2004
        assert device.product_id() == 132  # noqa: PLR2004
        result = device.read_feature(0x06, 32)
        assert result[0] == 0x06  # noqa: PLR2004
        assert result[5:].split(b"\x00", 1)[0] == b"EL51L1A00456"
    finally:
        device.close()
    connector.join_all()


def test_write_sends_correctly_wrapped_wire_bytes() -> None:
    """write() wraps its payload as a verbatim hid_write CORA message on the wire."""
    received: list[bytes] = []

    def play_deck_capture(sock: socket.socket) -> None:
        received.append(sock.recv(4096))
        time.sleep(0.3)

    connector = ScriptedConnector(play_dock(), play_deck_capture)
    device = TCPTransportDevice("192.0.2.1", connect=connector)
    device.open()
    device.write(bytes([0x02, 0xAA, 0xBB]))
    time.sleep(0.2)
    device.close()
    connector.join_all()

    assert len(received) == 1
    result = cora.decode_message(received[0])
    assert result is not None
    message, _ = result
    assert message.hid_op == cora.HID_OP_WRITE
    assert message.flags == cora.FLAG_VERBATIM
    assert message.payload == bytes([0x02, 0xAA, 0xBB])


def test_write_feature_sends_correctly_wrapped_wire_bytes() -> None:
    """write_feature() wraps its payload as a verbatim hid_send_feature_report CORA message."""
    received: list[bytes] = []

    def play_deck_capture(sock: socket.socket) -> None:
        received.append(sock.recv(4096))
        time.sleep(0.3)

    connector = ScriptedConnector(play_dock(), play_deck_capture)
    device = TCPTransportDevice("192.0.2.1", connect=connector)
    device.open()
    device.write_feature(bytes([0x03, 0x08, 100]))
    time.sleep(0.2)
    device.close()
    connector.join_all()

    result = cora.decode_message(received[0])
    assert result is not None
    message, _ = result
    assert message.hid_op == cora.HID_OP_SEND_REPORT
    assert message.payload == bytes([0x03, 0x08, 100])


def test_read_returns_input_report_matching_real_key_press() -> None:
    """Input payload is a real key-0-press capture from the user's hardware.

    Verified both at the TCPTransportDevice.read() level and, via a real
    StreamDeckPlus wrapping this device, all the way through
    StreamDeckPlus._read_control_states().

    Wire payload layout for one CORA input-event message on the deck's own
    connection, confirmed against `tests/fixtures/cora_live_capture.json`'s
    `input_event_key_press_full_message_payload` (captured live: this
    session's first attempt used a synthetic payload shaped one byte off
    from reality -- StreamDeckPlus's own `states = states[1:]` strip expects
    `payload[0]` itself, not an extra tunnel byte on top of it -- and it
    took a real key press to catch that `TCPTransportDevice.read()` must
    return `payload[0:length]`, not `payload[1:1+length]`):

        payload[0]  = 0x01 -- CORA "input event" class byte. This IS the
                      same HID report-ID-like byte `StreamDeckPlus` strips
                      via its own `states = states[1:]` -- TCPTransportDevice
                      must NOT strip it again.
        payload[1]  = states[0] after that strip -- event-type discriminator;
                      0x00 == key event.
        payload[2:4] = states[1:3] -- unused for a key event.
        payload[4:12] = states[3:11] -- the 8 key states StreamDeckPlus turns
                      into `[bool(s) for s in states[3:11]]`. Key index 0 is
                      pressed here (payload[4] == 1).
        payload[12:14] = states[11:13] -- unused for a key event.
    """
    key_press_payload = bytes.fromhex(FIXTURES["input_event_key_press_full_message_payload"])

    def play_deck_input_event(sock: socket.socket) -> None:
        message = cora.CoraMessage(
            flags=cora.FLAG_VERBATIM,
            hid_op=cora.HID_OP_WRITE,
            message_id=0,
            payload=key_press_payload,
        )
        sock.sendall(cora.encode_message(message))
        sock.sendall(cora.encode_message(message))
        time.sleep(0.3)

    connector = ScriptedConnector(play_dock(), play_deck_input_event)
    device = TCPTransportDevice("192.0.2.1", connect=connector)
    device.open()

    raw = None
    for _ in range(30):
        raw = device.read(14)
        if raw is not None:
            break
        time.sleep(0.05)

    assert raw is not None
    assert len(raw) == 14  # noqa: PLR2004
    assert raw[0] == 0x01  # CORA input-event class byte, stripped by StreamDeckPlus itself
    assert raw[1] == 0x00  # states[0] after StreamDeckPlus's own strip: key event

    deck = StreamDeckPlus(device)
    control_states = None
    for _ in range(30):
        control_states = deck._read_control_states()
        if control_states is not None:
            break
        time.sleep(0.05)

    device.close()
    connector.join_all()

    assert control_states == {
        ControlType.KEY: [True, False, False, False, False, False, False, False],
    }


def test_read_returns_none_when_no_data_available() -> None:
    """read() returns None (not an error) when no input report has arrived yet."""
    connector = ScriptedConnector(play_dock(), lambda _sock: time.sleep(0.3))
    device = TCPTransportDevice("192.0.2.1", connect=connector)
    device.open()
    result = device.read(14)
    device.close()
    connector.join_all()
    assert result is None


def test_open_raises_transport_error_when_dock_has_no_child_plugged_in() -> None:
    """open() raises TransportError when the dock reports nothing plugged in."""

    def play_dock_no_child(sock: socket.socket) -> None:
        request = sock.recv(4096)
        result = cora.decode_message(request)
        assert result is not None
        message, _ = result
        no_child_payload = bytearray(128)
        no_child_payload[4] = 0x00  # not OK -- nothing plugged in
        response = cora.CoraMessage(
            flags=cora.FLAG_NONE,
            hid_op=message.hid_op,
            message_id=message.message_id,
            payload=bytes(no_child_payload),
        )
        sock.sendall(cora.encode_message(response))
        sock.close()

    connector = ScriptedConnector(play_dock_no_child)
    device = TCPTransportDevice("192.0.2.1", connect=connector)

    import pytest
    from StreamDeck.Transport.Transport import TransportError

    with pytest.raises(TransportError):
        device.open()
    connector.join_all()
