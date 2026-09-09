"""Allowlisted state from HomeKit firmware v0.2.5; never return raw frames."""

import math

FIRMWARE = "v0.2.5"
MODES = ("heat", "cool", "dry", "fan", "auto")
FANS = ("auto", "quiet", "1", "2", "3", "4")
VANES = ("auto", "1", "2", "3", "4", "5", "swing")
WIDE_VANES = ("ll", "l", "c", "r", "rr", "split", "swing")
# Firmware's Mitsubishi setpoint display table, not physical F/C conversion.
# See v0.2.5 main/sl2_proto.h sl2_ftab1 and THIRD_PARTY_NOTICES.txt.
FAHRENHEIT_TARGETS = (
    16,
    16.5,
    17,
    17.5,
    18,
    18.5,
    19,
    20,
    21,
    21.5,
    22,
    22.5,
    23,
    23.5,
    24,
    24.5,
    25,
    25.5,
    26,
    26.5,
    27,
    27.5,
    28,
    28.5,
    29,
    29.5,
    30,
    30.5,
)


def number(value):
    try:
        return value if type(value) in (int, float) and math.isfinite(value) else None
    except OverflowError:
        return None


def choice(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def target_f(value):
    if value is None or not 16 <= value <= 30.5:
        return None
    return min(range(61, 89), key=lambda f: abs(FAHRENHEIT_TARGETS[f - 61] - value))


def summarize(frame: dict) -> dict:
    if frame.get("type") != "state" or type(frame.get("connected")) is not bool:
        raise ValueError("unsupported controller state")
    connected = frame["connected"]
    # A reachable controller may have no CN105 connection; cached/default HVAC
    # values then do not describe the actual equipment.
    state = frame if connected else {}
    target = number(state.get("target"))
    fahrenheit = target_f(target)
    room = number(state.get("room"))
    return {
        "schema_version": 1,
        "controller_reachable": True,
        "heat_pump_connected": connected,
        "power": state.get("power") if type(state.get("power")) is bool else None,
        "mode": choice(state.get("mode"), MODES),
        "target_c": target,
        "target_f": fahrenheit,
        "target_f_exact": (FAHRENHEIT_TARGETS[fahrenheit - 61] == target)
        if fahrenheit is not None
        else None,
        "room_c": room,
        "room_f": number(round(room * 9 / 5 + 32, 2)) if room is not None else None,
        "outside_c": number(state.get("outsideTemp")),
        "operating": state.get("operating") if type(state.get("operating")) is bool else None,
        "compressor_hz": number(state.get("compressorHz")),
        "error_code": number(state.get("errorCode")),
        "fan": choice(state.get("fan"), FANS),
        "vane": choice(state.get("vane"), VANES),
        "wide_vane": choice(state.get("wideVane"), WIDE_VANES),
    }


def metadata(frame):
    """Nonsecret control metadata; these flags are configuration, not discovery."""
    mask = frame.get("modeMask")
    if type(mask) is not int or not 0 < mask <= 31 or not mask & 15:
        mask = None
    if mask is not None and mask & 16 and mask & 3 != 3:
        mask = None
    vane = frame.get("vaneConfig")
    if type(vane) is not int or vane not in (0, 1, 2):
        vane = None
    uptime = frame.get("uptime")
    if type(uptime) is not int or uptime < 0:
        uptime = None
    return {"mode_mask": mask, "vane_config": vane, "uptime_seconds": uptime}


def capabilities(meta, firmware):
    supported = firmware == FIRMWARE
    mask = meta["mode_mask"]
    vane = meta["vane_config"]
    return {
        "schema_version": 1,
        "firmware_supported": supported,
        "firmware_profile": FIRMWARE if supported else None,
        "source": "firmware_configuration",
        "physical_unit_support_verified": None,
        "configured_modes": (
            [mode for i, mode in enumerate(MODES) if mask & (1 << i)] if mask is not None else None
        ),
        "vane_config": vane,
        "temperature": {
            "min_c": 16,
            "max_c": 30.5,
            "step_c": 0.5,
            "min_f": 61,
            "max_f": 88,
            "step_f": 1,
            "fahrenheit_mapping": "mitsubishi_setpoint_table",
            "fahrenheit_setpoints": [
                {"f": f, "c": c} for f, c in enumerate(FAHRENHEIT_TARGETS, 61)
            ],
            "physical_step_c": None,
            "supported_target_modes": ["heat", "cool"],
        }
        if supported
        else None,
        "fan_values": list(FANS) if supported else None,
        "vane_values": list(VANES) if supported and vane in (1, 2) else None,
        "wide_vane_values": list(WIDE_VANES) if supported and vane == 2 else None,
        "hardware_ack_available": False,
    }


def target_c(value, unit="C"):
    """Reject unsupported values; never silently clamp or round a command."""
    if type(value) is bool:
        raise ValueError("temperature must be a finite number")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("temperature must be a finite number") from None
    if not math.isfinite(value):
        raise ValueError("temperature must be a finite number")
    if unit == "F":
        if not 61 <= value <= 88 or not value.is_integer():
            raise ValueError("Fahrenheit setpoint must be an integer from 61 to 88")
        return float(FAHRENHEIT_TARGETS[int(value) - 61])
    if unit != "C":
        raise ValueError("temperature unit must be C or F")
    if not 16 <= value <= 30.5 or not (value * 2).is_integer():
        raise ValueError("Celsius setpoint must be 16 to 30.5 in 0.5 degree steps")
    return value


def validate_settings(requested, before, meta, firmware):
    if firmware != FIRMWARE:
        raise ValueError("controls require verified HomeKit firmware v0.2.5")
    if not before["heat_pump_connected"]:
        raise ValueError("heat pump disconnected; refusing control")
    if before["power"] is None or before["mode"] is None:
        raise ValueError("current power or mode is unknown; refusing control")
    allowed = {"power", "mode", "target_c", "fan", "vane", "wide_vane"}
    if not requested or set(requested) - allowed:
        raise ValueError("provide only supported comfort settings")
    if "power" in requested and type(requested["power"]) is not bool:
        raise ValueError("power must be on or off")
    for key, values in (("mode", MODES), ("fan", FANS), ("vane", VANES), ("wide_vane", WIDE_VANES)):
        if key in requested and choice(requested[key], values) is None:
            raise ValueError(f"unsupported {key} value")
    mode = requested.get("mode", before["mode"])
    if "mode" in requested or "target_c" in requested or requested.get("power") is True:
        mask = meta["mode_mask"]
        if mask is None or not mask & (1 << MODES.index(mode)):
            raise ValueError("mode is disabled or configured mode support is unknown")
    if "target_c" in requested:
        if number(requested["target_c"]) is None:
            raise ValueError("target_c must be a finite number")
        target_c(requested["target_c"])
        if mode not in ("heat", "cool"):
            raise ValueError("temperature changes require heat or cool mode; select it explicitly")
    if "vane" in requested and meta["vane_config"] not in (1, 2):
        raise ValueError("vertical vane is disabled or configured support is unknown")
    if "wide_vane" in requested and meta["vane_config"] != 2:
        raise ValueError("horizontal vane is disabled or configured support is unknown")
    wire_keys = {"target_c": "target", "wide_vane": "wideVane"}
    return {"cmd": "set", **{wire_keys.get(k, k): v for k, v in requested.items()}}
