# Liebherr LocalAPI for Home Assistant

> **Unofficial integration.** Not affiliated with or endorsed by Liebherr. See the [disclaimer](#disclaimer).

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
| binary_sensor | door, cooling, manual defrost, door / high & low temperature / power-failure / emergency / failure alarms (with `confirmed` attribute); acoustic alarm, child lock, SuperCool and SuperFrost as read-only sensors where the appliance reports the state but cannot change it |
| number | target temperature, target humidity, temperature alarm repeat time, door alarm delay |
| switch | acoustic alarm, child lock, SuperCool, SuperFrost |
| select | eco mode, humidifier mode |
| button | confirm door / temperature / power-failure / emergency alarm |

*Door alarm delay* is write-only in the API. The entity shows the last value set
from Home Assistant and is unknown until set once.

Diagnostics (*device page → Download diagnostics*) dump the raw API documents
and the list of served routes.

## Limitations

This integration can only offer what the appliance's LocalAPI exposes. A feature
the appliance has, such as a button on its display, is not available in Home
Assistant unless the firmware serves it through an API endpoint. The capability
flags the appliance reports are not always complete either.

Which endpoints are served depends on the appliance model and the SmartModule
firmware version. A firmware update may add endpoints. Reload the integration
afterwards and any newly supported features appear automatically. The
diagnostics download lists the routes your appliance serves.

## Disclaimer

This is an **unofficial** integration, developed independently. It is not
affiliated with, endorsed by, sponsored by, or in any way officially connected
to Liebherr-International AG or any of its subsidiaries or affiliates. The name
"Liebherr" and related names, marks, and logos are trademarks of their
respective owners. They are used here only to identify compatible appliances.
The integration icon is original artwork, not a Liebherr logo.

The software is provided "as is", without warranty of any kind. Use it at your
own risk. The author accepts no liability for damage to appliances, spoiled
goods, failed temperature monitoring or alarms, or any other loss arising from
its use. Do not rely on it as your only means of temperature monitoring or
alarming, for example for HACCP or for medical or laboratory storage. See
[LICENSE](LICENSE) for the full terms.

## Development

The tests run against a fake appliance built from JSON captured on a real
BRPSvh 6501 (`tests/fixtures/`, serial numbers replaced), using Home Assistant's
own test harness:

```bash
pip install -r requirements_test.txt
pytest
```

`pytest-homeassistant-custom-component` pins the Home Assistant version; bump it
in `requirements_test.txt` to test against a newer release. CI runs Ruff and the
tests on every push.

## Releasing

HACS offers GitHub releases as updates. To publish one, bump `version` in
`custom_components/liebherr_localapi/manifest.json`, commit, then push a
matching tag:

```bash
git tag v1.0.1
git push origin v1.0.1
```

The release workflow refuses to publish if the tag doesn't match `manifest.json`.

## License

[MIT](LICENSE)
