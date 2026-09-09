# Everyday commands

Available in v0.3.0. Commands below use the local HomeKit v0.2.5 interface.

The `*ctl` family prioritizes everyday tasks with minimal external dependencies.
Keep Python and the existing WebSocket transport sufficient for Serin's routine
operations. Reuse that transport for controls and watching; do not add a cloud
SDK, browser automation, daemon, or TUI framework to perform these tasks.

## Primary commands

All examples start with `serinctl`. `ID` is the exact configured device ID.
Reads retain the existing optional ID for a single configured controller.

| Command | State | Meaning |
| --- | --- | --- |
| `status [ID]` | Implemented | Read one snapshot; distinguish powered on from operating. |
| `watch [ID]` | Implemented | Observe changes on a foreground WebSocket connection. Ctrl-C ends observation without changing the unit. |
| `heat ID [--temp VALUE] [--unit C/F] --yes` | Implemented | Turn on, select heat, and optionally set temperature. |
| `cool ID [--temp VALUE] [--unit C/F] --yes` | Implemented | Turn on, select cool, and optionally set temperature. |
| `temp ID VALUE [--unit C/F] --yes` | Implemented | Change only the setpoint; preserve power and mode. |

Heat/cool preserve the current target when no temperature is supplied, and
preserve fan and vane settings. Celsius remains the explicit default; Fahrenheit
is selected with `--unit F`. Never infer units from the value. Validate the
firmware's supported range and increments, and report the effective setpoint.
Celsius targets allow 16–30.5 in 0.5° steps; Fahrenheit uses the firmware table
for whole degrees 61–88 (71°F maps to 22°C). Hardware half-degree precision is
not exposed by the firmware. A target write in AUTO is rejected; choose heat or
cool explicitly first. Horizontal positions are `ll`, `l`, `c`, `r`, `rr`,
`split`, and `swing`; there is no horizontal `auto`.

## Supporting commands

| Command | State | Meaning |
| --- | --- | --- |
| `devices` | Implemented | List registered controllers and their room assignments. |
| `discover [ID]` | Implemented | Locate a registered controller by its pinned identity. |
| `--host IP inspect` | Implemented | Inspect allowlisted hardware identity and firmware. |
| `doctor [ID]` | Implemented | Read controller/CN105 connectivity. |
| `capabilities ID` | Implemented | Distinguish configured firmware options from verified unit support. |
| `power ID on/off --yes` | Implemented | Set power explicitly. |
| `mode ID MODE --yes` | Implemented | Select heat, cool, dry, fan, or auto where supported; preserve power. |
| `fan ID SPEED --yes` | Implemented | Select auto, quiet, or firmware speeds 1–4 where supported. |
| `vane ID POSITION --yes` | Implemented | Select automatic, positions 1–5, or vertical swing where supported. |
| `wide-vane ID POSITION --yes` | Implemented | Select horizontal direction, split, or swing where supported. |
| `set ID [SETTING FLAGS] --yes` | Implemented | Apply several requested settings through the shared control implementation. |

Keep compact human output and stable allowlisted JSON. `watch --jsonl` emits a
JSON-lines stream; `--duration SECONDS` bounds observation and `--interval`
sets the minimum human display interval; receipt time must not be presented
as proof of a fresh hardware measurement. Existing global options precede the
command, and output options follow it.

Controls require an exact registered device, matching hardware identity, a
newly received connected state, validated settings, and bounded readback. `--yes` is
the noninteractive execution flag: Codex may supply it for a change the user
has already authorized without asking the same question again. A controller's
immediate echo is not hardware confirmation; report unconfirmed outcomes
honestly and do not automatically retry an uncertain write.

## Validate and combine

```bash
serinctl cool serin-demo --temp 74 --unit F --dry-run --json
serinctl set serin-demo --power on --mode heat --temp 22 --fan auto --yes
serinctl watch serin-demo --duration 60 --jsonl
```

A dry run performs identity, firmware, connection, and setting checks without
sending a command; it does not require `--yes`. Combined `set` accepts
`--power`, `--mode`, `--temp`, `--fan`, `--vane`, and `--wide-vane`, leaving
unspecified settings out of the wire request.

Control observation lasts up to `--wait SECONDS` (default 20, maximum 60).
After the initial matching echo, readback waits out the 10-second firmware grace
period and requires two distinct later controller frames. Result
`readback_match` means only that those frames match. The firmware provides no
CN105 acknowledgment field or equipment sample timestamp, so hardware
acknowledgment remains unknown. Exit 3 indicates an unconfirmed attempt; no
reconnect or automatic retry occurs after sending starts.

`capabilities` reports configured firmware permissions, not verified indoor-unit
support. `watch` never sends application commands; Ctrl-C stops observation.

## Scope boundary

Controller administration is handled directly by Codex when requested, using
the relevant firmware evidence and private configuration. Do not add CLI
commands for firmware updates, reboot/reset, Wi-Fi setup, HomeKit/remote pairing,
sensor management, display administration, presets, timers, or schedules.
Named room metadata remains part of the existing private inventory.

All controls share validation and transport. Automated tests use only synthetic
frames and fake WebSockets; live control writes remain unverified.
