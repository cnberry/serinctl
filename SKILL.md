---
name: serinctl
description: Set up private Serin CN105 controller inventory, inspect local HomeKit firmware, and find registered controllers after address changes.
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

The current release is read-only and targets HomeKit v0.2.5. Live reads verified
hardware metadata and disconnected-CN105 handling; connected equipment telemetry
remains unverified. Do not claim writes, ESPHome, or Matter support. Send no
arbitrary WebSocket commands. Preserve unknown values and nonzero exit codes.
Raw frames contain pairing secrets; use only the CLI's allowlisted output.
