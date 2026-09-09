"""Private target selection. No discovery guesses or credential-bearing URLs."""

import json
import os
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


def resolve_url(host: str | None, config: str | None) -> str:
    if host is not None:
        return controller_url(host)
    path = Path(
        config or os.environ.get("SERINCTL_CONFIG", "/usr/local/config/serinctl/config.json")
    )
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or not isinstance(data.get("host"), str):
            raise ValueError
    except (OSError, ValueError):
        raise ValueError(
            "provide --host or a private config file containing a host string"
        ) from None
    return controller_url(data["host"])
