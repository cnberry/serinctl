# Setup and troubleshooting

Serin requires a **2.4 GHz** home Wi-Fi network. Join its setup access point,
open `http://192.168.4.1`, and enter home Wi-Fi details. After the controller
restarts, return the phone to home Wi-Fi and check the router's device list.
See the [official HomeKit setup guide](https://serin-labs.com/homekit/setup.html).

A shared 2.4/5 GHz SSID need not be split permanently. If onboarding fails,
try the router's temporary 2.4 GHz setup mode when available. Distinguish failure
to join the setup access point from failure to join the home network.

On eero: Settings → Troubleshooting → My device won't connect → My device is
2.4 GHz only → Pause 5 GHz and 6 GHz. Retry onboarding with the normal home
SSID. The other bands automatically resume after 10 minutes.
[Official eero instructions](https://eero.com/support/articles/how-do-i-temporarily-hide-the-5-and-6-ghz-bands).

If `.local` resolution fails, use the controller IP shown by the router with
`--host`. Check that the client and controller can communicate across the LAN.
Avoid guest-network isolation for local controller access.

`controller unavailable` can mean DNS, power, network, or WebSocket failure.
`unsupported or malformed controller state` means the response did not match
the supported firmware shape. Do not dump raw state into a public issue.
`heat pump disconnected` means the web controller answered but its CN105 link
is down; temperatures and power are intentionally unknown.

Keep the existing firmware during initial setup. The manufacturer's guide also
offers USB Wi-Fi provisioning without reinstalling firmware.
