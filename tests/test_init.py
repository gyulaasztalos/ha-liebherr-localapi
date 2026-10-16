"""Setup, unload and entity discovery tests."""

from __future__ import annotations

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
