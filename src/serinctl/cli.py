"""Small human and JSON command surface."""

import argparse
import json
import math
import sys

from . import __version__
from .client import read_status
from .config import resolve_url


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
        command.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        state = read_status(resolve_url(args.host, args.config), args.timeout)
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
