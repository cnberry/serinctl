# Local HomeKit transport

Reference: [firmware v0.2.5](https://github.com/akifbayram/mitsubishi-cn105-homekit/tree/c4f9088789e30eba2f7cadb92622c21d23370a86),
especially `main/web_server.cpp` and `main/web_ws.cpp`.
The manufacturer manifest inspected at
[`d274383`](https://github.com/Serin-Labs/serin-cn105/blob/d274383a8c4f73da56559dc38891257ca6ff7dc9/firmware/homekit/manifest.json)
also lists stable 0.2.5.

The HTTP server registers `/ws`. A WebSocket handshake triggers state and device
information; periodic state pushes follow. `serinctl` receives until a
`type: state` frame arrives under a bounded deadline, without sending application
messages. WebSocket protocol handshake/close frames still occur.

The state contains `connected`, `power`, `mode`, `target`, `room`, `operating`,
and compressor diagnostics. Target and room temperatures come directly from
the controller's Celsius state. Display preference `tempUnit` does not convert
these transport fields. Missing or invalid optional fields become JSON null.

The same payload includes `ssid`, `deviceName`, `hkSetupCode`, `hkSetupURI`,
and potentially location/sensor identity. Output is a fixed allowlist with
typed values, not a blacklist. Unknown modes are null, preventing arbitrary
device strings from passing into output.

Future control: upstream `cmd: set` may immediately broadcast wanted values
before hardware acknowledges them. A matching echo alone cannot establish a
successful physical write. Resolve confirmation semantics before adding writes.

No live-device response has been validated yet. Label and source inspection
are evidence for implementation, not a claim of tested hardware compatibility.
