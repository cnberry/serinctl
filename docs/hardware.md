# Hardware intake

Two recent Immich photos were reviewed locally on 2026-09-08. The kit label
identifies a Serin Labs controller, a CN105 cable, and HomeKit-compatible
firmware v0.2.5. A local web app and Apple Home pairing are printed setup paths.
Device identity and pairing data are intentionally omitted here. Originals
remain in Immich; no setup photo belongs in this public repository.

Live reads confirm LAN access, both disconnected and subsequently connected
CN105 state, and M5Stack NanoC6 hardware running HomeKit v0.2.5 / ESP-IDF v5.5.4.
The connected snapshot followed the user attaching the controller to the AC
unit. The indoor-unit model, its supported controls, and control-write
confirmation still need verification.

Follow the manufacturer's [installation and setup guide](https://serin-labs.com/homekit/setup.html).
Power off at the breaker before opening the indoor unit; disconnect USB before
connecting CN105. Wi-Fi commissioning and HomeKit pairing are separate steps.
