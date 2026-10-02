"""Read-only diagnostic for a Stream Deck+ on an Elgato Network Dock.

Discovers the dock via mDNS (or connects to a given address), fetches
device2Info, connects to the deck's own port, and prints its identity and
serial/firmware feature reports. Does not write key images or press
buttons -- safe to run against a deck in normal use.

Usage: python3 scripts/probe_network_dock.py [dock-ip]
       (with no argument, uses mDNS discovery)
"""

from __future__ import annotations

import sys

from streamdeck_tcp.device import TCPTransportDevice
from streamdeck_tcp.discovery import discover_first_dock


def main() -> None:
    """Connect to a Network Dock (mDNS-discovered or given by IP) and print its identity and input events."""
    if len(sys.argv) > 1:
        host = sys.argv[1]
        print(f"Using configured address {host}:5343")
    else:
        print("Discovering Network Dock via mDNS (up to 10s)...")
        dock = discover_first_dock()
        if dock is None:
            print("No Network Dock found via mDNS. Pass an IP address explicitly.")
            sys.exit(1)
        host = dock.address
        print(f"Discovered dock at {host}:{dock.port} (serial {dock.serial_number})")

    device = TCPTransportDevice(host)
    device.open()
    try:
        print(f"vendor_id=0x{device.vendor_id():04x} product_id=0x{device.product_id():04x}")
        serial = device.read_feature(0x06, 32)
        print(f"serial: {serial[5:].split(bytes([0]), 1)[0].decode('ascii', 'replace')!r}")
        firmware = device.read_feature(0x05, 32)
        print(f"firmware bytes: {firmware[5:].split(bytes([0]), 1)[0]!r}")
        print("Reading input events for 5 seconds -- press a key/dial/touch on the deck now...")
        import time

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            report = device.read(14)
            if report is not None:
                print(f"input report: {report.hex(' ')}")
    finally:
        device.close()


if __name__ == "__main__":
    main()
