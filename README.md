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
- `--json` emits an allowlisted schema, excluding pairing codes and network identity.
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

## Private configuration

Copy [the example](config/controller.example.json) to
`/usr/local/config/serinctl/config.json` with mode `0600`, or select your own
private file with `SERINCTL_CONFIG` or `--config`:

```bash
.venv/bin/serinctl --config /path/to/private/config.json status --json
```

`--host` overrides configuration. No pairing secret is needed for the local
WebSocket read. Keep the controller on a trusted LAN: its web interface also
exposes administrative actions. Raw frames and original setup photos must stay
private. `serinctl` does not save them or offer raw output.

## Output and exit codes

Temperatures are Celsius, matching the firmware transport irrespective of its
web display preference. `controller_reachable` is distinct from
`heat_pump_connected`. Exit `0` means connected equipment state was received,
`1` means configuration, transport, or protocol failure, and `2` means the
controller reports CN105 disconnected (also used by argparse for invalid usage).
A received snapshot is not proof of sensor freshness or physical operation.

## Notes from the bench

The photographed kit contains a Serin Controller and CN105 cable; its label
states HomeKit-compatible firmware v0.2.5. This establishes the starting
firmware target, not confirmation of the installed runtime or indoor-unit model.
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
