import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from serinctl.cli import main
from serinctl.client import IdentityMismatch, read_status
from serinctl.config import load_inventory, resolve_device
from serinctl.discovery import discover, inspect_device

MAC = "02:00:00:00:00:10"
INFO = {
    "type": "deviceInfo",
    "mac": MAC,
    "board": "Demo board",
    "fw": "v0.2.5",
    "idf": "v5.5.4",
    "hostname": "serin-demo",
    "ip": "192.0.2.10",
}
STATE = {"type": "state", "connected": False}


def inventory():
    return {
        "version": 1,
        "rooms": [{"id": "office", "name": "Office"}],
        "devices": [
            {
                "id": "unit-a",
                "name": "Desk unit",
                "room_id": "office",
                "host": "192.0.2.10",
                "hostname": "serin-demo.local",
                "mac": MAC,
            }
        ],
    }


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "config.json")
        self.save(inventory())

    def save(self, data):
        Path(self.path).write_text(json.dumps(data))

    def test_rename_and_address_change_preserve_selection(self):
        data = inventory()
        data["devices"][0].update(name="New name", host="192.0.2.20")
        self.save(data)
        device = resolve_device(None, self.path, "unit-a")
        self.assertEqual(device.mac, MAC)
        self.assertEqual(device.name, "New name")

    def test_multiple_devices_require_exact_id(self):
        data = inventory()
        data["devices"].append(
            {"id": "unit-b", "name": "Desk unit", "room_id": "office", "host": "192.0.2.11"}
        )
        self.save(data)
        with self.assertRaisesRegex(ValueError, "multiple"):
            resolve_device(None, self.path)
        self.assertEqual(resolve_device(None, self.path, "unit-b").host, "192.0.2.11")
        with self.assertRaisesRegex(ValueError, "unknown device"):
            resolve_device(None, self.path, "Desk unit")

    def test_invalid_inventory_rejected(self):
        for change in ("id", "mac", "host", "room", "version", "mixed"):
            data = inventory()
            if change in ("id", "mac", "host"):
                other = dict(
                    data["devices"][0], id="unit-b", host="192.0.2.11", mac="02:00:00:00:00:11"
                )
                other[change] = data["devices"][0][change]
                data["devices"].append(other)
            elif change == "room":
                data["devices"][0]["room_id"] = "missing"
            elif change == "version":
                data["version"] = True
            else:
                data["host"] = "192.0.2.10"
            self.save(data)
            with self.subTest(change=change), self.assertRaises(ValueError):
                load_inventory(self.path)

    def test_direct_host_cannot_claim_configured_identity(self):
        with self.assertRaises(ValueError):
            resolve_device("192.0.2.11", self.path, "unit-a")

    @patch("serinctl.cli.read_status")
    @patch("serinctl.cli.inspect_device")
    def test_listing_is_offline_and_excludes_network_identity(self, inspect, read):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--config", self.path, "devices", "--json"]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["devices"][0]["room_id"], "office")
        self.assertNotIn(MAC, output.getvalue())
        self.assertNotIn("192.0.2.", output.getvalue())
        inspect.assert_not_called()
        read.assert_not_called()

    @patch("serinctl.discovery.read_status")
    def test_fallback_verifies_same_mac(self, read):
        read.side_effect = [ValueError("unavailable"), {"heat_pump_connected": False}]
        inspect_device(resolve_device(None, self.path))
        self.assertEqual(read.call_count, 2)
        self.assertTrue(all(c.kwargs["expected_mac"] == MAC for c in read.call_args_list))

    @patch("serinctl.discovery.read_status", side_effect=IdentityMismatch("mismatch"))
    def test_identity_mismatch_stops_status(self, read):
        with self.assertRaises(IdentityMismatch):
            inspect_device(resolve_device(None, self.path))
        self.assertEqual(read.call_count, 1)

    @patch("serinctl.discovery.read_info")
    def test_discovery_matches_and_never_changes_config(self, read):
        read.return_value = {k: v for k, v in INFO.items() if k != "type"}
        original = Path(self.path).read_bytes()
        result = discover(resolve_device(None, self.path))
        self.assertEqual(result["hardware"]["mac"], MAC)
        self.assertEqual(Path(self.path).read_bytes(), original)

    @patch("serinctl.discovery.read_info")
    def test_scan_scope_validation_precedes_network(self, read):
        for network in ("0.0.0.0/0", "192.168.0.0/16", "8.8.8.0/24", "::1/128"):
            with self.assertRaises(ValueError):
                discover(resolve_device(None, self.path), network=network)
        read.assert_not_called()

    @patch("serinctl.discovery.read_info")
    def test_subnet_finds_new_address_and_ignores_wrong_device(self, read):
        def reply(url, timeout, expected_mac):
            self.assertEqual(expected_mac, MAC)
            if url == "ws://192.168.10.2/ws":
                return dict(INFO, ip="192.168.10.2")
            raise IdentityMismatch("wrong device")

        read.side_effect = reply
        result = discover(resolve_device(None, self.path), network="192.168.10.0/30")
        self.assertEqual(result["endpoint"], "192.168.10.2")
        self.assertEqual(result["hardware"]["mac"], MAC)

    @patch("serinctl.discovery.read_info")
    def test_conflicting_identity_is_not_selected(self, read):
        read.side_effect = [dict(INFO, ip="192.0.2.10"), dict(INFO, ip="192.0.2.11")]
        with self.assertRaisesRegex(ValueError, "multiple endpoints"):
            discover(resolve_device(None, self.path))

    @patch("serinctl.discovery.read_info")
    def test_unpinned_inventory_cannot_scan(self, read):
        data = inventory()
        del data["devices"][0]["mac"]
        self.save(data)
        with self.assertRaisesRegex(ValueError, "hardware MAC"):
            discover(resolve_device(None, self.path), network="192.168.10.0/30")
        read.assert_not_called()


class IdentityTests(unittest.TestCase):
    @patch("serinctl.client.connect")
    def test_status_waits_for_identity_and_excludes_info(self, connect):
        ws = connect.return_value.__enter__.return_value
        ws.recv.side_effect = [json.dumps(STATE), json.dumps(dict(INFO, hkSetupCode="private"))]
        result = read_status("ws://example.local/ws", expected_mac=MAC)
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn(MAC, json.dumps(result))
        ws.send.assert_not_called()

    @patch("serinctl.client.connect")
    def test_wrong_hardware_refused(self, connect):
        ws = connect.return_value.__enter__.return_value
        ws.recv.side_effect = [json.dumps(STATE), json.dumps(dict(INFO, mac="02:00:00:00:00:11"))]
        with self.assertRaises(IdentityMismatch):
            read_status("ws://example.local/ws", expected_mac=MAC)

    @patch("serinctl.client.connect")
    def test_missing_identity_cannot_return_state(self, connect):
        ws = connect.return_value.__enter__.return_value
        ws.recv.side_effect = [json.dumps(STATE), TimeoutError()]
        with self.assertRaises(ValueError):
            read_status("ws://example.local/ws", expected_mac=MAC)


class InspectTests(unittest.TestCase):
    @patch("serinctl.cli.read_info")
    def test_inspect_requires_explicit_host(self, read):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["inspect", "--json"]), 1)
        read.assert_not_called()

    @patch("serinctl.client.connect")
    def test_info_before_state_and_metadata_allowlist(self, connect):
        from serinctl.client import read_info

        ws = connect.return_value.__enter__.return_value
        ws.recv.side_effect = [json.dumps(dict(INFO, hkSetupCode="private", ssid="private"))]
        info = read_info("ws://example.local/ws")
        self.assertEqual(info["mac"], MAC)
        self.assertNotIn("private", json.dumps(info))
        ws.recv.side_effect = [json.dumps(INFO), json.dumps(STATE)]
        self.assertFalse(
            read_status("ws://example.local/ws", expected_mac=MAC)["heat_pump_connected"]
        )
