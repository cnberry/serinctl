<p align="center">
  <img src="docs/assets/serinctl-hero.png" alt="A tiny coral robot adjusts a mini-split thermostat" width="100%">
</p>

# serinctl

> **Big comfort. One tiny command.**
>
> Check the room. Know the state. Keep your cool.

`serinctl` is a small Python CLI for controlling and inspecting a Serin Labs CN105 mini-split
controller over the local network. Same little-robot energy as `poolctl` and
`gatectl`: small commands, private configuration, readable output, and honest
equipment state.

## Firmware attribution

Thanks to [Serin Labs](https://serin-labs.com/) for the Serin controller and
the firmware distribution, setup guides, and local interface this CLI builds on.
The current adapter targets HomeKit firmware v0.2.5 distributed through
[Serin Labs' firmware repository](https://github.com/Serin-Labs/serin-cn105).
That firmware is built from
[Mitsubishi CN105 HomeKit Controller](https://github.com/akifbayram/mitsubishi-cn105-homekit/tree/v0.2.5),
by Mehmet Bayram and contributors, whose firmware source is MIT-licensed.

`serinctl` supplies the command-line client. Credit for the controller firmware,
CN105 implementation, and HomeKit integration belongs to the upstream projects
and their contributors.

## Everyday comfort

```bash
serinctl status serin-demo --unit F
serinctl heat serin-demo --temp 71 --unit F --yes
serinctl cool serin-demo --temp 74 --unit F --yes
serinctl temp serin-demo 72 --unit F --yes
serinctl watch serin-demo --unit F
```

The primary commands are **heat, cool, temp, status, and watch**. Supporting
commands cover power, mode, fan, both vane directions, combined settings,
capabilities, inventory, and discovery. See the [command reference](docs/commands.md).
Runtime dependencies remain Python and `websockets`; routine use needs no Codex,
cloud account, browser, or background service.

Controls target an exact registered ID with a pinned MAC and HomeKit firmware
v0.2.5. Add `--dry-run` to validate a requested change without sending it; use
`--yes` to execute. Heat/cool without `--temp` preserve the target. `temp`
preserves power and mode; AUTO requires choosing heat or cool first because the
firmware manages its own automatic thresholds. Administration, pairing, sensors,
presets, timers, and schedules stay outside this CLI.

Writes wait for bounded readback beyond the firmware's minimum optimistic
grace period. A match is reported as **post-grace readback matched**, with hardware
acknowledgment unknown. Uncertain writes are never automatically replayed.
Live connected/disconnected reads are verified; control writes have only been
validated against pinned firmware source and simulated transport so far.
ESPHome and Matter are not supported by this adapter.

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
Private deployment configuration stays in `home-config`.

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
| `mac` | Expected Wi-Fi station MAC, required for controls and verified discovery |

IDs use lowercase letters, numbers, hyphens, and underscores. Device IDs, room
IDs, and configured hardware MACs must be unique within their respective sets.
Renaming a device or room does not change its ID. IDs are inventory labels;
`mac` is the hardware identity check.

Reads require an exact device ID when multiple controllers exist; with one
controller it can be omitted. Controls always require an exact registered ID
and pinned MAC. Names and rooms are not implicit target selectors.
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

JSON preserves canonical Celsius fields and adds Fahrenheit display fields.
Targets use Mitsubishi's firmware lookup table, while measured room temperature
uses physical conversion. Use `--unit F` for Fahrenheit input or human output;
Celsius is the default. Valid targets are 16–30.5°C in 0.5° steps or 61–88°F in
whole degrees. `target_f_exact` distinguishes an exact table match from a
fallback display for a Celsius target outside that table.

`controller_reachable` is distinct from `heat_pump_connected`. A received
snapshot proves neither sensor freshness nor physical operation.

| Exit | Meaning |
| --- | --- |
| `0` | Connected read, validated dry run, or post-grace readback match. |
| `1` | Configuration, preflight, transport, or protocol failure before control execution. |
| `2` | CN105 disconnected on reads, or invalid CLI usage. |
| `3` | Control attempted; result unconfirmed. Refresh before deciding on another change. |

Control JSON separates `requested`, `before`, `after`, `command_attempted`,
`command_sent`, `outcome`, and `verification`. `hardware_acknowledged` remains
null even when the readback matches. `--wait` bounds observation (20 seconds by
default); `--wait 0` sends once and immediately returns unconfirmed.

## Notes from the bench

The photographed kit contains a Serin Controller and CN105 cable; its label
states HomeKit-compatible firmware v0.2.5. Runtime metadata also confirms v0.2.5 on an M5Stack NanoC6.
Connected CN105 telemetry is verified; the indoor-unit model and control-write
confirmation remain unverified.
See [hardware notes](docs/hardware.md), [protocol](docs/protocol.md),
[setup troubleshooting](docs/troubleshooting.md), and [roadmap](docs/roadmap.md).

## Control-tool family

- [gatectl](https://github.com/cnberry/gatectl) — gates and garage doors.
- [poolctl](https://github.com/cnberry/poolctl) — pool equipment.
- [hottubctl](https://github.com/cnberry/hottubctl) — hot tub inspection.
- [switchctl](https://github.com/cnberry/switchctl) — named local switches.
- [serinctl](https://github.com/cnberry/serinctl) — local mini-split comfort controls.

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
Mitsubishi Electric. See [Firmware attribution](#firmware-attribution) for
Serin Labs and upstream firmware credits. The adapted temperature lookup's
[upstream MIT notice](THIRD_PARTY_NOTICES.txt) ships with this package.
