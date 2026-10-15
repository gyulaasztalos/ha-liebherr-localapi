"""Constants for the Liebherr LocalAPI integration."""

from datetime import timedelta

DOMAIN = "liebherr_localapi"

DEFAULT_PORT = 8080
SCAN_INTERVAL = timedelta(seconds=30)

# Writable routes from the LocalAPI spec (v1.22.10). Firmware registers only a
# subset of them, so each one is probed with OPTIONS at setup before an entity
# is created for it.
APPLIANCE_ROUTES = (
    ("PUT", "appliance/setting/acoustic-alarm"),
    ("PUT", "appliance/setting/child-lock"),
    ("PUT", "appliance/setting/eco-mode"),
)
ZONE_ROUTES = (
    ("PUT", "zones/{zone}/temperature"),
    ("PUT", "zones/{zone}/temperature/alarm/refresh-time"),
    ("DELETE", "zones/{zone}/temperature/alarm/upper"),
    ("DELETE", "zones/{zone}/temperature/alarm/lower"),
    ("DELETE", "zones/{zone}/alarm/power-failure-alarm/upper"),
    ("DELETE", "zones/{zone}/alarm/power-failure-alarm/lower"),
    ("DELETE", "zones/{zone}/alarm/emergency-alarm"),
    ("DELETE", "zones/{zone}/door/alarm"),
    ("PUT", "zones/{zone}/door/alarm/delay"),
    ("PUT", "zones/{zone}/supercool"),
    ("PUT", "zones/{zone}/superfrost"),
    ("PUT", "zones/{zone}/humidity"),
    ("PUT", "zones/{zone}/humidifier/mode"),
)

ZONE_POSITIONS = {0: "top", 1: "bottom", 2: "middle"}
