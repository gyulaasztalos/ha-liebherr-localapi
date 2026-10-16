"""Diagnostics tests."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.liebherr_localapi.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


async def test_diagnostics_redacts_identity(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Diagnostics keep the raw documents but hide serial and module id."""
    diagnostics = await async_get_config_entry_diagnostics(hass, setup_integration)

    assert diagnostics["info"]["serialNo"] == "**REDACTED**"
    assert diagnostics["info"]["cm"]["ident"] == "**REDACTED**"
    assert diagnostics["info"]["name"] == "BRPSvh 6501"
    assert "PUT /zones/0/temperature" in diagnostics["routes"]
    assert "PUT /zones/0/supercool" not in diagnostics["routes"]
    assert diagnostics["state"]["zones"][0]["temperature"]["displayed"] == 4.9375
