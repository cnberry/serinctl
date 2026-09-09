import contextlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from serinctl.cli import main
from serinctl.client import read_status
from serinctl.config import controller_url, resolve_url
from serinctl.protocol import summarize


def sample(**updates):
    return {
        "type": "state",
        "connected": True,
        "power": True,
        "mode": "cool",
        "target": 23.5,
        "room": 25.0,
        "operating": False,
        **updates,
    }


class ProtocolTests(unittest.TestCase):
    def test_secrets_and_unknown_strings_never_pass_through(self):
        result = summarize(
            sample(
                hkSetupCode="private-code",
                hkSetupURI="private-uri",
                ssid="private-network",
                deviceName="private-name",
                mode="private-mode",
                target="private-temperature",
                extra={"secret": "private-extra"},  # pragma: allowlist secret (synthetic fixture)
            )
        )
        self.assertNotIn("private", json.dumps(result))
        self.assertIsNone(result["mode"])
        self.assertIsNone(result["target_c"])

    def test_disconnected_values_are_not_equipment_state(self):
        result = summarize(sample(connected=False))
        self.assertTrue(result["controller_reachable"])
        self.assertFalse(result["heat_pump_connected"])
        for key in ("power", "mode", "target_c", "room_c", "operating"):
            self.assertIsNone(result[key])

    def test_celsius_is_independent_of_display_preference(self):
        result = summarize(sample(tempUnit="F"))
        self.assertEqual(result["target_c"], 23.5)

    def test_nonfinite_and_boolean_numbers_become_null(self):
        for value in (math.nan, math.inf, True, "23"):
            self.assertIsNone(summarize(sample(target=value))["target_c"])

    def test_connection_type_is_required(self):
        for value in (None, "true", 1):
            with self.assertRaises(ValueError):
                summarize(sample(connected=value))


class ConfigTests(unittest.TestCase):
    def test_rejects_credentials_paths_and_invalid_ports(self):
        for host in (
            "",
            "http://example.local",
            "user:secret@host",
            "host/path",
            "host?q=1",
            "host#fragment",
            "host:0",
            "host:65536",
            "host\n",
        ):
            with self.subTest(host=host), self.assertRaises(ValueError):
                controller_url(host)

    def test_private_file_and_override(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text('{"host": "example.local:8080"}')
            self.assertEqual(resolve_url(None, str(path)), "ws://example.local:8080/ws")
            self.assertEqual(resolve_url("[::1]", str(path)), "ws://[::1]/ws")


class ClientTests(unittest.TestCase):
    @patch("serinctl.client.connect")
    def test_skips_nonstate_frames_without_sending(self, connect):
        ws = connect.return_value.__enter__.return_value
        ws.recv.side_effect = ['{"type":"log","message":"private"}', json.dumps(sample())]
        self.assertEqual(read_status("ws://example.local/ws")["room_c"], 25.0)
        ws.send.assert_not_called()
        self.assertIsNone(connect.call_args.kwargs["proxy"])

    @patch("serinctl.client.connect")
    def test_error_does_not_expose_endpoint_or_payload(self, connect):
        connect.side_effect = OSError("private-host and private-secret")
        with self.assertRaisesRegex(ValueError, "controller unavailable") as error:
            read_status("ws://example.local/ws")
        self.assertNotIn("private", str(error.exception))

    @patch("serinctl.client.connect")
    def test_malformed_frame_fails(self, connect):
        connect.return_value.__enter__.return_value.recv.return_value = "private-bad-json"
        with self.assertRaisesRegex(ValueError, "malformed"):
            read_status("ws://example.local/ws")

    @patch("serinctl.client.time.monotonic", side_effect=[0, 6])
    @patch("serinctl.client.connect")
    def test_deadline_includes_handshake(self, connect, clock):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            read_status("ws://example.local/ws", 5)
        connect.return_value.__enter__.return_value.recv.assert_not_called()


class CliTests(unittest.TestCase):
    @patch("serinctl.cli.read_status", return_value=summarize(sample(connected=False)))
    def test_disconnected_json_and_exit(self, read):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--host", "example.local", "doctor", "--json"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output.getvalue())["heat_pump_connected"])

    def test_missing_config_is_json_error(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--config", "/nonexistent/serinctl.json", "status", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("error", json.loads(output.getvalue()))

    def test_invalid_timeout_and_write_command_refused(self):
        for args in (
            ["--timeout", "nan", "status"],
            ["--timeout", "0", "status"],
            ["set", "power", "on", "--yes"],
        ):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
