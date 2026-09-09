"""Private target selection. No discovery guesses or credential-bearing URLs."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


def controller_url(host: str) -> str:
    if not isinstance(host, str) or not host or any(c.isspace() for c in host):
        raise ValueError("controller host must be a hostname or IP, optionally with a port")
    try:
        parsed = urlsplit("//" + host)
        port = parsed.port
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or (port is not None and port < 1)
        ):
            raise ValueError
    except ValueError:
        raise ValueError(
            "controller host must be a hostname or IP, optionally with a port"
        ) from None
    return f"ws://{host}/ws"


@dataclass(frozen=True)
class Device:
    id: str | None
    name: str | None
    room_id: str | None
    host: str
    mac: str | None = None
    hostname: str | None = None

    def identity(self):
        return {"id": self.id, "name": self.name, "room_id": self.room_id}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        raise ValueError("IDs must be lowercase letters, numbers, hyphens, or underscores")
    return value


def label(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 128
        or any(not c.isprintable() for c in value)
    ):
        raise ValueError("names must be nonempty printable strings of at most 128 characters")
    return value


def load_inventory(config: str | None):
    path = Path(
        config or os.environ.get("SERINCTL_CONFIG", "/usr/local/config/serinctl/config.json")
    )
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        raise ValueError("provide --host or a valid private config file") from None
    if not isinstance(data, dict):
        raise ValueError("config must be an object")
    if "host" in data:
        if set(data) != {"host"}:
            raise ValueError("legacy host config cannot be mixed with inventory fields")
        controller_url(data["host"])
        return [Device(None, None, None, data["host"])], []
    if set(data) - {"version", "devices", "rooms"}:
        raise ValueError("unknown inventory fields")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("inventory version must be 1")
    rooms = data.get("rooms", [])
    entries = data.get("devices")
    if not isinstance(rooms, list) or not isinstance(entries, list) or not entries:
        raise ValueError("inventory requires a nonempty devices list and a rooms list")
    room_ids = set()
    for room in rooms:
        if not isinstance(room, dict) or set(room) != {"id", "name"}:
            raise ValueError("each room requires only id and name")
        room_id = identifier(room["id"])
        label(room["name"])
        if room_id in room_ids:
            raise ValueError("duplicate room ID")
        room_ids.add(room_id)
    devices = []
    ids = set()
    endpoints = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not {"id", "name", "room_id", "host"} <= set(entry)
            or set(entry) - {"id", "name", "room_id", "host", "mac", "hostname"}
        ):
            raise ValueError("each device requires id, name, room_id, and host")
        device_id = identifier(entry["id"])
        name = label(entry["name"])
        room_id = entry["room_id"]
        if room_id is not None and (not isinstance(room_id, str) or room_id not in room_ids):
            raise ValueError("device room_id must reference a room or be null")
        parsed = urlsplit(controller_url(entry["host"]))
        endpoint = (parsed.hostname, parsed.port or 80)
        if device_id in ids or endpoint in endpoints:
            raise ValueError("duplicate device ID or endpoint")
        ids.add(device_id)
        endpoints.add(endpoint)
        mac = entry.get("mac")
        if mac is not None:
            mac = normalize_mac(mac)
        hostname = entry.get("hostname")
        if hostname is not None:
            if not isinstance(hostname, str) or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}", hostname
            ):
                raise ValueError("hostname must be a DNS name")
        if mac is not None and any(d.mac == mac for d in devices):
            raise ValueError("duplicate hardware MAC")
        devices.append(Device(device_id, name, room_id, entry["host"], mac, hostname))
    return devices, rooms


def resolve_device(host: str | None, config: str | None, device_id: str | None = None):
    if host is not None:
        if device_id is not None:
            raise ValueError("--host cannot be combined with a device ID")
        controller_url(host)
        return Device(None, None, None, host)
    devices, _ = load_inventory(config)
    if device_id is not None:
        for device in devices:
            if device.id == device_id:
                return device
        raise ValueError("unknown device ID; use devices to list configured IDs")
    if len(devices) != 1:
        raise ValueError("multiple devices configured; select an exact device ID")
    return devices[0]


def resolve_url(host: str | None, config: str | None) -> str:
    return controller_url(resolve_device(host, config).host)


def normalize_mac(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value
    ):
        raise ValueError("MAC must contain six colon-separated hexadecimal pairs")
    return value.upper()
