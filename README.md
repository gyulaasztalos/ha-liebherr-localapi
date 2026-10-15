# Liebherr LocalAPI for Home Assistant

Local polling integration for Liebherr business fridges and freezers with a
**SmartModule**, using the appliance's own REST API on port 8080. No cloud,
no SmartMonitoring licence.

Tested with a BRPSvh 6501 (SmartModule firmware 3.2.4.0) on Home Assistant 2026.10.

## Activate the LocalAPI (once)

1. On the appliance, switch Wi-Fi **on** (do a Wi-Fi reset if credentials are already set).
2. Join the appliance's access point (SSID and password are shown on its display).
3. Open `http://192.168.1.1:8080/onboarding/#/localapi` and activate the LocalAPI.
4. Configure Wi-Fi or switch back to LAN. The API is then on `http://<appliance-ip>:8080`.

The API has **no authentication**. Anyone who can reach port 8080 can change
the setpoint, so firewall it so only Home Assistant can reach it.

## Install

HACS → Custom repositories → add this repository (type *Integration*), install,
restart Home Assistant, then *Settings → Devices & services → Add integration →
Liebherr LocalAPI* and enter the appliance's IP.

## What you get

One device per appliance. Multi-zone appliances get one extra device per zone.

Entities are created from the appliance's capability flags **and** the routes
its firmware actually serves (probed with `OPTIONS` at setup). A feature shows
up only when the API can read or change it. Reload the integration after a
firmware update to pick up new routes.

| Platform | Entities |
|---|---|
| sensor | temperature, humidity, high/low temperature alarm threshold and delay, failure codes |
| binary_sensor | door, cooling, manual defrost, door / high & low temperature / power-failure / emergency / failure alarms (with `confirmed` attribute); read-only acoustic alarm, child lock, SuperCool, SuperFrost when the firmware has no route to change them |
| number | target temperature, target humidity, temperature alarm repeat time, door alarm delay |
| switch | acoustic alarm, child lock, SuperCool, SuperFrost |
| select | eco mode, humidifier mode |
| button | confirm door / temperature / power-failure / emergency alarm |

*Door alarm delay* is write-only in the API. The entity shows the last value set
from Home Assistant and is unknown until set once.

Diagnostics (*device page → Download diagnostics*) dump the raw API documents
and the list of served routes.

## Known gaps on BRPSvh 6501 / firmware 3.2.4.0

The appliance has SuperCool, a humidity function and an interior light, but this
firmware exposes none of them over the LocalAPI. The SuperCool and humidity routes
return 404, and the API has no light or fan endpoint at all. They will appear
automatically if a firmware update adds the routes.
