---
name: serinctl
description: Inspect a Serin CN105 mini-split controller using local HomeKit firmware.
---

Use `serinctl --host HOST status --json` or private configured targets.
`doctor --json` checks the same controller/CN105 read path. Global options precede
the subcommand. Never infer equipment state from controller reachability alone.

Version 0.1 is read-only, source-grounded in firmware v0.2.5 and awaiting live
validation. Do not claim support for writes, ESPHome, or Matter. Do not send
arbitrary WebSocket commands. Preserve unknown values and report exit failures.
Keep setup codes, original photos, and raw frames private.
