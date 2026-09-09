---
name: serinctl
description: Control everyday Serin CN105 comfort settings, watch local equipment state, and maintain private controller inventory.
---

## Setup

Use the [README setup section](README.md#setup) and
[example inventory](config/controller.example.json) when onboarding a controller.

- Obtain its initial address from the user's router or known setup context.
  `serinctl --host HOST inspect --json` reads allowlisted private hardware metadata.
  Confirm initial identity against the setup card/router before trusting its MAC.
- Save real configuration in private home-config, never this public repository.
  Keep config files mode `0600`. Add stable device `id`, editable `name`,
  `room_id` (null until assigned), last known `host`, reported `hostname` with
  `.local` as appropriate, and verified `mac`. Preserve existing devices.
- `rooms` contains stable room IDs and editable names. Reuse a room ID for
  multiple units in the same room. Do not infer room from an IP or MAC.
- Run `serinctl --config CONFIG devices --json`, then
  `serinctl --config CONFIG doctor DEVICE_ID --json`.
  Global options precede commands. Multi-device configs require exact IDs.
  Legacy single-host configs work but do not verify hardware identity.

## Inspect and relocate

`status DEVICE_ID --json` returns equipment state. `--show-identity` adds
configured ID/name/room; normal status excludes identity. Listing and discovery
are explicitly private outputs. Never infer equipment state from reachability.

For a registered MAC, status verifies deviceInfo on the same connection and
tries the configured hostname before the saved IP. A mismatch stops the read.
Use `discover DEVICE_ID --json` to probe configured addresses. If needed within
an authorized local discovery task, pass `--network PRIVATE_CIDR` for an explicit
IPv4 scan of /24 or smaller. Discover does not modify config. Update the private
host only after one matching hardware identity is found, preserving its ID,
MAC, and room. Stop on ambiguity; don't select another responding controller.
The MAC is self-reported, not cryptographic authentication.

## Boundaries

Keep the CLI focused on everyday operations with minimal external dependencies.
The [agreed command plan](docs/commands.md) prioritizes heat, cool, temp, status,
and watch, with the accepted supporting inspection and airflow commands.
Controller administration is handled
directly by Codex when requested; do not expand this CLI into firmware, pairing,
Wi-Fi, sensor management, presets, timers, or schedules.

Version 0.3.1 targets HomeKit v0.2.5. Reads and cooling activation with matching
post-grace readback have been verified on hardware. Upgrade 0.3.0 before using
controls: its spaced JSON was silently ignored by the firmware's string parser.
Use exact registered IDs with pinned MACs for writes. `heat ID --temp 71 --unit F
--yes`, `cool`, and `temp` share validation. `--dry-run` checks a proposed change
without sending it. Use `--yes` for a change already authorized by the user;
do not ask them to approve it again. Never actuate equipment as an automated test.

Fahrenheit setpoints use Mitsubishi's table; do not independently convert them.
AUTO rejects a single target; choose heat/cool explicitly. Preserve all
unspecified settings. Readback matching after the optimistic grace period is
not proof of hardware acknowledgment. Exit 3 is uncertain: inspect fresh status
before considering another change, and never automatically repeat a write.

Do not claim ESPHome or Matter support. Send no arbitrary WebSocket commands.
Preserve unknown values and nonzero exit codes. Raw frames contain pairing
secrets; use only the CLI's allowlisted output.
