"""Setup, unload and entity discovery tests."""

from __future__ import annotations

import copy

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.liebherr_localapi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import BASE_URL, SERIAL, FakeAppliance

# Every entity the real BRPSvh 6501 (firmware 3.2.4.0) gets
REAL_ENTITIES = {
    "binary_sensor.liebherr_brpsvh_6501_child_lock",
    "binary_sensor.liebherr_brpsvh_6501_cooling",
    "binary_sensor.liebherr_brpsvh_6501_door",
    "binary_sensor.liebherr_brpsvh_6501_door_alarm",
    "binary_sensor.liebherr_brpsvh_6501_emergency_mode_alarm",
    "binary_sensor.liebherr_brpsvh_6501_failure_alarm",
    "binary_sensor.liebherr_brpsvh_6501_high_temperature_alarm",
    "binary_sensor.liebherr_brpsvh_6501_low_temperature_alarm",
    "binary_sensor.liebherr_brpsvh_6501_manual_defrost",
    "binary_sensor.liebherr_brpsvh_6501_power_failure_high_temperature_alarm",
    "binary_sensor.liebherr_brpsvh_6501_power_failure_low_temperature_alarm",
    "button.liebherr_brpsvh_6501_confirm_door_alarm",
    "button.liebherr_brpsvh_6501_confirm_emergency_mode_alarm",
    "button.liebherr_brpsvh_6501_confirm_high_temperature_alarm",
    "button.liebherr_brpsvh_6501_confirm_low_temperature_alarm",
    "button.liebherr_brpsvh_6501_confirm_power_failure_high_temperature_alarm",
    "button.liebherr_brpsvh_6501_confirm_power_failure_low_temperature_alarm",
    "number.liebherr_brpsvh_6501_door_alarm_delay",
    "number.liebherr_brpsvh_6501_target_temperature",
    "number.liebherr_brpsvh_6501_temperature_alarm_repeat_time",
    "sensor.liebherr_brpsvh_6501_failure_codes",
    "sensor.liebherr_brpsvh_6501_high_temperature_alarm_delay",
    "sensor.liebherr_brpsvh_6501_high_temperature_alarm_threshold",
    "sensor.liebherr_brpsvh_6501_low_temperature_alarm_delay",
    "sensor.liebherr_brpsvh_6501_low_temperature_alarm_threshold",
    "sensor.liebherr_brpsvh_6501_temperature",
    "switch.liebherr_brpsvh_6501_acoustic_alarm",
}


def _entity_ids(hass: HomeAssistant, entry: MockConfigEntry) -> set[str]:
    registry = er.async_get(hass)
    return {
        e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The entry loads, registers one device, and unloads cleanly."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, SERIAL)}
    assert device.manufacturer == "Liebherr"
    assert device.model == "BRPSvh 6501"
    assert device.model_id == "994553903"
    assert device.serial_number == SERIAL
    assert device.sw_version == "3.2.4.0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """An unreachable appliance leaves the entry retrying, not failed."""
    aioclient_mock.get(f"{BASE_URL}/appliance/info", exc=aiohttp.ClientError())
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_route_probe_fails(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """An appliance error while probing routes retries setup, not drops controls."""
    appliance.probe_status = 504
    serve()
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_without_serial_number(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """An appliance description without a serial number is not set up."""
    del appliance.info["serialNo"]
    serve()
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_real_appliance_entities(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Entities follow the real fridge's caps and the routes it serves.

    Child lock has a capability flag and a state field but no route, so it is a
    read-only binary sensor, not a switch. Eco mode has a route but neither a
    flag nor a state field, so nothing is created for it.
    """
    assert _entity_ids(hass, setup_integration) == REAL_ENTITIES


async def test_feature_rich_appliance_entities(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """Features appear once the firmware reports and serves them."""
    appliance.zone_info["caps"]["superCool"] = 1
    appliance.zone_state["superCool"] = 1
    appliance.info["caps"]["ecoMode"] = 1
    appliance.state["ecoMode"] = 2
    appliance.info["caps"]["childLock"] = 1
    appliance.routes |= {
        ("PUT", "zones/0/supercool"),
        ("PUT", "appliance/setting/child-lock"),
    }
    serve()

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entities = _entity_ids(hass, config_entry)
    assert "switch.liebherr_brpsvh_6501_supercool" in entities
    assert "switch.liebherr_brpsvh_6501_child_lock" in entities
    assert "select.liebherr_brpsvh_6501_eco_mode" in entities
    # The read-only fallback disappears once the switch exists
    assert "binary_sensor.liebherr_brpsvh_6501_child_lock" not in entities

    assert hass.states.get("switch.liebherr_brpsvh_6501_supercool").state == "on"
    assert hass.states.get("select.liebherr_brpsvh_6501_eco_mode").state == "eco_plus"


async def test_alarms_follow_state_when_caps_under_report(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """An alarm in the zone state counts as supported even with its cap at 0."""
    caps = appliance.zone_info["caps"]
    caps["emergencyAlarm"] = 0
    caps["doorAlarm"] = 0
    # Upper alarm: cap 0 and no state field, so it is really not there
    caps["upperTemperatureAlarm"] = 0
    del appliance.zone_state["temperatureAlarm"]["upper"]
    serve()

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entities = _entity_ids(hass, config_entry)
    assert "binary_sensor.liebherr_brpsvh_6501_emergency_mode_alarm" in entities
    assert "button.liebherr_brpsvh_6501_confirm_emergency_mode_alarm" in entities
    assert "binary_sensor.liebherr_brpsvh_6501_door_alarm" in entities
    assert "number.liebherr_brpsvh_6501_door_alarm_delay" in entities
    assert "binary_sensor.liebherr_brpsvh_6501_high_temperature_alarm" not in entities
    assert "button.liebherr_brpsvh_6501_confirm_high_temperature_alarm" not in entities


async def test_refresh_time_with_lower_alarm_only(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """The alarm refresh time also applies to a zone with only a low alarm."""
    appliance.zone_info["caps"]["upperTemperatureAlarm"] = 0
    del appliance.zone_state["temperatureAlarm"]["upper"]
    del appliance.zone_state["temperatureAlarm"]["refreshTime"]
    serve()

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert "number.liebherr_brpsvh_6501_temperature_alarm_repeat_time" in (
        _entity_ids(hass, config_entry)
    )


def _two_zone(appliance: FakeAppliance) -> None:
    """Give the appliance a bottom zone next to its top zone."""
    bottom_info = copy.deepcopy(appliance.zone_info)
    bottom_info["position"] = 1
    appliance.extra_zones.append((bottom_info, copy.deepcopy(appliance.zone_state)))


async def test_multi_zone_child_devices(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """Each zone of a multi-zone appliance is a child device of the appliance."""
    _two_zone(appliance)
    serve()

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    (parent,) = dr.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert parent.identifiers == {(DOMAIN, SERIAL)}
    children = dr.async_entries_for_parent_device(registry, parent.id)
    assert {(c.name, frozenset(c.identifiers)) for c in children} == {
        ("Top zone", frozenset({(DOMAIN, f"{SERIAL}_zone0")})),
        (
            "Bottom zone",
            frozenset({(DOMAIN, f"{SERIAL}_zone1")}),
        ),
    }

    bottom = registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{SERIAL}_zone1"), config_entry.entry_id
    )
    temperature = er.async_get(hass).async_get(
        "sensor.liebherr_brpsvh_6501_bottom_zone_temperature"
    )
    assert temperature.device_id == bottom.id
    # Appliance-level entities stay on the appliance device
    door = er.async_get(hass).async_get("switch.liebherr_brpsvh_6501_acoustic_alarm")
    assert door.device_id == parent.id


async def test_zone_with_unknown_position(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """A zone in a position the integration does not know is named by number."""
    _two_zone(appliance)
    appliance.extra_zones[0][0]["position"] = 7
    serve()

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    child = dr.async_get(hass).async_get_child_device_by_identifier(
        (DOMAIN, f"{SERIAL}_zone1"), config_entry.entry_id
    )
    assert child.name == "Zone 1"


async def test_zone_devices_become_child_devices(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    config_entry: MockConfigEntry,
    serve,
) -> None:
    """Zone devices of an earlier version turn into child devices, keeping their id."""
    _two_zone(appliance)
    serve()
    config_entry.add_to_hass(hass)

    # What earlier versions registered: full zone devices linked to the appliance
    registry = dr.async_get(hass)
    parent = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, SERIAL)}
    )
    old_zone_ids = {
        zone: registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, f"{SERIAL}_zone{zone}")},
            manufacturer="Liebherr",
            via_device_id=parent.id,
        ).id
        for zone in (0, 1)
    }
    # Those came from an earlier run, as after a restart, not from this setup
    registry.async_config_entry_unloaded(config_entry.entry_id)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert dr.async_entries_for_config_entry(registry, config_entry.entry_id) == [
        registry.async_get(parent.id)
    ]
    for zone, device_id in old_zone_ids.items():
        child = registry.async_get_child_device_by_identifier(
            (DOMAIN, f"{SERIAL}_zone{zone}"), config_entry.entry_id
        )
        assert child.id == device_id
        assert child.parent_device_id == parent.id
