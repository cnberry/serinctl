"""Control/observation scenarios use synthetic endpoints and a fake clock only."""

import contextlib
import io
import json
import math
import unittest
from unittest.mock import patch

from serinctl.cli import main, parser_for_cli, settings_from_args
from serinctl.client import IdentityMismatch
from serinctl.config import Device
from serinctl.control import apply_settings, read_capabilities, watch_states
from serinctl.protocol import capabilities, metadata, summarize, target_c, validate_settings

MAC = "02:00:00:00:00:10"
DEVICE = Device("unit-a", "Demo unit", None, "192.0.2.10", MAC)
INFO = {
    "type": "deviceInfo",
    "mac": MAC,
    "board": "Demo board",
    "fw": "v0.2.5",
    "idf": "v5.5.4",
    "hostname": "serin-demo",
    "ip": "192.0.2.10",
}


def state(**updates):
    return {
        "type": "state",
        "connected": True,
        "power": False,
        "mode": "cool",
        "target": 22.5,
        "room": 26.5,
        "operating": False,
        "fan": "auto",
        "vane": "auto",
        "wideVane": "c",
        "modeMask": 31,
        "vaneConfig": 2,
        "uptime": 100,
        **updates,
    }


class Clock:
    now = 0

    def monotonic(self):
        return self.now


class Socket:
    def __init__(self, clock, events, send_error=None):
        self.clock = clock
        self.events = list(events)
        self.sent = []
        self.send_error = send_error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def recv(self, timeout):
        deadline = self.clock.now + timeout
        if not self.events or self.events[0][0] > deadline:
            self.clock.now = deadline
            raise TimeoutError
        when, frame = self.events.pop(0)
        self.clock.now = max(self.clock.now, when)
        if isinstance(frame, BaseException):
            raise frame
        return json.dumps(frame) if not isinstance(frame, str) else frame

    def send(self, payload):
        self.sent.append(json.loads(payload))
        if self.send_error:
            raise self.send_error


class ProtocolControls(unittest.TestCase):
    def test_temperature_table_and_rejected_precision(self):
        self.assertEqual(target_c(71, "F"), 22)
        self.assertEqual(target_c(72, "F"), 22.5)
        self.assertEqual(target_c(61, "F"), 16)
        self.assertEqual(target_c(88, "F"), 30.5)
        for value, unit in (
            (math.nan, "C"),
            (math.inf, "C"),
            (True, "C"),
            (15.5, "C"),
            (31, "C"),
            (22.25, "C"),
            (70.5, "F"),
            (60, "F"),
            (89, "F"),
            (20, "K"),
            ("bad", "C"),
        ):
            with self.subTest(value=value, unit=unit), self.assertRaises(ValueError):
                target_c(value, unit)

    def test_status_fahrenheit_distinguishes_setpoint_table_and_physical_room(self):
        result = summarize(state(target=22.5, room=22.5))
        self.assertEqual(result["target_f"], 72)
        self.assertEqual(result["room_f"], 72.5)
        self.assertTrue(result["target_f_exact"])
        result = summarize(state(target=20.5))
        self.assertEqual(result["target_f"], 68)
        self.assertFalse(result["target_f_exact"])
        result = summarize(state(connected=False))
        for key in ("target_f", "room_f", "target_f_exact", "fan", "vane", "wide_vane"):
            self.assertIsNone(result[key])

    def test_extreme_numeric_input_stays_json_safe(self):
        for value in (10**400, 1e308):
            result = summarize(state(room=value))
            self.assertIsNone(result["room_f"])
            json.dumps(result, allow_nan=False)

    def test_configuration_is_not_physical_capability(self):
        result = capabilities(metadata(state(modeMask=2, vaneConfig=1)), "v0.2.5")
        self.assertEqual(result["configured_modes"], ["cool"])
        self.assertIsNone(result["physical_unit_support_verified"])
        self.assertIsNone(result["temperature"]["physical_step_c"])
        self.assertIsNone(result["wide_vane_values"])
        self.assertEqual(len(result["temperature"]["fahrenheit_setpoints"]), 28)
        self.assertIsNone(capabilities(metadata(state()), "v9")["temperature"])
        for mask in (True, 16, 18, 32, -1):
            self.assertIsNone(metadata(state(modeMask=mask))["mode_mask"])

    def test_validation_rejects_auto_target_disabled_modes_vanes_and_unknown_strings(self):
        cases = [
            ({"mode": "heat"}, state(modeMask=2)),
            ({"target_c": 22}, state(mode="auto")),
            ({"target_c": 22}, state(mode="fan")),
            ({"mode": "auto", "target_c": 22}, state()),
            ({"vane": "1"}, state(vaneConfig=0)),
            ({"wide_vane": "l"}, state(vaneConfig=1)),
            ({"wide_vane": "auto"}, state()),
            ({"power": True}, state(connected=False)),
            ({"fan": "unsupported"}, state()),
            ({"target_c": 22}, state(modeMask=None)),
            ({"cmd": "reset"}, state()),
        ]
        for request, frame in cases:
            with self.subTest(request=request, frame=frame), self.assertRaises(ValueError):
                validate_settings(request, summarize(frame), metadata(frame), "v0.2.5")


class TransportControls(unittest.TestCase):
    def exercise(self, events, requested=None, info=None, first=None, send_error=None, **kwargs):
        clock = Clock()
        ws = Socket(clock, [(0, first or state()), (0, info or INFO), *events], send_error)
        with (
            patch("serinctl.control.connect", return_value=ws) as connect,
            patch("serinctl.control.time.monotonic", side_effect=clock.monotonic),
        ):
            result = apply_settings(DEVICE, requested or {"power": True}, **kwargs)
        return result, ws, connect

    def test_dry_run_never_sends_and_excludes_private_frame_fields(self):
        result, ws, _ = self.exercise(
            [],
            dry_run=True,
            first=state(hkSetupCode="private", ssid="private", arbitrary={"secret": "private"}),
        )
        self.assertEqual(result["outcome"], "dry_run")
        self.assertFalse(result["command_attempted"])
        self.assertEqual(ws.sent, [])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn(MAC, json.dumps(result))
        self.assertNotIn("192.0.2.10", json.dumps(result))

    def test_matching_post_grace_readback_has_no_hardware_ack_claim(self):
        result, ws, connect = self.exercise(
            [
                (0.1, state(power=True)),
                (1, state(power=True, uptime=101)),
                (11.1, state(power=True, uptime=111)),
                (12.1, state(power=True, uptime=112)),
            ]
        )
        self.assertEqual(ws.sent, [{"cmd": "set", "power": True}])
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(result["outcome"], "readback_match")
        self.assertTrue(result["verification"]["readback_match"])
        self.assertEqual(result["verification"]["observations"], 2)
        self.assertIsNone(result["verification"]["hardware_acknowledged"])

    def test_echo_or_buffered_frames_do_not_confirm(self):
        for events in (
            [(0.1, state(power=True))],
            [(0.1, state(power=True)), (12, state(power=True)), (13, state(power=True))],
        ):
            result, ws, _ = self.exercise(events)
            self.assertEqual(result["outcome"], "unconfirmed")
            self.assertEqual(result["verification"]["observations"], 0)
            self.assertEqual(len(ws.sent), 1)

    def test_no_wait_sends_once_and_reports_unconfirmed(self):
        result, ws, _ = self.exercise([], wait=0)
        self.assertTrue(result["command_sent"])
        self.assertEqual(result["outcome"], "unconfirmed")
        self.assertIsNone(result["after"])
        self.assertEqual(len(ws.sent), 1)

    def test_rejected_half_degree_is_mismatch_not_rounded_success(self):
        result, _, _ = self.exercise(
            [
                (0.1, state(target=23.5)),
                (12, state(target=23, uptime=112)),
                (13, state(target=23, uptime=113)),
            ],
            requested={"target_c": 23.5},
        )
        self.assertEqual(result["outcome"], "unconfirmed")
        self.assertFalse(result["verification"]["readback_match"])
        self.assertEqual(result["after"]["target_c"], 23)

    def test_preserved_power_mode_are_checked_without_resending(self):
        result, ws, _ = self.exercise(
            [
                (0.1, state(target=23)),
                (12, state(target=23, power=True, uptime=112)),
                (13, state(target=23, power=True, uptime=113)),
            ],
            requested={"target_c": 23},
        )
        self.assertEqual(ws.sent, [{"cmd": "set", "target": 23}])
        self.assertEqual(result["outcome"], "unconfirmed")

    def test_send_failure_is_uncertain_without_retry(self):
        result, ws, connect = self.exercise([], send_error=OSError("private endpoint"))
        self.assertTrue(result["command_attempted"])
        self.assertFalse(result["command_sent"])
        self.assertEqual(result["verification"]["reason"], "send_uncertain")
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(len(ws.sent), 1)
        self.assertNotIn("private", json.dumps(result))

    def test_malformed_numeric_observation_after_send_stays_structured(self):
        result, ws, connect = self.exercise([(0.1, state(power=True, room=10**400))])
        self.assertEqual(result["outcome"], "unconfirmed")
        self.assertIsNone(result["after"]["room_c"])
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(len(ws.sent), 1)
        json.dumps(result, allow_nan=False)

    def test_interrupted_malformed_disconnected_or_restarted_after_send_is_uncertain(self):
        for frame, reason in (
            (OSError("private"), "observation_interrupted"),
            ("private malformed", "invalid_observation"),
            (state(connected=False), "heat_pump_disconnected"),
            (state(uptime=0), "controller_restarted"),
            (KeyboardInterrupt(), "observation_cancelled"),
        ):
            result, ws, connect = self.exercise([(0.1, frame)])
            self.assertEqual(result["outcome"], "unconfirmed")
            self.assertEqual(result["verification"]["reason"], reason)
            self.assertEqual(connect.call_count, 1)
            self.assertEqual(len(ws.sent), 1)

    def test_wrong_identity_firmware_and_disconnected_preflight_never_send(self):
        for info, first in (
            (dict(INFO, mac="02:00:00:00:00:11"), state()),
            (dict(INFO, fw="v0.2.6"), state()),
            (INFO, state(connected=False)),
        ):
            clock = Clock()
            ws = Socket(clock, [(0, info), (0, first)])
            with (
                patch("serinctl.control.connect", return_value=ws) as connect,
                patch("serinctl.control.time.monotonic", side_effect=clock.monotonic),
                self.assertRaises(ValueError),
            ):
                apply_settings(DEVICE, {"power": True})
            self.assertEqual(ws.sent, [])
            self.assertEqual(connect.call_count, 1)

    def test_unpinned_or_direct_targets_rejected_before_network(self):
        for device in (
            Device(None, None, None, "192.0.2.10"),
            Device("unit-a", "Demo", None, "192.0.2.10"),
        ):
            with patch("serinctl.control.connect") as connect, self.assertRaises(ValueError):
                apply_settings(device, {"power": True})
            connect.assert_not_called()

    def test_only_preflight_transport_failure_allows_address_fallback(self):
        clock = Clock()
        ws = Socket(clock, [(0, INFO), (0, state())])
        device = Device("unit-a", "Demo", None, "192.0.2.10", MAC, "example.local")
        with (
            patch("serinctl.control.connect", side_effect=[OSError(), ws]) as connect,
            patch("serinctl.control.time.monotonic", side_effect=clock.monotonic),
        ):
            self.assertEqual(
                apply_settings(device, {"power": True}, dry_run=True)["outcome"], "dry_run"
            )
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(ws.sent, [])


class WatchTests(unittest.TestCase):
    def test_foreground_watch_emits_sanitized_frames_and_never_sends(self):
        clock = Clock()
        ws = Socket(
            clock, [(0, INFO), (0, state()), (1, state(connected=False, hkSetupCode="private"))]
        )
        with (
            patch("serinctl.control.connect", return_value=ws),
            patch("serinctl.control.time.monotonic", side_effect=clock.monotonic),
        ):
            result = list(watch_states(DEVICE, duration=2))
        self.assertEqual(len(result), 2)
        self.assertFalse(result[-1]["heat_pump_connected"])
        self.assertIsNone(result[-1]["power"])
        self.assertNotIn("private", json.dumps(result))
        self.assertIn("hardware_sample_age_unknown", result[0]["freshness"])
        self.assertEqual(ws.sent, [])

    def test_watch_requires_matching_identity_before_output(self):
        clock = Clock()
        ws = Socket(clock, [(0, state()), (0, dict(INFO, mac="02:00:00:00:00:11"))])
        with (
            patch("serinctl.control.connect", return_value=ws),
            patch("serinctl.control.time.monotonic", side_effect=clock.monotonic),
            self.assertRaises(IdentityMismatch),
        ):
            list(watch_states(DEVICE, duration=2))
        self.assertEqual(ws.sent, [])

    def test_capabilities_reads_allowlisted_data_only(self):
        clock = Clock()
        ws = Socket(clock, [(0, INFO), (0, state(hkSetupCode="private"))])
        with (
            patch("serinctl.control.connect", return_value=ws),
            patch("serinctl.control.time.monotonic", side_effect=clock.monotonic),
        ):
            result = read_capabilities(DEVICE)
        self.assertTrue(result["firmware_supported"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn(MAC, json.dumps(result))
        self.assertEqual(ws.sent, [])


class ControlCliTests(unittest.TestCase):
    def test_shortcuts_and_temp_omit_unspecified_settings(self):
        parser = parser_for_cli()
        for argv, expected in (
            (["heat", "unit-a", "--yes"], {"power": True, "mode": "heat"}),
            (
                ["cool", "unit-a", "--temp", "72", "--unit", "F", "--yes"],
                {"power": True, "mode": "cool", "target_c": 22.5},
            ),
            (["temp", "unit-a", "23", "--yes"], {"target_c": 23}),
            (["mode", "unit-a", "heat", "--yes"], {"mode": "heat"}),
            (
                ["set", "unit-a", "--power", "off", "--wide-vane", "l", "--yes"],
                {"power": False, "wide_vane": "l"},
            ),
        ):
            self.assertEqual(settings_from_args(parser.parse_args(argv)), expected)

    @patch("serinctl.cli.resolve_device", return_value=DEVICE)
    @patch("serinctl.cli.apply_settings")
    def test_guard_blocks_calls_and_dry_run_does_not_need_yes(self, apply, resolve):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["heat", "unit-a", "--json"]), 1)
        apply.assert_not_called()
        apply.return_value = {"schema_version": 1, "outcome": "dry_run"}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["heat", "unit-a", "--dry-run", "--json"]), 0)
        self.assertTrue(apply.call_args.kwargs["dry_run"])

    @patch("serinctl.cli.resolve_device", return_value=DEVICE)
    @patch(
        "serinctl.cli.apply_settings", return_value={"schema_version": 1, "outcome": "unconfirmed"}
    )
    def test_unconfirmed_is_exit_three_with_stable_json(self, apply, resolve):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                main(
                    ["power", "unit-a", "off", "--yes", "--wait", "0", "--json", "--show-identity"]
                ),
                3,
            )
        result = json.loads(output.getvalue())
        self.assertEqual(result["outcome"], "unconfirmed")
        self.assertEqual(result["device"]["id"], "unit-a")
        self.assertEqual(apply.call_args.kwargs["wait"], 0)

    def test_explicit_target_and_invalid_wait_are_parser_errors(self):
        for argv in (
            ["heat", "--yes"],
            ["power", "unit-a", "toggle", "--yes"],
            ["heat", "unit-a", "--wait", "nan"],
            ["watch", "unit-a", "--duration", "0"],
        ):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                main(argv)
            self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
