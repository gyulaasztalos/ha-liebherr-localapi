"""Sensors for the Liebherr LocalAPI integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry
from .entity import LiebherrEntity, dig, supported


def _threshold(state: dict[str, Any], side: str) -> float | None:
    """Alarm level = setpoint + upper limit, or setpoint - lower limit."""
    setpoint = dig(state, "temperature", "setpoint")
    limit = dig(state, "temperatureAlarm", side, "limit")
    if setpoint is None or limit is None:
        return None
    return setpoint + limit if side == "upper" else setpoint - limit


@dataclass(frozen=True, kw_only=True)
class LiebherrSensorDescription(SensorEntityDescription):
    """Sensor bound to a state field."""

    zone: bool
    cap: str | None = None
    state_key: str | None = None
    value_fn: Callable[[dict[str, Any]], Any]
    temperature: bool = False


SENSORS: tuple[LiebherrSensorDescription, ...] = (
    LiebherrSensorDescription(
        key="temperature",
        zone=True,
        state_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        temperature=True,
        # The appliance can hold one value for hours; publish every poll so
        # history and exports (e.g. InfluxDB) show no gaps in the temperature log.
        force_update=True,
        value_fn=lambda s: dig(s, "temperature", "displayed"),
    ),
    LiebherrSensorDescription(
        key="humidity",
        zone=True,
        cap="humiditySensor",
        state_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: dig(s, "humidity", "displayed"),
    ),
    LiebherrSensorDescription(
        key="upper_alarm_threshold",
        translation_key="upper_alarm_threshold",
        zone=True,
        cap="upperTemperatureAlarm",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        temperature=True,
        value_fn=lambda s: _threshold(s, "upper"),
    ),
    LiebherrSensorDescription(
        key="lower_alarm_threshold",
        translation_key="lower_alarm_threshold",
        zone=True,
        cap="lowerTemperatureAlarm",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        temperature=True,
        value_fn=lambda s: _threshold(s, "lower"),
    ),
    LiebherrSensorDescription(
        key="upper_alarm_delay",
        translation_key="upper_alarm_delay",
        zone=True,
        cap="upperTemperatureAlarm",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: dig(s, "temperatureAlarm", "upper", "delay"),
    ),
    LiebherrSensorDescription(
        key="lower_alarm_delay",
        translation_key="lower_alarm_delay",
        zone=True,
        cap="lowerTemperatureAlarm",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: dig(s, "temperatureAlarm", "lower", "delay"),
    ),
    LiebherrSensorDescription(
        key="failure_codes",
        translation_key="failure_codes",
        zone=False,
        cap="failureAlarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: (
            ", ".join(map(str, dig(s, "failureAlarm", "codes") or [])) or "none"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors for supported features."""
    coordinator = entry.runtime_data
    entities: list[LiebherrSensor] = []
    for description in SENSORS:
        scopes = list(coordinator.zone_info) if description.zone else [None]
        entities.extend(
            LiebherrSensor(coordinator, description, scope)
            for scope in scopes
            if supported(coordinator, scope, description.cap, description.state_key)
        )
    async_add_entities(entities)


class LiebherrSensor(LiebherrEntity, SensorEntity):
    """Read-only value from appliance or zone state."""

    entity_description: LiebherrSensorDescription

    def __init__(self, coordinator, description, zone) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key, zone)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Current value."""
        return self.entity_description.value_fn(self.state_data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Temperature unit follows the appliance setting."""
        if self.entity_description.temperature:
            unit = dig(self.state_data, "temperature", "unit")
            return (
                UnitOfTemperature.FAHRENHEIT if unit == 1 else UnitOfTemperature.CELSIUS
            )
        return self.entity_description.native_unit_of_measurement
