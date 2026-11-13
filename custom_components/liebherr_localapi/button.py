"""Alarm confirmation buttons for the Liebherr LocalAPI integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry
from .entity import LiebherrEntity, dig, supported

_LOGGER = logging.getLogger(__name__)

# Alarm states: 0 inactive, 1 active, 2 active and confirmed
ALARM_ACTIVE = 1


@dataclass(frozen=True, kw_only=True)
class LiebherrButtonDescription(ButtonEntityDescription):
    """Confirms one zone alarm with DELETE."""

    cap: str
    path: str
    state_path: tuple[str, ...]


BUTTONS: tuple[LiebherrButtonDescription, ...] = (
    LiebherrButtonDescription(
        key="confirm_door_alarm",
        translation_key="confirm_door_alarm",
        cap="doorAlarm",
        path="zones/{zone}/door/alarm",
        state_path=("doorAlarm", "state"),
    ),
    LiebherrButtonDescription(
        key="confirm_upper_temperature_alarm",
        translation_key="confirm_upper_temperature_alarm",
        cap="upperTemperatureAlarm",
        path="zones/{zone}/temperature/alarm/upper",
        state_path=("temperatureAlarm", "upper", "state"),
    ),
    LiebherrButtonDescription(
        key="confirm_lower_temperature_alarm",
        translation_key="confirm_lower_temperature_alarm",
        cap="lowerTemperatureAlarm",
        path="zones/{zone}/temperature/alarm/lower",
        state_path=("temperatureAlarm", "lower", "state"),
    ),
    LiebherrButtonDescription(
        key="confirm_upper_power_failure_alarm",
        translation_key="confirm_upper_power_failure_alarm",
        cap="upperPowerFailureAlarm",
        path="zones/{zone}/alarm/power-failure-alarm/upper",
        state_path=("powerFailureAlarm", "upper", "state"),
    ),
    LiebherrButtonDescription(
        key="confirm_lower_power_failure_alarm",
        translation_key="confirm_lower_power_failure_alarm",
        cap="lowerPowerFailureAlarm",
        path="zones/{zone}/alarm/power-failure-alarm/lower",
        state_path=("powerFailureAlarm", "lower", "state"),
    ),
    LiebherrButtonDescription(
        key="confirm_emergency_alarm",
        translation_key="confirm_emergency_alarm",
        cap="emergencyAlarm",
        path="zones/{zone}/alarm/emergency-alarm",
        state_path=("emergencyAlarm", "state"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create buttons for alarms the firmware can confirm."""
    coordinator = entry.runtime_data
    async_add_entities(
        LiebherrButton(coordinator, description, zone)
        for description in BUTTONS
        for zone in coordinator.zone_info
        if supported(coordinator, zone, description.cap, None)
        and coordinator.has_route("DELETE", description.path.format(zone=zone))
    )


class LiebherrButton(LiebherrEntity, ButtonEntity):
    """Confirm (silence) an active alarm."""

    entity_description: LiebherrButtonDescription

    def __init__(self, coordinator, description, zone) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key, zone)
        self.entity_description = description

    async def async_press(self) -> None:
        """Confirm the alarm, if there is an unconfirmed one.

        With no active alarm, or one already confirmed, the press succeeds without
        contacting the appliance: confirming an alarm that has already cleared
        makes it report the alarm as active-and-confirmed until its next state
        update, which looks like a new alarm.
        """
        if dig(self.state_data, *self.entity_description.state_path) != ALARM_ACTIVE:
            _LOGGER.debug(
                "%s: no unconfirmed alarm, nothing to confirm", self.entity_id
            )
            return
        await self.coordinator.async_write(
            "DELETE", self.route(self.entity_description.path)
        )
