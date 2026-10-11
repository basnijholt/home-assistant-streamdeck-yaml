"""mDNS discovery for the Elgato Network Dock.

Service type and TXT record layout ported from @elgato-stream-deck/tcp
(MIT License, Copyright Julian Waller), discoveryService.ts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

SERVICE_TYPE = "_elg._tcp.local."
NETWORK_DOCK_DEVICE_TYPE = "215"
DEFAULT_PORT = 5343


@dataclass(frozen=True)
class DiscoveredDock:
    """An Elgato Network Dock found via mDNS."""

    address: str
    port: int
    serial_number: str | None
    name: str


def txt_record_to_discovered_dock(
    *,
    name: str,
    address: str,
    port: int,
    properties: dict[bytes, bytes | None],
) -> DiscoveredDock | None:
    """Pure filter/transform from mDNS service info to a DiscoveredDock, or None if it isn't a Network Dock."""
    device_type = properties.get(b"dt")
    if device_type is None or device_type.decode("ascii", "replace") != NETWORK_DOCK_DEVICE_TYPE:
        return None
    serial_raw = properties.get(b"sn")
    serial_number = serial_raw.decode("ascii", "replace") if serial_raw else None
    return DiscoveredDock(address=address, port=port, serial_number=serial_number, name=name)


def discover_first_dock(timeout: float = 10.0) -> DiscoveredDock | None:
    """Browse mDNS for up to `timeout` seconds.

    Returns the first Network Dock found, or `None` if none responded in
    time.
    """
    found: list[DiscoveredDock] = []

    def on_change(
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if state_change != ServiceStateChange.Added or found:
            return
        info = zeroconf.get_service_info(service_type, name)
        if info is None:
            return
        addresses = info.parsed_addresses()
        if not addresses or info.port is None:
            return
        dock = txt_record_to_discovered_dock(
            name=name,
            address=addresses[0],
            port=info.port,
            properties=info.properties,
        )
        if dock is not None:
            found.append(dock)

    zeroconf = Zeroconf()
    try:
        ServiceBrowser(zeroconf, SERVICE_TYPE, handlers=[on_change])
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not found:
            time.sleep(0.1)
    finally:
        zeroconf.close()
    return found[0] if found else None
