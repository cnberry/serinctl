# Roadmap

1. **Connected equipment:** Wi-Fi commissioning and initial disconnected-CN105
   reads are verified. Runtime firmware is verified as v0.2.5. Confirm indoor-unit model, establish
   CN105 connectivity, and validate telemetry against the local web app.
   Retain only sanitized fixtures.
2. **Private deployment:** register `serinctl` with the home-config bootstrap
   using the native inventory already stored outside this public repository.
3. **Deliberate controls:** exact target, current connected state, explicit
   `--yes`, validated temperature/mode limits, bounded confirmation, and readback
   that distinguishes wanted settings from acknowledged CN105 state.
4. **More comfort:** fan and vane support, optional Fahrenheit presentation,
   and richer freshness reporting. Named multi-device inventory, rooms, and
   MAC-verified rediscovery are implemented.

ESPHome and Matter would be separate adapters with their own evidence and tests.
