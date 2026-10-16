"""Entity state, polling and control tests."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)
from yarl import URL

from custom_components.liebherr_localapi.const import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import BASE_URL, FakeAppliance

PREFIX = "liebherr_brpsvh_6501"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time by one scan interval and let the coordinator refresh."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _calls(aioclient_mock: AiohttpClientMocker, method: str, path: str) -> list:
    url = URL(f"{BASE_URL}/{path}")
    return [
        data
        for call_method, call_url, data, _ in aioclient_mock.mock_calls
        if call_method.upper() == method and call_url == url
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_sensor_values(hass: HomeAssistant) -> None:
    """Sensors read the documented fields of the real fridge."""
    temperature = hass.states.get(f"sensor.{PREFIX}_temperature")
    assert float(temperature.state) == 4.9375
    assert temperature.attributes["unit_of_measurement"] == "°C"
    assert temperature.attributes["state_class"] == "measurement"

    # Alarm level = setpoint 5 + limit 8 / setpoint 5 - limit 2
    high = hass.states.get(f"sensor.{PREFIX}_high_temperature_alarm_threshold")
    low = hass.states.get(f"sensor.{PREFIX}_low_temperature_alarm_threshold")
    assert float(high.state) == 13
    assert float(low.state) == 3
    assert hass.states.get(f"sensor.{PREFIX}_failure_codes").state == "none"
    assert hass.states.get(f"binary_sensor.{PREFIX}_door").state == STATE_OFF
    assert hass.states.get(f"binary_sensor.{PREFIX}_cooling").state == STATE_ON
    assert float(hass.states.get(f"number.{PREFIX}_target_temperature").state) == 5


async def test_alarm_confirmed_attribute(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    serve,
    setup_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Alarm state 2 (active and confirmed) is on, with confirmed=True."""
    appliance.zone_state["doorAlarm"]["state"] = 2
    serve()
    await _poll(hass, freezer)

    door_alarm = hass.states.get(f"binary_sensor.{PREFIX}_door_alarm")
    assert door_alarm.state == STATE_ON
    assert door_alarm.attributes["confirmed"] is True


async def test_temperature_published_every_poll(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An unchanged temperature still produces a state update on each poll."""
    entity_id = f"sensor.{PREFIX}_temperature"
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    await _poll(hass, freezer)
    await _poll(hass, freezer)

    updates = [e for e in events if e.data["entity_id"] == entity_id]
    assert len(updates) == 2
    assert all(float(e.data["new_state"].state) == 4.9375 for e in updates)


async def test_unavailable_while_appliance_fails(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    serve,
    setup_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed poll marks entities unavailable; the next good poll restores them."""
    entity_id = f"sensor.{PREFIX}_temperature"

    appliance.state_status = 504
    serve()
    await _poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    appliance.state_status = 200
    serve()
    await _poll(hass, freezer)
    assert float(hass.states.get(entity_id).state) == 4.9375


@pytest.mark.usefixtures("setup_integration")
async def test_set_target_temperature(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The setpoint is written as a whole number for a 1-degree resolution zone."""
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: f"number.{PREFIX}_target_temperature", "value": 6},
        blocking=True,
    )
    assert _calls(aioclient_mock, "PUT", "zones/0/temperature") == [{"value": 6}]


@pytest.mark.usefixtures("setup_integration")
async def test_door_alarm_delay_written_and_shown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The write-only door alarm delay shows the last value written."""
    entity_id = f"number.{PREFIX}_door_alarm_delay"
    assert hass.states.get(entity_id).state == "unknown"

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 90}, blocking=True
    )
    assert _calls(aioclient_mock, "PUT", "zones/0/door/alarm/delay") == [{"value": 90}]
    assert float(hass.states.get(entity_id).state) == 90


@pytest.mark.usefixtures("setup_integration")
async def test_acoustic_alarm_switch(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Switching writes {"state": 0|1} to the setting route."""
    entity_id = f"switch.{PREFIX}_acoustic_alarm"
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert _calls(aioclient_mock, "PUT", "appliance/setting/acoustic-alarm") == [
        {"state": 0},
        {"state": 1},
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_confirm_alarm_button(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Confirm buttons send DELETE to the alarm route."""
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: f"button.{PREFIX}_confirm_door_alarm"},
        blocking=True,
    )
    assert len(_calls(aioclient_mock, "DELETE", "zones/0/door/alarm")) == 1


async def test_rejected_write_raises(
    hass: HomeAssistant,
    appliance: FakeAppliance,
    serve,
    setup_integration: MockConfigEntry,
) -> None:
    """An error status from the appliance surfaces as a HomeAssistantError."""
    appliance.write_status = 409
    serve()

    with pytest.raises(HomeAssistantError, match="HTTP 409"):
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: f"number.{PREFIX}_target_temperature", "value": 6},
            blocking=True,
        )
