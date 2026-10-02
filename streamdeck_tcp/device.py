"""Transport.Device implementation for a Stream Deck+ over TCP.

Reached through an Elgato Network Dock (CORA framing), instead of USB HID.

Connection topology (dock port 5343 -> 0x1c query -> deck's own port) and
framing ported from @elgato-stream-deck/tcp (MIT License, Copyright Julian
Waller), confirmed against real hardware -- see
docs/superpowers/specs/2026-08-28-network-dock-transport-design.md.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import socket
import threading
import time
from typing import Callable

from StreamDeck.Transport.Transport import Transport, TransportError

from . import cora

logger = logging.getLogger(__name__)

DEFAULT_DOCK_PORT = 5343
_CONNECT_TIMEOUT = 5.0
_HANDSHAKE_TIMEOUT = 5.0
_RECV_SIZE = 4096
_SOCKET_POLL_TIMEOUT = 0.5
_READ_POLL_TIMEOUT = 0.1
_FEATURE_REPORT_TIMEOUT = 5.0


def _disable_nagle(sock: socket.socket) -> None:
    """Disable Nagle's algorithm so small, frequent CORA messages aren't delayed.

    This protocol is small-message and latency-sensitive (individual key/dial
    input reports, keepalives, per-chunk image writes) -- exactly the traffic
    shape Nagle's algorithm (combined with delayed ACKs) is known to stall by
    tens to hundreds of milliseconds per round trip. The JS reference
    implementation (@elgato-stream-deck/tcp's socketWrapper.ts) does the same
    (`socket.setNoDelay(true)`) for this reason.

    Best-effort: the test suite connects `TCPTransportDevice` over
    `socket.socketpair()` (AF_UNIX, not a real TCP socket), where
    `IPPROTO_TCP`/`TCP_NODELAY` isn't a valid socket option -- swallow that
    case rather than fail, since it's a real-network-only optimization.
    """
    with contextlib.suppress(OSError):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class TCPTransportDevice(Transport.Device):
    """A Stream Deck+ reached through an Elgato Network Dock over TCP."""

    def __init__(
        self,
        host: str,
        dock_port: int = DEFAULT_DOCK_PORT,
        *,
        connect: Callable[..., socket.socket] = socket.create_connection,
    ) -> None:
        """Store connection parameters; no I/O happens until open()."""
        self._host = host
        self._dock_port = dock_port
        self._connect = connect
        self._sock: socket.socket | None = None
        self._serial = ""
        self._vendor_id = 0
        self._product_id = 0
        self._recv_buffer = b""
        self._input_queue: queue.Queue[bytes] = queue.Queue()
        self._response_queues: dict[int, queue.Queue[bytes]] = {}
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._reader_failed = threading.Event()
        self._next_message_id = 0

    # -- Transport.Device --

    def open(self) -> None:
        """Query the dock for its plugged-in device, then connect to that device's own TCP port."""
        dock_sock = self._connect((self._host, self._dock_port), timeout=_CONNECT_TIMEOUT)
        _disable_nagle(dock_sock)
        try:
            payload, _ = self._synchronous_request(dock_sock, b"", 0x1C, to_host=True)
        finally:
            dock_sock.close()

        info = cora.parse_device2_info(payload)
        if info is None:
            msg = f"No Stream Deck found on Network Dock at {self._host}:{self._dock_port}"
            raise TransportError(msg)

        self._serial = info.serial_number
        self._vendor_id = info.vendor_id
        self._product_id = info.product_id

        self._sock = self._connect((self._host, info.tcp_port), timeout=_CONNECT_TIMEOUT)
        _disable_nagle(self._sock)
        self._sock.settimeout(_SOCKET_POLL_TIMEOUT)
        self._recv_buffer = b""
        self._stop.clear()
        self._reader_failed.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def close(self) -> None:
        """Stop the reader thread and close the socket. Safe to call more than once."""
        self._stop.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def is_open(self) -> bool:
        """True once open() has connected the deck's own socket."""
        return self._sock is not None

    def connected(self) -> bool:
        """True while open and the reader thread hasn't died unexpectedly or been asked to stop."""
        return (
            self._sock is not None and not self._stop.is_set() and not self._reader_failed.is_set()
        )

    def path(self) -> str:
        """A human-readable identifier for this connection, for logging/enumeration."""
        return f"tcp://{self._host}:{self._dock_port}"

    def vendor_id(self) -> int:
        """USB vendor ID of the Stream Deck, learned from the dock's device2Info response."""
        return self._vendor_id

    def product_id(self) -> int:
        """USB product ID of the Stream Deck, learned from the dock's device2Info response."""
        return self._product_id

    def write(self, payload: bytes | bytearray) -> int:
        """Send `payload` as a hid_write (e.g. a key/touchscreen image chunk)."""
        self._send(cora.build_write_message(bytes(payload)))
        return len(payload)

    def write_feature(self, payload: bytes | bytearray) -> int:
        """Send `payload` as a hid_send_feature_report (e.g. set_brightness, reset)."""
        self._send(cora.build_send_report_message(bytes(payload)))
        return len(payload)

    def read(self, length: int) -> bytes | None:
        """Return the next queued input report, or None if none is ready.

        Confirmed against real hardware: the CORA input-event marker byte at
        `payload[0]` (`0x01`) is itself the same HID report-ID-like byte
        `StreamDeckPlus._read_control_states()` strips via its own
        `states = states[1:]` -- it is not an extra tunnel byte on top of
        that. Returning `payload[1:1+length]` (stripping it here too) shifts
        every field by one byte, silently misclassifying every real key
        press, dial turn, and touch event. Must return `payload[0:length]`.
        """
        if self._reader_failed.is_set():
            msg = "Network Dock connection lost (reader thread exited unexpectedly)"
            raise TransportError(msg)
        try:
            payload = self._input_queue.get(timeout=_READ_POLL_TIMEOUT)
        except queue.Empty:
            return None
        return payload[0:length]

    def read_feature(self, report_id: int, length: int) -> bytes:
        """Request and return a hid_get_feature_report response for `report_id`."""
        response_queue: queue.Queue[bytes] = queue.Queue()
        with self._lock:
            self._response_queues[report_id] = response_queue
        try:
            message_id = self._allocate_message_id()
            request = cora.build_get_report_command(report_id, to_host=False, message_id=message_id)
            self._send(request)
            try:
                payload = response_queue.get(timeout=_FEATURE_REPORT_TIMEOUT)
            except queue.Empty as exc:
                msg = f"Timed out waiting for feature report 0x{report_id:02x}"
                raise TransportError(msg) from exc
        finally:
            with self._lock:
                self._response_queues.pop(report_id, None)
        return cora.repack_feature_report(payload, report_id=report_id, length=length)

    # -- internals --

    def _allocate_message_id(self) -> int:
        with self._lock:
            self._next_message_id += 1
            return self._next_message_id

    def _send(self, message: cora.CoraMessage) -> None:
        if self._sock is None:
            msg = "Device is not open"
            raise TransportError(msg)
        # Held for the full sendall() so the application thread (bursts of
        # key/touchscreen image writes) and the reader thread (keepalive
        # acks from _handle_message) can never interleave partial frames on
        # the wire. Deliberately NOT self._lock -- that one guards
        # _response_queues/_next_message_id bookkeeping and must stay free
        # for read_feature() to register while a write burst is in flight.
        with self._send_lock:
            try:
                self._sock.sendall(cora.encode_message(message))
            except OSError as exc:
                msg = "Failed to send data to Network Dock"
                raise TransportError(msg) from exc

    def _synchronous_request(
        self,
        sock: socket.socket,
        buf: bytes,
        command_type: int,
        *,
        to_host: bool,
    ) -> tuple[bytes, bytes]:
        """Blocking request/response used only during open()'s handshake.

        Runs before the background reader thread exists. Drains and acks
        any keepalives received while waiting for the real response.
        """
        message_id = self._allocate_message_id()
        sock.settimeout(_HANDSHAKE_TIMEOUT)
        sock.sendall(
            cora.encode_message(
                cora.build_get_report_command(command_type, to_host=to_host, message_id=message_id),
            ),
        )
        deadline = time.monotonic() + _HANDSHAKE_TIMEOUT
        while time.monotonic() < deadline:
            decoded = cora.decode_message(buf)
            if decoded is not None:
                message, consumed = decoded
                buf = buf[consumed:]
                if cora.is_keepalive(message.payload):
                    # Best-effort: this is a one-shot handshake and the peer
                    # may have already sent its real response and closed by
                    # the time we get here (both can arrive in the same
                    # recv()). Failing to deliver the ack must not abort a
                    # handshake whose real answer is already in `buf`.
                    with contextlib.suppress(OSError):
                        sock.sendall(cora.encode_message(cora.build_keepalive_ack(message)))
                    continue
                return message.payload, buf
            try:
                chunk = sock.recv(_RECV_SIZE)
            except TimeoutError:
                continue
            if not chunk:
                msg = "Connection closed during handshake"
                raise TransportError(msg)
            buf += chunk
        msg = f"Timed out waiting for response to command 0x{command_type:02x}"
        raise TransportError(msg)

    def _reader_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                chunk = self._sock.recv(_RECV_SIZE)
            except TimeoutError:
                continue
            except OSError:
                break
            if not chunk:
                break
            self._recv_buffer += chunk
            while True:
                decoded = cora.decode_message(self._recv_buffer)
                if decoded is None:
                    break
                message, consumed = decoded
                self._recv_buffer = self._recv_buffer[consumed:]
                try:
                    self._handle_message(message)
                except Exception:
                    # A single malformed/unexpected message must not kill
                    # the reader thread -- that would leave the transport
                    # silently deaf (see connected()/read()'s handling of
                    # self._reader_failed for genuine socket-level failures).
                    logger.exception("Error handling CORA message from Network Dock")
        if not self._stop.is_set():
            # The loop above only exits early (via `break`) on a genuine
            # socket-level failure; a deliberate close() sets self._stop
            # first, so that case is excluded here.
            self._reader_failed.set()

    def _handle_message(self, message: cora.CoraMessage) -> None:
        payload = message.payload
        if cora.is_keepalive(payload):
            self._send(cora.build_keepalive_ack(message))
            return
        if cora.is_input_event(payload):
            self._input_queue.put(payload)
            return
        if not payload:
            return
        report_id = payload[0]
        with self._lock:
            response_queue = self._response_queues.get(report_id)
        if response_queue is not None:
            response_queue.put(payload)
