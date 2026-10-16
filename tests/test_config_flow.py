"""Config flow tests."""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.liebherr_localapi.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import BASE_URL, HOST, PORT, SERIAL, FakeAppliance

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT}
SETUP_ENTRY = "custom_components.liebherr_localapi.async_setup_entry"


async def test_user_flow_creates_entry(hass: HomeAssistant, serve) -> None:
    """A reachable appliance becomes an entry keyed by its serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Liebherr BRPSvh 6501"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL


async def test_user_flow_cannot_connect_then_recovers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, serve
) -> None:
    """Connection errors show cannot_connect and the form can be retried."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE_URL}/appliance/info", exc=aiohttp.ClientError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    serve()
    with patch(SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A host that answers without LocalAPI data shows invalid_response."""
    aioclient_mock.get(f"{BASE_URL}/appliance/info", status=404)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_response"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, serve
) -> None:
    """The same appliance cannot be added twice."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_updates_host(
    hass: HomeAssistant, config_entry: MockConfigEntry, serve
) -> None:
    """Reconfigure keeps the entry and stores the new address."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_HOST: HOST, CONF_PORT: PORT}


async def test_reconfigure_rejects_other_appliance(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    appliance: FakeAppliance,
    serve,
) -> None:
    """An address that answers with another serial number is refused."""
    config_entry.add_to_hass(hass)
    appliance.info["serialNo"] = "11.111.111.1"
    serve()

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_appliance"
