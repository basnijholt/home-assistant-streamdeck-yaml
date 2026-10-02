"""Tests for get_deck()'s USB-then-network fallback logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from home_assistant_streamdeck_yaml import Config, get_deck
from streamdeck_tcp.discovery import DiscoveredDock

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class _EmptyDeviceManager:
    """Stand-in for DeviceManager that finds no USB-connected Stream Deck."""

    def enumerate(self) -> list[Any]:
        """Return no devices, forcing get_deck() onto the network path."""
        return []


class _FakeStreamDeckPlus:
    """Stand-in for StreamDeckPlus that records open()/reset() without touching hardware."""

    def __init__(self, device: Any) -> None:
        """Store the transport device and initialize open/reset tracking flags."""
        self.device = device
        self._opened = False
        self._reset = False

    def open(self) -> None:
        """Record that open() was called."""
        self._opened = True

    def reset(self) -> None:
        """Record that reset() was called."""
        self._reset = True

    def is_visual(self) -> bool:
        """Report as a visual (key-bearing) device, matching the real StreamDeckPlus."""
        return True

    def key_count(self) -> int:
        """Report the Stream Deck+'s real key count."""
        return 8


def test_get_deck_uses_configured_static_address_without_discovery(
    monkeypatch: MonkeyPatch,
) -> None:
    """A configured streamdeck_address skips mDNS discovery entirely."""
    monkeypatch.setattr("home_assistant_streamdeck_yaml.DeviceManager", _EmptyDeviceManager)

    def fail_discovery(_timeout: float = 10.0) -> None:
        msg = "discovery should not run when a static address is configured"
        raise AssertionError(msg)

    monkeypatch.setattr("streamdeck_tcp.discovery.discover_first_dock", fail_discovery)

    created: dict[str, str | int] = {}

    class _FakeTCPTransportDevice:
        def __init__(self, host: str, dock_port: int) -> None:
            created["host"] = host
            created["dock_port"] = dock_port

    monkeypatch.setattr("streamdeck_tcp.device.TCPTransportDevice", _FakeTCPTransportDevice)
    monkeypatch.setattr("home_assistant_streamdeck_yaml.StreamDeckPlus", _FakeStreamDeckPlus)

    config = Config(streamdeck_address="192.0.2.9", streamdeck_port=1234)
    deck = get_deck(config)

    assert created == {"host": "192.0.2.9", "dock_port": 1234}
    assert isinstance(deck, _FakeStreamDeckPlus)
    assert deck._opened is True
    assert deck._reset is True


def test_get_deck_falls_back_to_mdns_discovery_when_no_static_address(
    monkeypatch: MonkeyPatch,
) -> None:
    """No static address configured falls back to mDNS discovery."""
    monkeypatch.setattr("home_assistant_streamdeck_yaml.DeviceManager", _EmptyDeviceManager)

    fake_dock = DiscoveredDock(address="192.0.2.5", port=5343, serial_number="X", name="dock")
    monkeypatch.setattr(
        "streamdeck_tcp.discovery.discover_first_dock",
        lambda _timeout=10.0: fake_dock,
    )

    created: dict[str, str | int] = {}

    class _FakeTCPTransportDevice:
        def __init__(self, host: str, dock_port: int) -> None:
            created["host"] = host
            created["dock_port"] = dock_port

    monkeypatch.setattr("streamdeck_tcp.device.TCPTransportDevice", _FakeTCPTransportDevice)
    monkeypatch.setattr("home_assistant_streamdeck_yaml.StreamDeckPlus", _FakeStreamDeckPlus)

    config = Config(streamdeck_address=None)
    deck = get_deck(config)

    assert created == {"host": "192.0.2.5", "dock_port": 5343}
    assert isinstance(deck, _FakeStreamDeckPlus)


def test_get_deck_raises_when_nothing_found(monkeypatch: MonkeyPatch) -> None:
    """No USB device, no static address, and no mDNS discovery raises RuntimeError."""
    monkeypatch.setattr("home_assistant_streamdeck_yaml.DeviceManager", _EmptyDeviceManager)
    monkeypatch.setattr(
        "streamdeck_tcp.discovery.discover_first_dock",
        lambda _timeout=10.0: None,
    )

    config = Config(streamdeck_address=None)
    with pytest.raises(RuntimeError, match="No Stream Deck found"):
        get_deck(config)
