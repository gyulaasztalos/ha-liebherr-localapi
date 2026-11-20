"""LocalAPI client tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.liebherr_localapi.api import (
    LiebherrClient,
    LiebherrConnectionError,
    LiebherrError,
    LiebherrResponseError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import BASE_URL, HOST, PORT


@pytest.fixture
async def client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> LiebherrClient:
    """Client for the fake appliance, on the mocked session."""
    return LiebherrClient(async_get_clientsession(hass), HOST, PORT)


async def test_timeout_names_the_error(
    client: LiebherrClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """A timeout has no message of its own, so the error names its type."""
    aioclient_mock.get(f"{BASE_URL}/appliance/state", exc=TimeoutError())

    with pytest.raises(LiebherrConnectionError, match=r"state: TimeoutError$"):
        await client.appliance_state()


@pytest.mark.parametrize("body", [[], "ok", 1])
async def test_get_rejects_non_object(
    client: LiebherrClient, aioclient_mock: AiohttpClientMocker, body
) -> None:
    """Valid JSON that is not an object is a LocalAPI error, not a crash later."""
    aioclient_mock.get(f"{BASE_URL}/appliance/info", json=body)

    with pytest.raises(LiebherrError, match="expected a JSON object"):
        await client.appliance_info()


async def test_allowed_methods_unregistered_route(
    client: LiebherrClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """404 means the firmware does not register the route."""
    aioclient_mock.options(f"{BASE_URL}/zones/0/supercool", status=404)

    assert await client.allowed_methods("zones/0/supercool") == frozenset()


async def test_allowed_methods_raises_on_appliance_error(
    client: LiebherrClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Any other error is not taken as a missing route."""
    aioclient_mock.options(f"{BASE_URL}/zones/0/temperature", status=504)

    with pytest.raises(LiebherrResponseError) as err:
        await client.allowed_methods("zones/0/temperature")
    assert err.value.status == 504
