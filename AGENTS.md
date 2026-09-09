# Repository guidance

`serinctl` is a terminal-first Serin CN105 mini-split inspection and control project.

- Keep configuration, transport, protocol shaping, and CLI dispatch separate.
- Ground protocol behavior in the exact installed firmware source and live reads.
- Current release is read-only. Future writes require exact target selection,
  fresh connected state, explicit confirmation, limits, and verified readback.
- Firmware may echo wanted settings before CN105 confirms them. Never equate
  an optimistic WebSocket echo with completed hardware control.
- Never commit photos containing pairing codes, raw state, MACs, hostnames,
  Wi-Fi credentials, HomeKit data, or private deployment inventory.
- Allowlist public output. Raw WebSocket frames contain HomeKit setup secrets.
- Preserve compact human output, stable JSON, and honest unknown states.
- Keep `script/install` as the language-neutral deployment contract.
- Update README, SKILL.md, and docs with behavior changes.
- Run `just test` before publishing. Automated tests must never contact live HVAC.
