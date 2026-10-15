"""Config flow for the Liebherr LocalAPI integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LiebherrClient, LiebherrConnectionError, LiebherrError
from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
)


class LiebherrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an appliance by host."""

    VERSION = 1

    async def _async_probe(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Read /appliance/info; return it or form errors."""
        client = LiebherrClient(
            async_get_clientsession(self.hass),
            user_input[CONF_HOST],
            user_input[CONF_PORT],
        )
        try:
            info = await client.appliance_info()
        except LiebherrConnectionError:
            return None, {"base": "cannot_connect"}
        except LiebherrError:
            _LOGGER.exception("Unexpected LocalAPI response")
            return None, {"base": "invalid_response"}
        if not info.get("serialNo"):
            return None, {"base": "invalid_response"}
        return info, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the appliance address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_probe(user_input)
            if info:
                await self.async_set_unique_id(info["serialNo"])
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=f"Liebherr {info.get('name', info['serialNo'])}",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the appliance address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_probe(user_input)
            if info:
                await self.async_set_unique_id(info["serialNo"])
                self._abort_if_unique_id_mismatch(reason="wrong_appliance")
                return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )
