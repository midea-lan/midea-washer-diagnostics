"""Select supported Midea LAN devices for the local read-only home monitor."""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from midealocal.const import ProtocolVersion
from midealocal.discover import discover
from midealocal.devices import device_selector


def supported(device: dict[str, object]) -> bool:
    """Return whether midea-local has a parser registered for this device type."""
    try:
        device_type = int(device["type"])
        protocol = int(device["protocol"])
        return device_selector(
            name=str(device.get("device_id", "")),
            device_id=int(device["device_id"]),
            device_type=device_type,
            ip_address=str(device["ip_address"]),
            port=int(device["port"]),
            token="",
            key="",
            device_protocol=ProtocolVersion(protocol),
            model=str(device.get("model", "")),
            subtype=int(device.get("subtype", 0)),
            mac=device.get("mac") if isinstance(device.get("mac"), str) else None,
            serial_number=device.get("sn") if isinstance(device.get("sn"), str) else None,
        ) is not None
    except (KeyError, TypeError, ValueError):
        return False


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("home_devices.json"))
    args = parser.parse_args()

    found = await discover()
    devices = [device for device in found.values() if supported(device)]
    if not devices:
        raise SystemExit("No devices with a registered midea-local parser were found.")

    print("Select one or more discovered devices. Enter comma-separated numbers, or 'all'.")
    for index, device in enumerate(devices, 1):
        print(
            f"{index}. type=0x{int(device['type']):02X} protocol={device['protocol']} "
            f"model={device.get('model') or 'unknown'} IP={device['ip_address']}"
        )
    try:
        selection = input("Selection: ").strip().lower()
        if selection == "all":
            selected = devices
        else:
            indices = [int(part.strip()) for part in selection.split(",")]
            if not indices or len(set(indices)) != len(indices):
                raise ValueError
            if any(index < 1 or index > len(devices) for index in indices):
                raise ValueError
            selected = [devices[index - 1] for index in indices]
    except (ValueError, EOFError) as exc:
        raise SystemExit("Enter valid device numbers, such as 1,3, or all.") from exc

    payload = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scan": "broadcast_user_selected_supported_types",
        "devices": selected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(selected)} local device identities to {args.output}. Keep this file private.")


if __name__ == "__main__":
    asyncio.run(main())
