"""Tests for the pure mDNS TXT-record filter.

discover_first_dock() itself does real network I/O and is covered by live
verification, not unit tests.
"""

from streamdeck_tcp.discovery import DiscoveredDock, txt_record_to_discovered_dock


def test_txt_record_to_discovered_dock_matches_network_dock() -> None:
    """A `dt=215` service with a serial number parses into a DiscoveredDock."""
    dock = txt_record_to_discovered_dock(
        name="My Dock._elg._tcp.local.",
        address="100.127.252.150",
        port=5343,
        properties={b"dt": b"215", b"sn": b"EL51L1A00456"},
    )
    assert dock == DiscoveredDock(
        address="100.127.252.150",
        port=5343,
        serial_number="EL51L1A00456",
        name="My Dock._elg._tcp.local.",
    )


def test_txt_record_to_discovered_dock_ignores_non_dock_device_types() -> None:
    """A `dt` value other than 215 (not a Network Dock) returns None."""
    dock = txt_record_to_discovered_dock(
        name="Some Deck._elg._tcp.local.",
        address="100.127.252.151",
        port=5343,
        properties={b"dt": b"200"},
    )
    assert dock is None


def test_txt_record_to_discovered_dock_returns_none_when_dt_missing() -> None:
    """A service with no `dt` TXT record property returns None."""
    dock = txt_record_to_discovered_dock(
        name="x",
        address="1.2.3.4",
        port=1,
        properties={},
    )
    assert dock is None


def test_txt_record_to_discovered_dock_handles_missing_serial() -> None:
    """A Network Dock with no `sn` TXT record property gets serial_number=None."""
    dock = txt_record_to_discovered_dock(
        name="Dock",
        address="1.2.3.4",
        port=5343,
        properties={b"dt": b"215"},
    )
    assert dock == DiscoveredDock(address="1.2.3.4", port=5343, serial_number=None, name="Dock")
