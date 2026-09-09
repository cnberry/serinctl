<p align="center">
  <img src="docs/assets/serinctl-hero.png" alt="A tiny coral robot adjusts a mini-split thermostat" width="100%">
</p>

# serinctl

> **Big comfort. One tiny command.**
>
> Check the room. Know the state. Keep your cool.

`serinctl` is a small Python CLI for inspecting a Serin Labs CN105 mini-split
controller over the local network. Same little-robot energy as `poolctl` and
`gatectl`: small commands, private configuration, readable output, and honest
equipment state.

## First batch: inspection

- `status` reads one equipment snapshot from the HomeKit firmware's `/ws` stream.
- `doctor` performs the same read to check controller and CN105 connectivity.
- Status `--json` emits an allowlisted schema; `--show-identity` adds configured ID/name/room.
- `inspect` reads hardware metadata; `devices` lists inventory; `discover` locates a pinned MAC.
- Disconnected heat pumps report unknown values instead of cached temperatures.

This is an initial read-only implementation grounded in HomeKit firmware v0.2.5.
Live reads have verified controller reachability and the disconnected-CN105
response. Connected heat-pump telemetry is still unverified. ESPHome and Matter firmware are not
supported by this adapter. Power, mode, setpoint, fan, and vane writes are roadmap
work; this release sends no application commands to the controller.

## Get cooking

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/serinctl --host serin-example.local status
.venv/bin/serinctl --host serin-example.local doctor --json
```

Replace the example with the controller hostname or IP from your private setup
card or router. Global options precede the command; `--json` follows it.

For an installed copy, `./script/install` uses the same contract as sibling
tools: `/usr/local/bin/serinctl` backed by an isolated environment under
`/usr/local/lib/home-config/ctls/serinctl`. It may require elevated permissions.
`CTL_INSTALL_PREFIX`, `CTL_VENV_ROOT`, and `CTL_BIN_DIR` support alternate paths.
Registration in the private `home-config` bootstrap is still pending.

## Setup

1. Follow the manufacturer's [hardware and Wi-Fi setup](https://serin-labs.com/homekit/setup.html).
   Use a 2.4 GHz network. Confirm the initial IP in the router's client list.
2. Read the controller's metadata without changing its settings:

   ```bash
   .venv/bin/serinctl --host 192.0.2.10 inspect --json
   ```

   This explicitly displays private hardware identity: board, firmware, ESP-IDF,
   Wi-Fi MAC, IP, and hostname. Confirm the device against its setup card/router
   before enrolling it. It excludes pairing codes and Wi-Fi credentials.
3. Copy [the example JSON](config/controller.example.json) into your private
   configuration repository, or `/usr/local/config/serinctl/config.json`.
   Use mode `0600`. Replace the sample addresses and MACs with verified values.
4. Give each controller a stable `id`, a readable `name`, and a `room_id`.
   Define rooms with stable IDs and readable names in `rooms`. Use `null` for a
   device whose room is not assigned yet. Multiple controllers may share a room.
5. Verify the saved target:

   ```bash
   .venv/bin/serinctl --config /path/to/private/config.json devices
   .venv/bin/serinctl --config /path/to/private/config.json doctor serin-demo --json
   .venv/bin/serinctl --config /path/to/private/config.json status serin-demo --show-identity
   ```

### Configuration fields

| Field | Meaning |
| --- | --- |
| `version` | Inventory format version, currently `1` |
| `rooms` | Room records with stable `id` and editable `name` |
| `devices[].id` | Locally assigned stable identifier, independent of room/name/IP |
| `name` | Editable display name |
| `room_id` | Reference to a room, or `null` |
| `host` | Last known address, optionally with a port |
| `hostname` | Optional DNS/mDNS name, normally the reported hostname plus `.local` |
| `mac` | Optional expected Wi-Fi station MAC, required for verified discovery |

IDs use lowercase letters, numbers, hyphens, and underscores. Device IDs, room
IDs, and configured hardware MACs must be unique within their respective sets.
Renaming a device or room does not change its ID. IDs are inventory labels;
`mac` is the hardware identity check.

An exact device ID is required when multiple controllers exist; with one
controller it can be omitted. Names and rooms are not implicit target selectors.
`devices` lists inventory without network traffic. `SERINCTL_CONFIG` or
`--config` selects a private config. The legacy `{"host": "example.local"}`
shape still works, without identity verification. `--host` is a direct,
unverified override and cannot be combined with a configured device ID.

### Find a controller after its IP changes

For MAC-pinned devices, status tries the configured hostname first, then the
saved address. It checks the `deviceInfo` MAC on the same WebSocket connection
before returning equipment status. A mismatch refuses the read; missing identity
never counts as verification. Firmware metadata is self-reported, so this check
prevents accidental device mix-ups; it is not cryptographic authentication.

```bash
.venv/bin/serinctl --config /path/to/private/config.json discover serin-demo --json
# If hostname and saved address fail, explicitly search your own LAN:
.venv/bin/serinctl --config /path/to/private/config.json discover serin-demo --network 192.168.1.0/24 --json
```

Choose the actual private subnet from your network settings. An explicit scan
probes local port 80 WebSocket endpoints with up to eight concurrent reads and
at most 256 addresses. It returns only a matching configured MAC. Per-endpoint
discovery timeout is capped at two seconds; a full scan may take about a minute
plus connection-close time. Without `--network`, only configured addresses are
tried. Hostname resolution relies on the operating system's DNS/mDNS support.

Discovery displays private network identity but does not edit files. If exactly
one controller matches, update `host` in the private config from the verified
result. Retain the stable ID, MAC, and room. Missing or conflicting results
require investigation; never select the first responding mini-split.

Keep raw frames and setup photos private: the local web interface also exposes
administrative actions. No pairing secret is needed for these reads.

## Output and exit codes

Temperatures are Celsius, matching the firmware transport irrespective of its
web display preference. `controller_reachable` is distinct from
`heat_pump_connected`. Exit `0` means connected equipment state was received,
`1` means configuration, transport, or protocol failure, and `2` means the
controller reports CN105 disconnected (also used by argparse for invalid usage).
A received snapshot is not proof of sensor freshness or physical operation.

## Notes from the bench

The photographed kit contains a Serin Controller and CN105 cable; its label
states HomeKit-compatible firmware v0.2.5. Runtime metadata also confirms v0.2.5 on an M5Stack NanoC6.
The indoor-unit model and connected CN105 telemetry remain unverified.
See [hardware notes](docs/hardware.md), [protocol](docs/protocol.md),
[setup troubleshooting](docs/troubleshooting.md), and [roadmap](docs/roadmap.md).

## Control-tool family

- [gatectl](https://github.com/cnberry/gatectl) — gates and garage doors.
- [poolctl](https://github.com/cnberry/poolctl) — pool equipment.
- [hottubctl](https://github.com/cnberry/hottubctl) — hot tub inspection.
- [switchctl](https://github.com/cnberry/switchctl) — named local switches.
- [serinctl](https://github.com/cnberry/serinctl) — local mini-split inspection.

## Development

```bash
just setup
just test
```

Tests use synthetic WebSocket frames and mock transport. They never contact
equipment. CI checks formatting, lint, secret scanning, and unit tests on
Python 3.11–3.13.

## License

[MIT](LICENSE). Independent project, not affiliated with Serin Labs or
Mitsubishi Electric. Protocol research references the MIT-licensed
[upstream HomeKit firmware](https://github.com/akifbayram/mitsubishi-cn105-homekit/tree/v0.2.5).
