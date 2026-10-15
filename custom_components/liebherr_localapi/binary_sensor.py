"""Binary sensors for the Liebherr LocalAPI integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry
from .entity import LiebherrEntity, dig, supported

# Alarm states: 0 inactive, 1 active, 2 active and confirmed
ALARM_CONFIRMED = 2


@dataclass(frozen=True, kw_only=True)
class LiebherrBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor bound to a state field."""

    zone: bool
    cap: str | None = None
    state_key: str | None = None
    value_fn: Callable[[dict[str, Any]], Any]
    # Alarms report whether they have been confirmed on the appliance
    alarm_path: tuple[str, ...] | None = None
    # Only created when the firmware lacks the matching control route
    fallback_for: str | None = None


def _alarm(key: str, *path: str, cap: str, zone: bool = True):
    return LiebherrBinarySensorDescription(
        key=key,
        translation_key=key,
        zone=zone,
        cap=cap,
        device_class=BinarySensorDeviceClass.PROBLEM,
        alarm_path=path,
        value_fn=lambda s: (dig(s, *path) or 0) != 0,
    )


BINARY_SENSORS: tuple[LiebherrBinarySensorDescription, ...] = (
    LiebherrBinarySensorDescription(
        key="door",
        zone=True,
        cap="door",
        state_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda s: (s.get("door") or 0) != 0,
    ),
    LiebherrBinarySensorDescription(
        key="cooling",
        translation_key="cooling",
        zone=True,
        state_key="state",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda s: s.get("state") == 1,
    ),
    LiebherrBinarySensorDescription(
        key="manual_defrost",
        translation_key="manual_defrost",
        zone=True,
        cap="manualDefrost",
        state_key="manualDefrost",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda s: s.get("manualDefrost") == 1,
    ),
    _alarm("door_alarm", "doorAlarm", "state", cap="doorAlarm"),
    _alarm(
        "upper_temperature_alarm",
        "temperatureAlarm",
        "upper",
        "state",
        cap="upperTemperatureAlarm",
    ),
    _alarm(
        "lower_temperature_alarm",
        "temperatureAlarm",
        "lower",
        "state",
        cap="lowerTemperatureAlarm",
    ),
    _alarm(
        "upper_power_failure_alarm",
        "powerFailureAlarm",
        "upper",
        "state",
        cap="upperPowerFailureAlarm",
    ),
    _alarm(
        "lower_power_failure_alarm",
        "powerFailureAlarm",
        "lower",
        "state",
        cap="lowerPowerFailureAlarm",
    ),
    _alarm("emergency_alarm", "emergencyAlarm", "state", cap="emergencyAlarm"),
    _alarm("failure_alarm", "failureAlarm", "state", cap="failureAlarm", zone=False),
    LiebherrBinarySensorDescription(
        key="acoustic_alarm_state",
        translation_key="acoustic_alarm_state",
        zone=False,
        cap="acousticAlarm",
        state_key="acousticAlarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        fallback_for="appliance/setting/acoustic-alarm",
        value_fn=lambda s: s.get("acousticAlarm") == 1,
    ),
    LiebherrBinarySensorDescription(
        key="child_lock_state",
        translation_key="child_lock_state",
        zone=False,
        cap="childLock",
        state_key="childLock",
        entity_category=EntityCategory.DIAGNOSTIC,
        fallback_for="appliance/setting/child-lock",
        value_fn=lambda s: s.get("childLock") == 1,
    ),
    LiebherrBinarySensorDescription(
        key="supercool_state",
        translation_key="supercool_state",
        zone=True,
        cap="superCool",
        state_key="superCool",
        device_class=BinarySensorDeviceClass.RUNNING,
        fallback_for="zones/{zone}/supercool",
        value_fn=lambda s: s.get("superCool") == 1,
    ),
    LiebherrBinarySensorDescription(
        key="superfrost_state",
        translation_key="superfrost_state",
        zone=True,
        cap="superFrost",
        state_key="superFrost",
        device_class=BinarySensorDeviceClass.RUNNING,
        fallback_for="zones/{zone}/superfrost",
        value_fn=lambda s: s.get("superFrost") == 1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create binary sensors for supported features."""
    coordinator = entry.runtime_data
    entities: list[LiebherrBinarySensor] = []
    for description in BINARY_SENSORS:
        scopes = list(coordinator.zone_info) if description.zone else [None]
        for scope in scopes:
            if not supported(
                coordinator, scope, description.cap, description.state_key
            ):
                continue
            if description.fallback_for and coordinator.has_route(
                "PUT", description.fallback_for.format(zone=scope)
            ):
                continue
            entities.append(LiebherrBinarySensor(coordinator, description, scope))
    async_add_entities(entities)


class LiebherrBinarySensor(LiebherrEntity, BinarySensorEntity):
    """On/off value from appliance or zone state."""

    entity_description: LiebherrBinarySensorDescription

    def __init__(self, coordinator, description, zone) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key, zone)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Current state."""
        return bool(self.entity_description.value_fn(self.state_data))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Whether an active alarm was confirmed on the appliance."""
        path = self.entity_description.alarm_path
        if path is None:
            return None
        return {"confirmed": dig(self.state_data, *path) == ALARM_CONFIRMED}
