# Hardware intake

Two recent Immich photos were reviewed locally on 2026-09-08. The kit label
identifies a Serin Labs controller, a CN105 cable, and HomeKit-compatible
firmware v0.2.5. A local web app and Apple Home pairing are printed setup paths.
Device identity and pairing data are intentionally omitted here. Originals
remain in Immich; no setup photo belongs in this public repository.

Live reads confirm LAN access, a state stream reporting CN105 disconnected, and
M5Stack NanoC6 hardware running HomeKit v0.2.5 / ESP-IDF v5.5.4. Still to confirm:
indoor-unit model, physical installation, and connected CN105 equipment state.

Follow the manufacturer's [installation and setup guide](https://serin-labs.com/homekit/setup.html).
Power off at the breaker before opening the indoor unit; disconnect USB before
connecting CN105. Wi-Fi commissioning and HomeKit pairing are separate steps.
