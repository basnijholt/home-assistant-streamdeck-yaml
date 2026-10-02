"""Tests for CORA frame encode/decode, verified against real hardware capture."""

import json
from pathlib import Path

from streamdeck_tcp import cora

FIXTURES = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "cora_live_capture.json").read_text(),
)


def test_decode_message_parses_real_keepalive() -> None:
    """A live-captured keepalive frame decodes into its header fields and payload."""
    buf = bytes.fromhex(FIXTURES["dock_first_bytes"])
    result = cora.decode_message(buf)
    assert result is not None
    message, consumed = result
    assert message.flags == 0
    assert message.hid_op == 0
    assert message.message_id == 0
    assert len(message.payload) == 512  # noqa: PLR2004
    assert cora.is_keepalive(message.payload)
    assert consumed == len(buf)


def test_decode_message_returns_none_for_incomplete_buffer() -> None:
    """A truncated buffer (shorter than the 16-byte header) is not yet decodable."""
    buf = bytes.fromhex(FIXTURES["dock_first_bytes"])[:10]
    assert cora.decode_message(buf) is None


def test_decode_message_skips_leading_garbage_before_magic() -> None:
    """Bytes before the CORA magic are counted as consumed along with the message."""
    buf = b"\x00\x01\x02" + bytes.fromhex(FIXTURES["dock_first_bytes"])
    result = cora.decode_message(buf)
    assert result is not None
    _, consumed = result
    assert consumed == len(buf)


def test_encode_message_round_trips() -> None:
    """encode_message() followed by decode_message() reproduces the original message."""
    original = cora.CoraMessage(
        flags=cora.FLAG_VERBATIM,
        hid_op=cora.HID_OP_WRITE,
        message_id=42,
        payload=b"hello",
    )
    encoded = cora.encode_message(original)
    result = cora.decode_message(encoded)
    assert result is not None
    decoded, consumed = result
    assert decoded == original
    assert consumed == len(encoded)


def test_build_keepalive_ack_echoes_connection_number_and_ids() -> None:
    """The ack echoes the keepalive's hid_op/message_id and its connection number byte."""
    buf = bytes.fromhex(FIXTURES["dock_first_bytes"])
    result = cora.decode_message(buf)
    assert result is not None
    message, _ = result
    ack = cora.build_keepalive_ack(message)
    assert ack.flags == cora.FLAG_ACK_NAK
    assert ack.hid_op == message.hid_op
    assert ack.message_id == message.message_id
    assert len(ack.payload) == 32  # noqa: PLR2004
    assert ack.payload[0] == 3  # noqa: PLR2004
    assert ack.payload[1] == 26  # noqa: PLR2004
    assert ack.payload[2] == message.payload[5]


def test_is_keepalive_false_for_short_payload() -> None:
    """A payload too short to contain the connection-number byte is never a keepalive."""
    assert cora.is_keepalive(b"\x01\x0a") is False


def test_is_keepalive_false_for_non_keepalive_payload() -> None:
    """A payload with the wrong class/sub-type bytes is not a keepalive."""
    assert cora.is_keepalive(bytes([0x06, 0x0C]) + b"\x00" * 30) is False


def test_parse_device2_info_from_live_capture() -> None:
    """A live-captured device2Info response parses into the expected identity fields."""
    payload = bytes.fromhex(FIXTURES["device2info_full_message_payload"])
    info = cora.parse_device2_info(payload)
    assert info == cora.Device2Info(
        vendor_id=4057,
        product_id=132,
        serial_number="EL51L1A00456",
        tcp_port=20001,
    )


def test_parse_device2_info_returns_none_when_status_byte_not_ok() -> None:
    """A status byte other than 0x02 (nothing plugged in) yields None."""
    payload = bytearray(bytes.fromhex(FIXTURES["device2info_full_message_payload"]))
    payload[4] = 0x00
    assert cora.parse_device2_info(bytes(payload)) is None


def test_parse_device2_info_returns_none_for_short_payload() -> None:
    """A payload shorter than the fixed device2Info layout yields None."""
    assert cora.parse_device2_info(b"\x00\x00\x00\x00") is None


def test_repack_feature_report_serial_number() -> None:
    """A live-captured serial-number feature report repacks with report ID and ASCII data."""
    payload = bytes.fromhex(FIXTURES["serial_report_full_payload"])
    result = cora.repack_feature_report(payload, report_id=0x06, length=32)
    assert len(result) == 32  # noqa: PLR2004
    assert result[0] == 0x06  # noqa: PLR2004
    serial = result[5:].split(b"\x00", 1)[0]
    assert serial == b"EL51L1A00456"


def test_repack_feature_report_firmware_version() -> None:
    """A live-captured firmware-version feature report repacks with report ID and version string."""
    payload = bytes.fromhex(FIXTURES["firmware_report_full_payload"])
    result = cora.repack_feature_report(payload, report_id=0x05, length=32)
    assert len(result) == 32  # noqa: PLR2004
    assert result[0] == 0x05  # noqa: PLR2004
    assert b"2.0.3.4" in result[5:]


def test_repack_feature_report_truncates_to_requested_length() -> None:
    """The repacked report is truncated to the caller-requested length."""
    payload = bytes.fromhex(FIXTURES["serial_report_full_payload"])
    result = cora.repack_feature_report(payload, report_id=0x06, length=8)
    assert len(result) == 8  # noqa: PLR2004
    assert result[0] == 0x06  # noqa: PLR2004


def test_build_get_report_command_to_host() -> None:
    """to_host=True wraps the command type for the dock's own hid_get_feature_report query."""
    msg = cora.build_get_report_command(0x1C, to_host=True, message_id=99)
    assert msg.flags == cora.FLAG_NONE
    assert msg.hid_op == cora.HID_OP_GET_REPORT
    assert msg.message_id == 99  # noqa: PLR2004
    assert msg.payload == bytes([0x03, 0x1C])


def test_build_get_report_command_not_to_host() -> None:
    """to_host=False wraps the command type verbatim for the deck's own connection."""
    msg = cora.build_get_report_command(0x06, to_host=False, message_id=99)
    assert msg.flags == cora.FLAG_VERBATIM
    assert msg.payload == bytes([0x06])


def test_build_write_message() -> None:
    """build_write_message() wraps its payload as a verbatim hid_write."""
    msg = cora.build_write_message(b"\x02\xaa\xbb")
    assert msg.hid_op == cora.HID_OP_WRITE
    assert msg.flags == cora.FLAG_VERBATIM
    assert msg.payload == b"\x02\xaa\xbb"


def test_build_send_report_message() -> None:
    """build_send_report_message() wraps its payload as a verbatim hid_send_feature_report."""
    msg = cora.build_send_report_message(b"\x03\x08\x64")
    assert msg.hid_op == cora.HID_OP_SEND_REPORT
    assert msg.flags == cora.FLAG_VERBATIM
    assert msg.payload == b"\x03\x08\x64"


def test_is_input_event_true_for_key_event_shaped_payload() -> None:
    """A payload with the input-event class byte and a non-keepalive sub-type is an input event."""
    assert cora.is_input_event(bytes([0x01, 0x00, 0x00, 0x00])) is True


def test_is_input_event_false_for_keepalive() -> None:
    """A keepalive payload is never treated as an input event."""
    payload = bytes.fromhex(FIXTURES["dock_first_bytes"])[16:]
    assert cora.is_input_event(payload) is False


def test_is_input_event_false_for_feature_report_response() -> None:
    """A GET_REPORT response payload is never treated as an input event."""
    payload = bytes.fromhex(FIXTURES["serial_report_full_payload"])
    assert cora.is_input_event(payload) is False
