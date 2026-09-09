"""Small human and JSON command surface."""

import argparse
import json
import math
import sys
import time

from . import __version__
from .client import read_info, read_status
from .config import controller_url, load_inventory, resolve_device
from .control import apply_settings, read_capabilities, watch_states
from .discovery import discover, inspect_device
from .protocol import FANS, MODES, VANES, WIDE_VANES, target_c

CONTROL_COMMANDS = {"heat", "cool", "temp", "power", "mode", "fan", "vane", "wide-vane", "set"}


def positive_timeout(value):
    result = float(value)
    if not math.isfinite(result) or not 0 < result <= 60:
        raise argparse.ArgumentTypeError("timeout must be greater than zero and at most 60 seconds")
    return result


def wait_seconds(value):
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 60:
        raise argparse.ArgumentTypeError("wait must be from zero to 60 seconds")
    return result


def duration_seconds(value):
    result = float(value)
    if not math.isfinite(result) or not 0 < result <= 86400:
        raise argparse.ArgumentTypeError(
            "duration must be greater than zero and at most 86400 seconds"
        )
    return result


def output_options(command, identity=False, unit=False):
    command.add_argument("--json", action="store_true")
    if identity:
        command.add_argument(
            "--show-identity", action="store_true", help="include configured ID/name/room"
        )
    if unit:
        command.add_argument("--unit", choices=("C", "F"), default="C")


def parser_for_cli():
    parser = argparse.ArgumentParser(description="Tiny local Serin mini-split comfort CLI")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--host", help="controller hostname or IP (reads only; optional port)")
    parser.add_argument("--config", help="private JSON config path")
    parser.add_argument("--timeout", type=positive_timeout, default=5)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor", "watch", "capabilities"):
        command = commands.add_parser(name)
        command.add_argument(
            "device",
            nargs=None if name == "capabilities" else "?",
            help="exact configured device ID",
        )
        output_options(command, identity=True, unit=name != "capabilities")
        if name == "watch":
            command.add_argument(
                "--jsonl",
                dest="json",
                action="store_true",
                help="one JSON object per received frame",
            )
            command.add_argument("--duration", type=duration_seconds)
            command.add_argument(
                "--interval",
                type=positive_timeout,
                default=1,
                help="minimum human display interval; all frames are received",
            )
    listing = commands.add_parser(
        "devices", help="list private configured devices without contacting them"
    )
    output_options(listing)
    finding = commands.add_parser(
        "discover", help="find a configured controller by its hardware MAC"
    )
    finding.add_argument("device", nargs="?")
    finding.add_argument("--network", help="explicit private IPv4 range, at most /24")
    output_options(finding)
    inspecting = commands.add_parser(
        "inspect", help="read private hardware metadata at an explicit host"
    )
    output_options(inspecting)
    for name in sorted(CONTROL_COMMANDS):
        command = commands.add_parser(name)
        command.add_argument("device", help="exact registered device ID with a pinned MAC")
        output_options(command, identity=True, unit=True)
        command.add_argument("--yes", action="store_true", help="execute an authorized change")
        command.add_argument(
            "--dry-run", action="store_true", help="verify target and validate without sending"
        )
        command.add_argument(
            "--wait",
            type=wait_seconds,
            default=20,
            help="bounded post-write observation, default 20 seconds; zero returns unconfirmed",
        )
        if name in ("heat", "cool"):
            command.add_argument("--temp")
        elif name == "temp":
            command.add_argument("value")
        elif name in ("power", "mode", "fan", "vane", "wide-vane"):
            values = {
                "power": ("on", "off"),
                "mode": MODES,
                "fan": FANS,
                "vane": VANES,
                "wide-vane": WIDE_VANES,
            }
            command.add_argument("value", choices=values[name])
        elif name == "set":
            command.add_argument("--power", choices=("on", "off"))
            command.add_argument("--mode", choices=MODES)
            command.add_argument("--temp")
            command.add_argument("--fan", choices=FANS)
            command.add_argument("--vane", choices=VANES)
            command.add_argument("--wide-vane", choices=WIDE_VANES)
    return parser


def settings_from_args(args):
    name = args.command
    if name in ("heat", "cool"):
        result = {"power": True, "mode": name}
        value = args.temp
    elif name == "temp":
        result = {}
        value = args.value
    elif name == "set":
        result = {
            k: getattr(args, k)
            for k in ("power", "mode", "fan", "vane", "wide_vane")
            if getattr(args, k) is not None
        }
        if "power" in result:
            result["power"] = result["power"] == "on"
        value = args.temp
    else:
        result = {name.replace("-", "_"): args.value == "on" if name == "power" else args.value}
        value = None
    if value is not None:
        result["target_c"] = target_c(value, args.unit)
    if not result:
        raise ValueError("provide at least one setting")
    return result


def print_json(value):
    print(json.dumps(value, allow_nan=False), flush=True)


def print_status(state, unit="C"):
    if not state["heat_pump_connected"]:
        print("Controller reachable · heat pump disconnected · equipment state unknown", flush=True)
        return

    def display(value):
        return "unknown" if value is None else str(value)

    power = {True: "on", False: "off", None: "unknown"}[state["power"]]
    operating = {True: "yes", False: "no", None: "unknown"}[state["operating"]]
    print(
        f"Heat pump connected · power {power} · mode {display(state['mode'])} · operating {operating}"
    )
    suffix = unit.lower()
    print(
        f"Room {display(state.get('room_' + suffix))} °{unit} · target {display(state.get('target_' + suffix))} °{unit}",
        flush=True,
    )
    if unit == "F" and state.get("target_f_exact") is False:
        print(f"Exact target {state['target_c']} °C; nearest Fahrenheit display shown", flush=True)


def show_result(result, args, device=None):
    if getattr(args, "show_identity", False) and device is not None:
        result = {**result, "device": device.identity()}
        if not args.json:
            print(
                f"{device.id or '(direct)'} · {device.name or 'Unnamed controller'} · room: {device.room_id or 'unassigned'}"
            )
    if args.json:
        print_json(result)
    elif args.command in CONTROL_COMMANDS:
        labels = {
            "dry_run": "Validated · no command sent",
            "readback_match": "Post-grace readback matched · hardware acknowledgment unavailable",
            "unconfirmed": "Change unconfirmed · do not assume equipment changed",
        }
        print(labels[result["outcome"]])
        print("Requested: " + json.dumps(result["requested"]))
        if result["after"] is not None:
            print_status(result["after"], args.unit)
    elif args.command == "capabilities":
        print("Firmware configuration · physical unit capabilities unverified")
        modes = result["configured_modes"]
        print("Modes: " + (", ".join(modes) if modes is not None else "unknown"))
        temperature = result["temperature"]
        if temperature is not None:
            print("Setpoints: 16–30.5 °C in 0.5 steps · 61–88 °F in integer Mitsubishi steps")
        for label, key in (
            ("Fan", "fan_values"),
            ("Vertical vane", "vane_values"),
            ("Horizontal vane", "wide_vane_values"),
        ):
            values = result[key]
            print(
                f"{label}: "
                + (", ".join(values) if values is not None else "unavailable or unknown")
            )
    else:
        print_status(result, args.unit)


def main(argv=None):
    args = parser_for_cli().parse_args(argv)
    try:
        if args.command == "inspect":
            if args.host is None:
                raise ValueError("inspect requires --host for initial identity enrollment")
            result = read_info(controller_url(args.host), args.timeout)
            if args.json:
                print_json(result)
            else:
                for key, value in result.items():
                    print(f"{key}: {value}")
            return 0
        if args.command == "devices":
            if args.host is not None:
                raise ValueError("devices requires inventory, not --host")
            devices, rooms = load_inventory(args.config)
            if args.json:
                print_json(
                    {
                        "schema_version": 1,
                        "devices": [d.identity() for d in devices],
                        "rooms": rooms,
                    }
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
                print_json(result)
            else:
                print(
                    f"Verified {device.id}: {result['endpoint']} · {result['hardware']['board']} · {result['hardware']['fw']}"
                )
            return 0
        if args.command in CONTROL_COMMANDS:
            if not args.yes and not args.dry_run:
                raise ValueError(
                    "controls require --yes; use --dry-run to validate without sending"
                )
            requested = settings_from_args(args)
            result = apply_settings(
                device, requested, timeout=args.timeout, wait=args.wait, dry_run=args.dry_run
            )
            show_result(result, args, device)
            return 3 if result["outcome"] == "unconfirmed" else 0
        if args.command == "capabilities":
            show_result(read_capabilities(device, args.timeout), args, device)
            return 0
        if args.command == "watch":
            last = None
            last_printed = None
            shown_at = 0
            for state in watch_states(device, args.timeout, args.duration):
                last = state
                comparable = {
                    k: v for k, v in state.items() if k not in ("received_at", "freshness")
                }
                if (
                    args.json
                    or last_printed is None
                    or (comparable != last_printed and time.monotonic() - shown_at >= args.interval)
                ):
                    show_result(state, args, device)
                    last_printed = comparable
                    shown_at = time.monotonic()
            return 0 if last is not None and last["heat_pump_connected"] else 2
        state = (
            inspect_device(device, args.timeout)
            if device.mac
            else read_status(controller_url(device.host), args.timeout)
        )
        show_result(state, args, device)
        return 0 if state["heat_pump_connected"] else 2
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        if args.json:
            print_json({"schema_version": 1, "error": str(exc)})
        else:
            print(f"serinctl: {exc}", file=sys.stderr)
        return 1
