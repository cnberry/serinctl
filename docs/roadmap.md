# Roadmap

1. **First read:** finish Wi-Fi commissioning, confirm installed firmware and
   indoor-unit model, validate status against the local web app, and retain only
   sanitized fixtures.
2. **Private deployment:** register `serinctl` with the home-config bootstrap
   and place the actual target outside this public repository.
3. **Deliberate controls:** exact target, current connected state, explicit
   `--yes`, validated temperature/mode limits, bounded confirmation, and readback
   that distinguishes wanted settings from acknowledged CN105 state.
4. **More comfort:** fan and vane support, optional Fahrenheit presentation,
   richer freshness reporting, and multiple named units as needed.

ESPHome and Matter would be separate adapters with their own evidence and tests.
