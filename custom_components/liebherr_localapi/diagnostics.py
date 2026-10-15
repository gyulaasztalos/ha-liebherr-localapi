"""Diagnostics for the Liebherr LocalAPI integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import LiebherrConfigEntry

TO_REDACT = {"serialNo", "ident"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LiebherrConfigEntry
) -> dict[str, Any]:
    """Raw LocalAPI documents plus the routes this firmware serves."""
    coordinator = entry.runtime_data
    return {
        "info": async_redact_data(coordinator.info, TO_REDACT),
        "zone_info": coordinator.zone_info,
        "routes": sorted(f"{method} /{path}" for method, path in coordinator.routes),
        "state": asdict(coordinator.data) if coordinator.data else None,
    }
