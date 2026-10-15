"""Switches for the Liebherr LocalAPI integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry
from .entity import LiebherrEntity, supported


@dataclass(frozen=True, kw_only=True)
class LiebherrSwitchDescription(SwitchEntityDescription):
    """On/off setting written as {"state": 0|1}."""

    zone: bool
    cap: str
    state_key: str
    path: str


SWITCHES: tuple[LiebherrSwitchDescription, ...] = (
    LiebherrSwitchDescription(
        key="acoustic_alarm",
        translation_key="acoustic_alarm",
        zone=False,
        cap="acousticAlarm",
        state_key="acousticAlarm",
        path="appliance/setting/acoustic-alarm",
        entity_category=EntityCategory.CONFIG,
    ),
    LiebherrSwitchDescription(
        key="child_lock",
        translation_key="child_lock",
        zone=False,
        cap="childLock",
        state_key="childLock",
        path="appliance/setting/child-lock",
        entity_category=EntityCategory.CONFIG,
    ),
    LiebherrSwitchDescription(
        key="supercool",
        translation_key="supercool",
        zone=True,
        cap="superCool",
        state_key="superCool",
        path="zones/{zone}/supercool",
    ),
    LiebherrSwitchDescription(
        key="superfrost",
        translation_key="superfrost",
        zone=True,
        cap="superFrost",
        state_key="superFrost",
        path="zones/{zone}/superfrost",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create switches for features the firmware can change."""
    coordinator = entry.runtime_data
    async_add_entities(
        LiebherrSwitch(coordinator, description, scope)
        for description in SWITCHES
        for scope in (list(coordinator.zone_info) if description.zone else [None])
        if supported(coordinator, scope, description.cap, description.state_key)
        and coordinator.has_route("PUT", description.path.format(zone=scope))
    )


class LiebherrSwitch(LiebherrEntity, SwitchEntity):
    """Appliance or zone on/off setting."""

    entity_description: LiebherrSwitchDescription

    def __init__(self, coordinator, description, zone) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, description.key, zone)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Current state."""
        value = self.state_data.get(self.entity_description.state_key)
        return None if value is None else value == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self.coordinator.async_write(
            "PUT", self.route(self.entity_description.path), {"state": 1}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self.coordinator.async_write(
            "PUT", self.route(self.entity_description.path), {"state": 0}
        )
