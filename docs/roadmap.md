# Roadmap

Version 0.3.0 implements the [everyday commands](commands.md): heat, cool, temp,
status, watch, power/mode/fan/vanes, combined set, capabilities, and inventory.
All use Python plus the existing local WebSocket transport.

1. Validate authorized comfort changes on the installed indoor unit, including
   its actual supported modes, vane settings, and temperature precision.
2. Review the staged private home-config kitchen dial before merging and deploying.
3. Improve hardware confirmation if upstream exposes a settings-sample sequence
   or CN105 acknowledgment; current matching readback retains acknowledgment unknown.

Wi-Fi commissioning and connected/disconnected reads are verified on HomeKit
v0.2.5. Control writes have only simulated transport tests so far. Retain only
sanitized evidence from future live validation.

Administration belongs to Codex's direct workflows. Sensors, firmware, pairing,
Wi-Fi, resets, presets, timers, and schedules stay outside the CLI. ESPHome and
Matter would require separate adapters with their own evidence and tests.
