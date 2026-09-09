"""Small human and JSON command surface."""

import argparse
import json
import math
import sys

from . import __version__
from .client import read_info, read_status
from .config import controller_url, load_inventory, resolve_device
from .discovery import discover, inspect_device


def positive_timeout(value):
    result = float(value)
    if not math.isfinite(result) or not 0 < result <= 60:
        raise argparse.ArgumentTypeError("timeout must be greater than zero and at most 60 seconds")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tiny local Serin mini-split inspection CLI")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--host", help="controller hostname or IP (optional port)")
    parser.add_argument("--config", help="private JSON config path")
    parser.add_argument("--timeout", type=positive_timeout, default=5)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor"):
        command = commands.add_parser(name)
        command.add_argument("device", nargs="?", help="exact configured device ID")
        command.add_argument("--json", action="store_true")
        command.add_argument(
            "--show-identity", action="store_true", help="include private configured identity"
        )
    listing = commands.add_parser(
        "devices", help="list private configured devices without contacting them"
    )
    listing.add_argument("--json", action="store_true")
    finding = commands.add_parser(
        "discover", help="find a configured controller by its hardware MAC"
    )
    finding.add_argument("device", nargs="?")
    finding.add_argument("--network", help="explicit private IPv4 range, at most /24")
    finding.add_argument("--json", action="store_true")
    inspecting = commands.add_parser(
        "inspect", help="read private hardware metadata at an explicit host"
    )
    inspecting.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            if args.host is None:
                raise ValueError("inspect requires --host for initial identity enrollment")
            result = read_info(controller_url(args.host), args.timeout)
            if args.json:
                print(json.dumps(result))
            else:
                for key, value in result.items():
                    print(f"{key}: {value}")
            return 0
        if args.command == "devices":
            if args.host is not None:
                raise ValueError("devices requires inventory, not --host")
            devices, rooms = load_inventory(args.config)
            if args.json:
                print(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "devices": [d.identity() for d in devices],
                            "rooms": rooms,
                        }
                    )
                )
            else:
                room_names = {r["id"]: r["name"] for r in rooms}
                for device in devices:
                    print(
                        f"{device.id or '(legacy)'} · {device.name or 'Unnamed controller'} · {room_names.get(device.room_id, 'Room unassigned')}"
                    )
            return 0
        device = resolve_device(args.host, args.config, args.device)
        if args.command == "discover":
            result = discover(device, min(args.timeout, 2), args.network)
            if args.json:
                print(json.dumps(result))
            else:
                print(
                    f"Verified {device.id}: {result['endpoint']} · {result['hardware']['board']} · {result['hardware']['fw']}"
                )
            return 0
        state = (
            inspect_device(device, args.timeout)
            if device.mac
            else read_status(controller_url(device.host), args.timeout)
        )
        if args.show_identity:
            state = {**state, "device": device.identity()}
            if not args.json:
                print(
                    f"{device.id or '(direct)'} · {device.name or 'Unnamed controller'} · room: {device.room_id or 'unassigned'}"
                )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"schema_version": 1, "error": str(exc)}))
        else:
            print(f"serinctl: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(state, allow_nan=False))
    elif not state["heat_pump_connected"]:
        print("Controller reachable · heat pump disconnected · equipment state unknown")
    else:

        def display(value):
            return "unknown" if value is None else str(value)

        power = {True: "on", False: "off", None: "unknown"}[state["power"]]
        print(f"Heat pump connected · power {power} · mode {display(state['mode'])}")
        print(f"Room {display(state['room_c'])} °C · target {display(state['target_c'])} °C")
    return 0 if state["heat_pump_connected"] else 2
