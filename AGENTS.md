# Repository guidance

`serinctl` is a terminal-first Serin CN105 mini-split inspection and control project.

- Keep the `*ctl` family focused on everyday device tasks with minimal external
  dependencies. Routine operation must not require Codex or a cloud service.
- Prioritize `heat`, `cool`, `temp`, `status`, and `watch`. The agreed supporting
  commands are documented in `docs/commands.md`. Codex handles administration
  directly; do not add admin, sensor management, presets, timers, or schedules.
- Keep configuration, transport, protocol shaping, and CLI dispatch separate.
- Ground protocol behavior in the exact installed firmware source and live reads.
- Credit Serin Labs and the upstream firmware authors prominently. Keep CLI
  authorship distinct from firmware authorship, and retain applicable upstream
  credits and notices if firmware code is later reused or adapted.
- Writes require exact pinned target selection, a newly received connected state,
  explicit confirmation, validated limits, and bounded post-grace readback.
  Report hardware acknowledgment as unknown: firmware exposes no proof of it.
- Firmware may echo wanted settings before CN105 confirms them. Never equate
  an optimistic WebSocket echo with completed hardware control.
- Never commit photos containing pairing codes, raw state, MACs, hostnames,
  Wi-Fi credentials, HomeKit data, or private deployment inventory.
- Allowlist public output. Raw WebSocket frames contain HomeKit setup secrets.
- Preserve compact human output, stable JSON, and honest unknown states.
- Keep `script/install` as the language-neutral deployment contract.
- Update README, SKILL.md, and docs with behavior changes.
- Run `just test` before publishing. Automated tests must never contact live HVAC.
