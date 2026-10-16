"""Shared fixtures: a fake appliance served through Home Assistant's aiohttp mocker.

The JSON fixtures were captured from a BRPSvh 6501 (SmartModule firmware
3.2.4.0) with its serial numbers replaced. `REAL_ROUTES` is the set of control
routes that firmware answers OPTIONS for; every other spec route returns 404.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.liebherr_localapi.const import (
    APPLIANCE_ROUTES,
    DOMAIN,
    ZONE_ROUTES,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

HOST = "192.0.2.21"
PORT = 8080
BASE_URL = f"http://{HOST}:{PORT}"
SERIAL = "00.000.000.0"
FIXTURES = Path(__file__).parent / "fixtures"

REAL_ROUTES = frozenset(
    {
        ("PUT", "appliance/setting/acoustic-alarm"),
        ("PUT", "appliance/setting/eco-mode"),
        ("PUT", "zones/0/temperature"),
        ("PUT", "zones/0/temperature/alarm/refresh-time"),
        ("DELETE", "zones/0/temperature/alarm/upper"),
        ("DELETE", "zones/0/temperature/alarm/lower"),
        ("DELETE", "zones/0/alarm/power-failure-alarm/upper"),
        ("DELETE", "zones/0/alarm/power-failure-alarm/lower"),
        ("DELETE", "zones/0/alarm/emergency-alarm"),
        ("DELETE", "zones/0/door/alarm"),
        ("PUT", "zones/0/door/alarm/delay"),
    }
)


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@dataclass
class FakeAppliance:
    """What the mocked appliance serves; tests mutate it, then call `serve()`."""

    info: dict[str, Any]
    state: dict[str, Any]
    zone_info: dict[str, Any]
    zone_state: dict[str, Any]
    routes: set[tuple[str, str]] = field(default_factory=lambda: set(REAL_ROUTES))
    write_status: int = 200
    state_status: int = 200


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration from custom_components."""


@pytest.fixture
def appliance() -> FakeAppliance:
    """A fresh copy of the real BRPSvh 6501 documents."""
    return FakeAppliance(
        info=copy.deepcopy(load_fixture("appliance_info.json")),
        state=copy.deepcopy(load_fixture("appliance_state.json")),
        zone_info=copy.deepcopy(load_fixture("zone_info.json")),
        zone_state=copy.deepcopy(load_fixture("zone_state.json")),
    )


@pytest.fixture
def serve(aioclient_mock: AiohttpClientMocker, appliance: FakeAppliance):
    """Return a callable that (re)registers every endpoint of `appliance`."""

    def _serve() -> None:
        aioclient_mock.clear_requests()
        state_kwargs: dict[str, Any] = {"status": appliance.state_status}
        aioclient_mock.get(f"{BASE_URL}/appliance/info", json=appliance.info)
        aioclient_mock.get(f"{BASE_URL}/zones/0/info", json=appliance.zone_info)
        aioclient_mock.get(
            f"{BASE_URL}/appliance/state", json=appliance.state, **state_kwargs
        )
        aioclient_mock.get(
            f"{BASE_URL}/zones/0/state", json=appliance.zone_state, **state_kwargs
        )

        candidates = {path for _, path in APPLIANCE_ROUTES} | {
            path.format(zone=0) for _, path in ZONE_ROUTES
        }
        for path in sorted(candidates):
            methods = sorted(m for m, p in appliance.routes if p == path)
            if methods:
                aioclient_mock.options(
                    f"{BASE_URL}/{path}",
                    headers={"Allow": ",".join([*methods, "OPTIONS"])},
                )
                for method in methods:
                    aioclient_mock.request(
                        method, f"{BASE_URL}/{path}", status=appliance.write_status
                    )
            else:
                aioclient_mock.options(f"{BASE_URL}/{path}", status=404)

    _serve()
    return _serve


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Config entry for the fake appliance."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Liebherr BRPSvh 6501",
        unique_id=SERIAL,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, serve
) -> MockConfigEntry:
    """Add the config entry and set it up against the fake appliance."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
