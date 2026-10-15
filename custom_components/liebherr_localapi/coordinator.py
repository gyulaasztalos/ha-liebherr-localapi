"""Polling coordinator for the Liebherr LocalAPI integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LiebherrClient, LiebherrError
from .const import APPLIANCE_ROUTES, DOMAIN, SCAN_INTERVAL, ZONE_ROUTES

_LOGGER = logging.getLogger(__name__)

type LiebherrConfigEntry = ConfigEntry[LiebherrCoordinator]


@dataclass
class LiebherrData:
    """One poll of the appliance."""

    appliance: dict[str, Any]
    zones: dict[int, dict[str, Any]]


class LiebherrCoordinator(DataUpdateCoordinator[LiebherrData]):
    """Poll appliance and zone state; hold the static appliance description."""

    config_entry: LiebherrConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LiebherrConfigEntry,
        client: LiebherrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.info: dict[str, Any] = {}
        self.zone_info: dict[int, dict[str, Any]] = {}
        self.routes: set[tuple[str, str]] = set()

    async def _async_setup(self) -> None:
        """Read identity, zone ranges and the routes this firmware serves."""
        try:
            self.info = await self.client.appliance_info()
            zones = self.info.get("zones", 1)
            zone_count = len(zones) if isinstance(zones, list) else int(zones)
            for zone in range(zone_count):
                self.zone_info[zone] = await self.client.zone_info(zone)

            candidates = list(APPLIANCE_ROUTES) + [
                (method, path.format(zone=zone))
                for zone in self.zone_info
                for method, path in ZONE_ROUTES
            ]
            for method, path in candidates:
                if method in await self.client.allowed_methods(path):
                    self.routes.add((method, path))
        except LiebherrError as err:
            raise UpdateFailed(str(err)) from err
        _LOGGER.debug("Routes served by %s: %s", self.info.get("name"), self.routes)

    async def _async_update_data(self) -> LiebherrData:
        """Fetch appliance and zone state."""
        try:
            appliance = await self.client.appliance_state()
            zones = {
                zone: await self.client.zone_state(zone) for zone in self.zone_info
            }
        except LiebherrError as err:
            raise UpdateFailed(str(err)) from err
        return LiebherrData(appliance=appliance, zones=zones)

    def has_route(self, method: str, path: str) -> bool:
        """Return whether the firmware serves a route."""
        return (method, path) in self.routes

    async def async_write(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> None:
        """Send a control request, then refresh state."""
        try:
            if method == "DELETE":
                await self.client.delete(path)
            else:
                await self.client.put(path, body or {})
        except LiebherrError as err:
            raise HomeAssistantError(str(err)) from err
        await self.async_request_refresh()
