"""Allowlisted state from HomeKit firmware v0.2.5; never return raw frames."""

import math


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def choice(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def summarize(frame: dict) -> dict:
    if frame.get("type") != "state" or type(frame.get("connected")) is not bool:
        raise ValueError("unsupported controller state")
    connected = frame["connected"]
    # A reachable controller may have no CN105 connection; cached/default HVAC
    # values then do not describe the actual equipment.
    state = frame if connected else {}
    return {
        "schema_version": 1,
        "controller_reachable": True,
        "heat_pump_connected": connected,
        "power": state.get("power") if type(state.get("power")) is bool else None,
        "mode": choice(state.get("mode"), {"heat", "cool", "dry", "fan", "auto"}),
        "target_c": number(state.get("target")),
        "room_c": number(state.get("room")),
        "outside_c": number(state.get("outsideTemp")),
        "operating": state.get("operating") if type(state.get("operating")) is bool else None,
        "compressor_hz": number(state.get("compressorHz")),
        "error_code": number(state.get("errorCode")),
    }
