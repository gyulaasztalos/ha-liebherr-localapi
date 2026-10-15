"""Base entity for the Liebherr LocalAPI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONE_POSITIONS
from .coordinator import LiebherrCoordinator


def dig(data: dict[str, Any] | None, *keys: str) -> Any:
    """Walk nested dicts; None when any key is missing."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def appliance_device(coordinator: LiebherrCoordinator) -> DeviceInfo:
    """Device for the appliance itself."""
    info = coordinator.info
    return DeviceInfo(
        identifiers={(DOMAIN, info["serialNo"])},
        manufacturer="Liebherr",
        model=info.get("name"),
        model_id=info.get("articleNo"),
        name=f"Liebherr {info.get('name', '')}".strip(),
        serial_number=info["serialNo"],
        sw_version=dig(info, "cm", "app"),
    )


def zone_device(coordinator: LiebherrCoordinator, zone: int) -> DeviceInfo:
    """Device for a zone; single-zone appliances use the appliance device."""
    if len(coordinator.zone_info) == 1:
        return appliance_device(coordinator)
    info = coordinator.info
    position = ZONE_POSITIONS.get(
        coordinator.zone_info[zone].get("position"), str(zone)
    )
    return DeviceInfo(
        identifiers={(DOMAIN, f"{info['serialNo']}_zone{zone}")},
        manufacturer="Liebherr",
        model=info.get("name"),
        name=f"Liebherr {info.get('name', '')} {position} zone",
        via_device=(DOMAIN, info["serialNo"]),
    )


class LiebherrEntity(CoordinatorEntity[LiebherrCoordinator]):
    """Entity bound to the appliance or one of its zones."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LiebherrCoordinator, key: str, zone: int | None = None
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.zone = zone
        serial = coordinator.info["serialNo"]
        if zone is None:
            self._attr_unique_id = f"{serial}_{key}"
            self._attr_device_info = appliance_device(coordinator)
        else:
            self._attr_unique_id = f"{serial}_zone{zone}_{key}"
            self._attr_device_info = zone_device(coordinator, zone)

    @property
    def state_data(self) -> dict[str, Any]:
        """Appliance or zone state, whichever this entity belongs to."""
        if self.zone is None:
            return self.coordinator.data.appliance
        return self.coordinator.data.zones[self.zone]

    def route(self, path: str) -> str:
        """Fill the zone into a route template."""
        return path.format(zone=self.zone)


def supported(
    coordinator: LiebherrCoordinator,
    zone: int | None,
    cap: str | None,
    state_key: str | None,
) -> bool:
    """Whether a feature exists: capability flag set, or field present in state.

    Both are checked because the capability flags under-report on some firmware.
    """
    caps = (
        coordinator.info.get("caps", {})
        if zone is None
        else coordinator.zone_info[zone].get("caps", {})
    )
    if cap and caps.get(cap) == 1:
        return True
    data = coordinator.data.appliance if zone is None else coordinator.data.zones[zone]
    return bool(state_key) and state_key in data
