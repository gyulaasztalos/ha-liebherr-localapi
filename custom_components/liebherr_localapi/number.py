"""Numbers for the Liebherr LocalAPI integration."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import LiebherrEntity, dig, supported

TEMPERATURE_PATH = "zones/{zone}/temperature"
HUMIDITY_PATH = "zones/{zone}/humidity"
REFRESH_TIME_PATH = "zones/{zone}/temperature/alarm/refresh-time"
DOOR_ALARM_DELAY_PATH = "zones/{zone}/door/alarm/delay"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create numbers for zone settings the firmware can change."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    for zone in coordinator.zone_info:

        def has(path: str, zone: int = zone) -> bool:
            return coordinator.has_route("PUT", path.format(zone=zone))

        if has(TEMPERATURE_PATH) and supported(coordinator, zone, None, "temperature"):
            entities.append(TargetTemperature(coordinator, zone))
        if has(HUMIDITY_PATH) and supported(coordinator, zone, "humidity", None):
            entities.append(TargetHumidity(coordinator, zone))
        if has(REFRESH_TIME_PATH) and supported(
            coordinator, zone, "upperTemperatureAlarm", None
        ):
            entities.append(AlarmRefreshTime(coordinator, zone))
        if has(DOOR_ALARM_DELAY_PATH) and supported(
            coordinator, zone, "doorAlarm", None
        ):
            entities.append(DoorAlarmDelay(coordinator, zone))
    async_add_entities(entities)


class TargetTemperature(LiebherrEntity, NumberEntity):
    """Zone setpoint; range and step come from the zone description."""

    _attr_translation_key = "target_temperature"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: LiebherrCoordinator, zone: int) -> None:
        """Initialize the setpoint."""
        super().__init__(coordinator, "target_temperature", zone)

    @property
    def _fahrenheit(self) -> bool:
        return dig(self.state_data, "temperature", "unit") == 1

    @property
    def native_unit_of_measurement(self) -> str:
        """Unit follows the appliance setting."""
        return (
            UnitOfTemperature.FAHRENHEIT
            if self._fahrenheit
            else UnitOfTemperature.CELSIUS
        )

    def _range(self, bound: str) -> float | None:
        unit = "fahrenheit" if self._fahrenheit else "celsius"
        return dig(self.coordinator.zone_info[self.zone], "temperature", unit, bound)

    @property
    def native_min_value(self) -> float:
        """Lowest settable temperature."""
        value = self._range("min")
        return -30 if value is None else value

    @property
    def native_max_value(self) -> float:
        """Highest settable temperature."""
        value = self._range("max")
        return 30 if value is None else value

    @property
    def native_step(self) -> float:
        """Resolution reported by the zone (1.0 = whole degrees)."""
        return dig(self.state_data, "temperature", "resolution") or 1.0

    @property
    def native_value(self) -> float | None:
        """Current setpoint."""
        return dig(self.state_data, "temperature", "setpoint")

    async def async_set_native_value(self, value: float) -> None:
        """Write the setpoint."""
        if self.native_step >= 1:
            value = int(round(value))
        await self.coordinator.async_write(
            "PUT", self.route(TEMPERATURE_PATH), {"value": value}
        )


class TargetHumidity(LiebherrEntity, NumberEntity):
    """Zone humidity setpoint."""

    _attr_translation_key = "target_humidity"
    _attr_device_class = NumberDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_step = 1

    def __init__(self, coordinator: LiebherrCoordinator, zone: int) -> None:
        """Initialize the humidity setpoint."""
        super().__init__(coordinator, "target_humidity", zone)
        humidity = coordinator.zone_info[zone].get("humidity") or {}
        self._attr_native_min_value = humidity.get("min", 0)
        self._attr_native_max_value = humidity.get("max", 100)

    @property
    def native_value(self) -> float | None:
        """Current humidity setpoint."""
        return dig(self.state_data, "humidity", "setpoint")

    async def async_set_native_value(self, value: float) -> None:
        """Write the humidity setpoint."""
        await self.coordinator.async_write(
            "PUT", self.route(HUMIDITY_PATH), {"value": int(value)}
        )


class AlarmRefreshTime(LiebherrEntity, NumberEntity):
    """Minutes until a confirmed temperature alarm re-triggers (0 = off)."""

    _attr_translation_key = "alarm_refresh_time"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: LiebherrCoordinator, zone: int) -> None:
        """Initialize the refresh time."""
        super().__init__(coordinator, "alarm_refresh_time", zone)

    @property
    def native_value(self) -> float | None:
        """Current refresh time."""
        return dig(self.state_data, "temperatureAlarm", "refreshTime")

    async def async_set_native_value(self, value: float) -> None:
        """Write the refresh time."""
        await self.coordinator.async_write(
            "PUT", self.route(REFRESH_TIME_PATH), {"value": int(value)}
        )


class DoorAlarmDelay(LiebherrEntity, RestoreNumber):
    """Seconds the door may stay open before the alarm (0 = disabled).

    The LocalAPI does not report this value, so the last value written from
    Home Assistant is shown; it is unknown until set once.
    """

    _attr_translation_key = "door_alarm_delay"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_assumed_state = True

    def __init__(self, coordinator: LiebherrCoordinator, zone: int) -> None:
        """Initialize the door alarm delay."""
        super().__init__(coordinator, "door_alarm_delay", zone)
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Restore the last written value."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) is not None:
            self._attr_native_value = last.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Write the delay."""
        await self.coordinator.async_write(
            "PUT", self.route(DOOR_ALARM_DELAY_PATH), {"value": int(value)}
        )
        self._attr_native_value = int(value)
        self.async_write_ha_state()
