"""CORA framing for the Elgato Network Dock's TCP protocol.

Ported from @elgato-stream-deck/tcp (MIT License, Copyright Julian Waller),
https://github.com/Julusian/node-elgato-stream-deck,
packages/tcp/src/socketWrapper.ts (frame codec) and
packages/tcp/src/hid-device/cora.ts (keepalive/command semantics).

Byte layouts below were confirmed against real hardware (a Stream Deck+
connected through an Elgato Network Dock) -- see
docs/superpowers/specs/2026-08-28-network-dock-transport-design.md and
tests/fixtures/cora_live_capture.json.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

CORA_MAGIC = bytes([0x43, 0x93, 0x8A, 0x41])

# CoraHidOp
HID_OP_WRITE = 0x00  # hid_write
HID_OP_SEND_REPORT = 0x01  # hid_send_feature_report
HID_OP_GET_REPORT = 0x02  # hid_get_feature_report

# CoraMessageFlags
FLAG_NONE = 0x0000
FLAG_RESULT = 0x0100  # In - response to a GET_REPORT op
FLAG_ACK_NAK = 0x0200  # In - response to a keepalive (REQ_ACK)
FLAG_REQ_ACK = 0x4000  # Out - host requests an ACK
FLAG_VERBATIM = 0x8000  # In/Out - payload is for the child/secondary HID device

# 16-byte header: magic(4s) flags(H) hidOp(B) pad(x) messageId(I) payloadLength(I)
_HEADER = struct.Struct("<4sHBxII")

# CORA payload class/sub-type bytes (payload[0]/payload[1]) relevant to
# hid_op WRITE messages on a deck's own connection.
_PAYLOAD_CLASS_INPUT_EVENT = 0x01  # unsolicited input, or a keepalive
_KEEPALIVE_SUBTYPE = 0x0A
_KEEPALIVE_MIN_LEN = 6  # need payload[5] for build_keepalive_ack's connection number

_DEVICE2_INFO_MIN_LEN = 128
_DEVICE2_INFO_OK = 0x02  # payload[4]: something is plugged in / query OK


@dataclass(frozen=True)
class CoraMessage:
    """One decoded CORA frame: header fields plus its payload."""

    flags: int
    hid_op: int
    message_id: int
    payload: bytes


def encode_message(message: CoraMessage) -> bytes:
    """Encode a CoraMessage as the 16-byte header plus its payload, ready to write to the wire."""
    header = _HEADER.pack(
        CORA_MAGIC,
        message.flags,
        message.hid_op,
        message.message_id,
        len(message.payload),
    )
    return header + message.payload


def decode_message(buf: bytes) -> tuple[CoraMessage, int] | None:
    """Find and decode one CORA message in `buf`.

    Returns `(message, bytes_consumed_from_start_of_buf)`, or `None` if
    `buf` does not (yet) contain a complete message. `bytes_consumed`
    includes any garbage bytes before the magic, which should be discarded
    by the caller along with the message itself.
    """
    idx = buf.find(CORA_MAGIC)
    if idx == -1:
        return None
    if len(buf) - idx < _HEADER.size:
        return None
    payload_length = struct.unpack_from("<I", buf, idx + 12)[0]
    end = idx + _HEADER.size + payload_length
    if len(buf) < end:
        return None
    flags, hid_op, message_id = struct.unpack_from("<HBxI", buf, idx + 4)
    payload = buf[idx + _HEADER.size : end]
    message = CoraMessage(flags=flags, hid_op=hid_op, message_id=message_id, payload=payload)
    return message, end


def is_keepalive(payload: bytes) -> bool:
    """True if this CORA payload is an unsolicited dock keepalive needing an ack.

    Length must be `> _KEEPALIVE_MIN_LEN - 1` (i.e. a byte at index 5 must
    exist): build_keepalive_ack() reads payload[5], so a payload that
    doesn't have a byte there must not be admitted here.
    """
    return (
        len(payload) >= _KEEPALIVE_MIN_LEN
        and payload[0] == _PAYLOAD_CLASS_INPUT_EVENT
        and payload[1] == _KEEPALIVE_SUBTYPE
    )


def build_keepalive_ack(message: CoraMessage) -> CoraMessage:
    """Build the ack CORA message a keepalive from the dock expects in response."""
    ack_payload = bytearray(32)
    ack_payload[0] = 3
    ack_payload[1] = 26
    ack_payload[2] = message.payload[5]  # echoed connection number
    return CoraMessage(
        flags=FLAG_ACK_NAK,
        hid_op=message.hid_op,
        message_id=message.message_id,
        payload=bytes(ack_payload),
    )


@dataclass(frozen=True)
class Device2Info:
    """Identity of the Stream Deck plugged into a Network Dock, plus its own TCP port."""

    vendor_id: int
    product_id: int
    serial_number: str
    tcp_port: int


def parse_device2_info(payload: bytes) -> Device2Info | None:
    """Parse the response to a 0x1c "Device 2 info" query.

    Byte offsets ported from device2Info.ts, confirmed live: byte[4] must
    be 0x02 (something is plugged in / query OK); vendor/product IDs and
    the TCP port to reach that device are little-endian uint16s; the
    serial number is a NUL-terminated ASCII string.
    """
    if len(payload) < _DEVICE2_INFO_MIN_LEN or payload[4] != _DEVICE2_INFO_OK:
        return None
    vendor_id = struct.unpack_from("<H", payload, 26)[0]
    product_id = struct.unpack_from("<H", payload, 28)[0]
    serial_number = payload[94:125].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    tcp_port = struct.unpack_from("<H", payload, 126)[0]
    return Device2Info(
        vendor_id=vendor_id,
        product_id=product_id,
        serial_number=serial_number,
        tcp_port=tcp_port,
    )


def build_get_report_command(command_type: int, *, to_host: bool, message_id: int) -> CoraMessage:
    """Build a GET_REPORT-style query.

    `to_host=True` asks the far end of *this* connection about itself
    (used against the dock's own port-5343 connection for the 0x1c
    Device-2-info query). `to_host=False` asks about the device this
    connection reaches directly (used against the deck's own connection
    for report IDs like 0x05/0x06/0x08).
    """
    if to_host:
        return CoraMessage(
            flags=FLAG_NONE,
            hid_op=HID_OP_GET_REPORT,
            message_id=message_id,
            payload=bytes([0x03, command_type]),
        )
    return CoraMessage(
        flags=FLAG_VERBATIM,
        hid_op=HID_OP_GET_REPORT,
        message_id=message_id,
        payload=bytes([command_type]),
    )


def build_write_message(payload: bytes) -> CoraMessage:
    """Build a CoraMessage wrapping `payload` as a hid_write (HID_OP_WRITE)."""
    return CoraMessage(
        flags=FLAG_VERBATIM,
        hid_op=HID_OP_WRITE,
        message_id=0,
        payload=bytes(payload),
    )


def build_send_report_message(payload: bytes) -> CoraMessage:
    """Build a CoraMessage wrapping `payload` as a hid_send_feature_report (HID_OP_SEND_REPORT)."""
    return CoraMessage(
        flags=FLAG_VERBATIM,
        hid_op=HID_OP_SEND_REPORT,
        message_id=0,
        payload=bytes(payload),
    )


def repack_feature_report(payload: bytes, *, report_id: int, length: int) -> bytes:
    """Repack a CORA GET_REPORT response into the byte layout expected from a real USB HID feature report.

    `python-elgato-streamdeck`'s `StreamDeckPlus` expects report ID at
    offset 0 and data starting at offset 5.

    The CORA payload is `[echoed_report_id, length_byte, data...]` (data
    starting at offset 2) -- confirmed live for both report 0x06 (serial
    number, pure ASCII data) and report 0x05 (firmware version, 4 binary
    bytes followed by an ASCII version string). This is a fixed byte-shift
    of whatever data follows the CORA header, not a string-specific
    extraction -- it works without needing to know what the data means.
    """
    result = bytearray(length)
    if len(payload) > 0:
        result[0] = report_id
    data = payload[2:]
    copy_len = max(min(len(data), length - 5), 0)
    if copy_len > 0:
        result[5 : 5 + copy_len] = data[:copy_len]
    return bytes(result)


def is_input_event(payload: bytes) -> bool:
    """True if this CORA payload is an unsolicited key/dial/touch input report.

    That is: not a keepalive and not a response to a GET_REPORT query.

    Scoped to a single deck's own connection: the `0x01 0x0B` Device-2
    plug-event case (relevant only on a dock's own primary connection,
    used solely during the one-shot handshake in device.py) never reaches
    this function, so it doesn't need to be distinguished here.
    """
    return (
        len(payload) > 1
        and payload[0] == _PAYLOAD_CLASS_INPUT_EVENT
        and payload[1] != _KEEPALIVE_SUBTYPE
    )
