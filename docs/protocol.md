# Local HomeKit transport

The current controller firmware is provided through
[Serin Labs](https://github.com/Serin-Labs/serin-cn105), using the
MIT-licensed HomeKit firmware by Mehmet Bayram and contributors. `serinctl`
implements a client for that existing interface. See the
[firmware credits](../README.md#firmware-attribution).

Reference: [firmware v0.2.5](https://github.com/akifbayram/mitsubishi-cn105-homekit/tree/c4f9088789e30eba2f7cadb92622c21d23370a86),
especially `main/web_server.cpp` and `main/web_ws.cpp`.
The manufacturer manifest inspected at
[`d274383`](https://github.com/Serin-Labs/serin-cn105/blob/d274383a8c4f73da56559dc38891257ca6ff7dc9/firmware/homekit/manifest.json)
also lists stable 0.2.5.

The HTTP server registers `/ws`. A WebSocket handshake triggers state and device
information; periodic state pushes follow. `serinctl` receives until a
`type: state` frame arrives under a bounded deadline, without sending application
messages during reads. WebSocket protocol handshake/close frames still occur.

The state contains `connected`, `power`, `mode`, `target`, `room`, `operating`,
and compressor diagnostics. Target and room temperatures come directly from
the controller's Celsius state. Display preference `tempUnit` does not convert
these transport fields. Missing or invalid optional fields become JSON null.

The same payload includes `ssid`, `deviceName`, `hkSetupCode`, `hkSetupURI`,
and potentially location/sensor identity. Output is a fixed allowlist with
typed values, not a blacklist. Unknown modes are null, preventing arbitrary
device strings from passing into output.

## Control and readback

Controls use one narrow `cmd: set` frame containing only requested settings,
after same-connection MAC verification, firmware v0.2.5 checking, a newly
received connected state, and validation against configured permissions.
Firmware `modeMask`/`vaneConfig` describe configured options, not measured unit
capabilities. Target bounds are 16–30.5°C with half-degree steps; the old integer
CN105 encoding can truncate half degrees and its precision is not exposed.
AUTO actively derives its target from saved thresholds, so standalone target
writes in final AUTO mode are rejected.

Upstream `getEffectiveState()` broadcasts wanted settings for 10 seconds after
a setter; these are optimistic values. Observation anchors its grace timer at
the first matching echo, consumes intervening frames, checks controller uptime
has advanced beyond grace, then requires two distinct later matching frames.
The result is `readback_match`, never hardware acknowledgment. Other clients can
restart firmware grace, and `connected` can persist without a fresh settings
sample. The WebSocket interface exposes no sample timestamp or explicit CN105
ACK, so `hardware_acknowledged` remains null.

A send attempt is never automatically retried or replayed on another address.
Interruption, mismatch, malformed data, disconnect, or expiration yields an
unconfirmed result. No background service is involved.

Canonical transport targets stay Celsius regardless of `tempUnit`.
Fahrenheit input/display uses the lookup in
[`main/sl2_proto.h`](https://github.com/akifbayram/mitsubishi-cn105-homekit/blob/c4f9088789e30eba2f7cadb92622c21d23370a86/main/sl2_proto.h),
not ordinary physical conversion (71°F maps to 22°C). Room readings do use
physical conversion. The adapted table's MIT notice ships with the client.

Live read-only validation on 2026-09-08 received a state frame from a physical
Serin controller after Wi-Fi commissioning. Both direct target selection and
private configuration worked. The controller reported CN105 disconnected;
the CLI returned exit 2 and null equipment values. No application commands
were sent. A later allowlisted deviceInfo read confirmed an M5Stack NanoC6 running
v0.2.5 (ESP-IDF v5.5.4). After the user attached CN105 to the AC unit, a further
read returned connected equipment telemetry: power on, cooling mode, room and
target temperatures, operating state, and compressor frequency. The CLI returned
exit 0. This verifies the connected read path, not write acknowledgement or
independent sensor accuracy. Device identity and network details belong in
private home-config.


## Identity and discovery

Firmware sends `type: deviceInfo` on connection, including Wi-Fi station `mac`,
`board`, `fw`, `idf`, `ip`, and `hostname`. `inspect` exposes only these fields.
For configured MACs, status waits for both state and matching deviceInfo on the
same connection, regardless of message order. Room/name metadata comes from
private inventory, not firmware. DNS and saved IPs are locators, not identity.

Discovery only accepts the registered MAC; it never sends `cmd` messages, changes
Wi-Fi, or updates inventory. Explicit subnet scans are limited to RFC1918 IPv4
ranges no larger than /24. Ordinary status never initiates a subnet scan.
