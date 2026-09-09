"""Read-only WebSocket snapshots with optional hardware identity verification."""

import ipaddress
import json
import time

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from .config import normalize_mac
from .protocol import summarize


class IdentityMismatch(ValueError):
    pass


def device_info(frame):
    """Explicit metadata allowlist; never return raw firmware frames."""
    result = {"mac": normalize_mac(frame.get("mac"))}
    for key in ("board", "fw", "idf", "hostname"):
        value = frame.get(key)
        if not isinstance(value, str) or not value or len(value) > 128 or not value.isprintable():
            raise ValueError("invalid device metadata")
        result[key] = value
    result["ip"] = str(ipaddress.IPv4Address(frame.get("ip")))
    return result


def read_snapshot(url, timeout=5, expected_mac=None, info_only=False):
    deadline = time.monotonic() + timeout
    state = None
    info = None
    try:
        with connect(
            url,
            open_timeout=timeout,
            close_timeout=1,
            max_size=65536,
            proxy=None,
            compression=None,
            ping_interval=None,
        ) as ws:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                frame = json.loads(ws.recv(timeout=remaining))
                if not isinstance(frame, dict):
                    continue
                if frame.get("type") == "state" and not info_only:
                    state = summarize(frame)
                elif frame.get("type") == "deviceInfo" and (expected_mac or info_only):
                    info = device_info(frame)
                    if expected_mac and info["mac"] != normalize_mac(expected_mac):
                        raise IdentityMismatch("hardware identity mismatch; refusing this endpoint")
                if info_only and info is not None:
                    return info
                if (
                    not info_only
                    and state is not None
                    and (expected_mac is None or info is not None)
                ):
                    return state
    except IdentityMismatch:
        raise
    except (OSError, TimeoutError, WebSocketException):
        raise ValueError(
            "controller unavailable; check power, Wi-Fi, hostname, and local access"
        ) from None
    except (ValueError, UnicodeError):
        raise ValueError("unsupported or malformed controller state") from None


def read_status(url: str, timeout: float = 5, expected_mac=None) -> dict:
    return read_snapshot(url, timeout, expected_mac)


def read_info(url, timeout=5, expected_mac=None):
    return read_snapshot(url, timeout, expected_mac, info_only=True)
