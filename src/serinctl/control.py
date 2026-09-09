"""Guarded local comfort settings and foreground observations.

Readback is deliberately weaker than a hardware acknowledgment: v0.2.5
publishes wanted values and has no authenticated CN105 acknowledgment field.
"""

import json
import math
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone

from websockets.exceptions import WebSocketException

from .client import IdentityMismatch, connect, device_info
from .config import controller_url, normalize_mac
from .protocol import capabilities, metadata, summarize, validate_settings

GRACE_SECONDS = 10
TRANSPORT_ERRORS = (OSError, TimeoutError, WebSocketException)


class Session:
    def __init__(self, ws, expected_mac):
        self.ws = ws
        self.expected_mac = expected_mac
        self.info = None
        self.state = None
        self.meta = None
        self.received = None
        self.received_at = None

    def receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        try:
            frame = json.loads(self.ws.recv(timeout=remaining))
        except (ValueError, UnicodeError, RecursionError, OverflowError):
            raise ValueError("unsupported or malformed controller state") from None
        if not isinstance(frame, dict):
            return False
        if frame.get("type") == "deviceInfo":
            try:
                info = device_info(frame)
            except ValueError:
                raise ValueError("unsupported or malformed device metadata") from None
            if self.expected_mac and info["mac"] != normalize_mac(self.expected_mac):
                raise IdentityMismatch("hardware identity mismatch; refusing this endpoint")
            if self.info is not None and info["fw"] != self.info["fw"]:
                raise ValueError("firmware identity changed during observation")
            self.info = info
        elif frame.get("type") == "state":
            self.state = summarize(frame)
            self.meta = metadata(frame)
            self.received = time.monotonic()
            self.received_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def initial(self, deadline, require_info):
        while True:
            self.receive(deadline)
            if self.state is not None and (not require_info or self.info is not None):
                if time.monotonic() - self.received <= 2:
                    return

    def next_state(self, deadline):
        while not self.receive(deadline):
            pass
        return self.state


@contextmanager
def open_session(device, timeout=5, require_info=True):
    """Address fallback is permitted only before yielding a verified session."""
    hosts = list(dict.fromkeys(h for h in (device.hostname, device.host) if h))
    stack = None
    for host in hosts:
        stack = ExitStack()
        try:
            deadline = time.monotonic() + timeout
            ws = stack.enter_context(
                connect(
                    controller_url(host),
                    open_timeout=timeout,
                    close_timeout=1,
                    max_size=65536,
                    max_queue=4,
                    proxy=None,
                    compression=None,
                    ping_interval=None,
                )
            )
            session = Session(ws, device.mac)
            session.initial(deadline, require_info)
            break
        except TRANSPORT_ERRORS:
            stack.close()
            stack = None
        except BaseException:
            stack.close()
            raise
    if stack is None:
        raise ValueError("controller unavailable at configured addresses; use discover")
    try:
        yield session
    finally:
        try:
            stack.close()
        except TRANSPORT_ERRORS:
            # Closing after a completed read does not invalidate that read.
            pass


def read_capabilities(device, timeout=5):
    with open_session(device, timeout) as session:
        return capabilities(session.meta, session.info["fw"])


def _result(requested, before):
    return {
        "schema_version": 1,
        "outcome": "unconfirmed",
        "command_sent": False,
        "command_attempted": False,
        "requested": dict(requested),
        "before": before,
        "after": None,
        "verification": {
            "method": "post_grace_readback",
            "hardware_acknowledged": None,
            "readback_match": None,
            "grace_seconds": GRACE_SECONDS,
            "observations": 0,
            "reason": "not_sent",
        },
    }


def apply_settings(device, requested, timeout=5, wait=20, dry_run=False):
    if device.id is None or device.mac is None:
        raise ValueError("controls require an exact registered device ID with a pinned MAC")
    if type(wait) not in (int, float) or not math.isfinite(wait) or not 0 <= wait <= 60:
        raise ValueError("wait must be from zero to 60 seconds")
    with open_session(device, timeout) as session:
        before = dict(session.state)
        payload = validate_settings(requested, before, session.meta, session.info["fw"])
        result = _result(requested, before)
        verification = result["verification"]
        if dry_run:
            result["outcome"] = "dry_run"
            verification["reason"] = "validated_without_sending"
            return result
        # Include preserved power/mode in readback checks, without writing them.
        expected = {"power": before["power"], "mode": before["mode"], **requested}
        sent_at = time.monotonic()
        deadline = sent_at + wait
        verification["reason"] = "send_uncertain"
        try:
            # Once send is attempted, no exception may trigger endpoint fallback
            # or another send. A failed send may still have reached the unit.
            result["command_attempted"] = True
            session.ws.send(json.dumps(payload, allow_nan=False))
            result["command_sent"] = True
            verification["reason"] = "readback_timeout"
            anchor = None
            last_uptime = None
            baseline_uptime = session.meta["uptime_seconds"]
            count = 0
            while time.monotonic() < deadline:
                state = session.next_state(deadline)
                result["after"] = dict(state)
                if not state["heat_pump_connected"]:
                    verification["reason"] = "heat_pump_disconnected"
                    return result
                uptime = session.meta["uptime_seconds"]
                if baseline_uptime is not None and uptime is not None and uptime < baseline_uptime:
                    verification["reason"] = "controller_restarted"
                    return result
                match = all(state.get(key) == value for key, value in expected.items())
                if anchor is None:
                    if match:
                        # Start the grace clock at the first observed matching
                        # echo, so network transit is not mistaken for grace.
                        anchor = (time.monotonic(), uptime)
                    continue
                elapsed = time.monotonic() - anchor[0]
                generated_after_grace = (
                    uptime is not None
                    and anchor[1] is not None
                    and uptime - anchor[1] >= GRACE_SECONDS + 1
                )
                if elapsed < GRACE_SECONDS or not generated_after_grace:
                    continue
                if not match:
                    count = 0
                    verification["observations"] = 0
                    verification["readback_match"] = False
                    verification["reason"] = "readback_mismatch"
                elif uptime != last_uptime:
                    count += 1
                    verification["observations"] = count
                    if count >= 2:
                        result["outcome"] = "readback_match"
                        verification["readback_match"] = True
                        verification["reason"] = "post_grace_frames_matched"
                        return result
                last_uptime = uptime
        except TimeoutError:
            if result["command_sent"] and verification["readback_match"] is not False:
                verification["reason"] = "readback_timeout"
        except (OSError, WebSocketException):
            if result["command_sent"]:
                verification["reason"] = "observation_interrupted"
        except ValueError:
            verification["reason"] = "invalid_observation"
        except KeyboardInterrupt:
            verification["reason"] = "observation_cancelled"
        return result


def watch_states(device, timeout=5, duration=None):
    """Yield allowlisted status frames; nothing sends an application command."""
    try:
        with open_session(device, timeout, require_info=bool(device.mac)) as session:
            deadline = time.monotonic() + duration if duration is not None else None
            while True:
                yield {
                    **session.state,
                    "received_at": session.received_at,
                    "freshness": "controller_frame_received; hardware_sample_age_unknown",
                }
                now = time.monotonic()
                if deadline is not None and now >= deadline:
                    return
                receive_deadline = (
                    min(now + timeout, deadline) if deadline is not None else now + timeout
                )
                try:
                    session.next_state(receive_deadline)
                except TimeoutError:
                    if deadline is not None and time.monotonic() >= deadline:
                        return
                    raise
    except TRANSPORT_ERRORS:
        raise ValueError("observation interrupted; equipment state is unknown") from None
