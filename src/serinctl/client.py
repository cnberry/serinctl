"""Receive one state frame. No application commands are sent."""

import json
import time

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from .protocol import summarize


def read_status(url: str, timeout: float = 5) -> dict:
    deadline = time.monotonic() + timeout
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
                if isinstance(frame, dict) and frame.get("type") == "state":
                    return summarize(frame)
    except (OSError, TimeoutError, WebSocketException):
        raise ValueError(
            "controller unavailable; check power, Wi-Fi, hostname, and local access"
        ) from None
    except (ValueError, UnicodeError):
        raise ValueError("unsupported or malformed controller state") from None
