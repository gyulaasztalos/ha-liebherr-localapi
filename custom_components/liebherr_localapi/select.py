"""Selects for the Liebherr LocalAPI integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry
from .entity import LiebherrEntity, dig, supported


@dataclass(frozen=True, kw_only=True)
class LiebherrSelectDescription(SelectEntityDescription):
    """Enum setting written as {"state": index}; options are in index order."""

    zone: bool
    cap: str
    state_path: tuple[str, ...]
    path: str


SELECTS: tuple[LiebherrSelectDescription, ...] = (
    LiebherrSelectDescription(
        key="eco_mode",
        translation_key="eco_mode",
        zone=False,
        cap="ecoMode",
        state_path=("ecoMode",),
        path="appliance/setting/eco-mode",
        options=["off", "eco", "eco_plus"],
    ),
    LiebherrSelectDescription(
        key="humidifier_mode",
        translation_key="humidifier_mode",
        zone=True,
        cap="humidifier",
        state_path=("humidifier", "mode"),
        path="zones/{zone}/humidifier/mode",
        options=["off", "low", "mid", "high"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create selects for features the firmware can change."""
    coordinator = entry.runtime_data
    async_add_entities(
        LiebherrSelect(coordinator, description, scope)
        for description in SELECTS
        for scope in (list(coordinator.zone_info) if description.zone else [None])
        if supported(coordinator, scope, description.cap, description.state_path[0])
        and coordinator.has_route("PUT", description.path.format(zone=scope))
    )


class LiebherrSelect(LiebherrEntity, SelectEntity):
    """Appliance or zone mode."""

    entity_description: LiebherrSelectDescription

    def __init__(self, coordinator, description, zone) -> None:
        """Initialize the select."""
        super().__init__(coordinator, description.key, zone)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Current mode."""
        index = dig(self.state_data, *self.entity_description.state_path)
        options = self.entity_description.options
        if not isinstance(index, int) or not 0 <= index < len(options):
            return None
        return options[index]

    async def async_select_option(self, option: str) -> None:
        """Write the mode."""
        await self.coordinator.async_write(
            "PUT",
            self.route(self.entity_description.path),
            {"state": self.entity_description.options.index(option)},
        )
