"""Async client for the Liebherr SmartModule LocalAPI."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

# Response codes documented in the LocalAPI spec
STATUS_MEANING = {
    400: "bad request",
    403: "PIN not accepted",
    404: "route or zone does not exist",
    406: "appliance does not have this feature",
    409: "not possible in the zone's current operating state",
    420: "value out of the accepted range",
    500: "failed to write to the appliance bus",
    504: "appliance bus not ready or data not present yet",
}


class LiebherrError(Exception):
    """Base error for the LocalAPI client."""


class LiebherrConnectionError(LiebherrError):
    """The appliance could not be reached."""


class LiebherrResponseError(LiebherrError):
    """The appliance answered with an error status."""

    def __init__(self, method: str, path: str, status: int) -> None:
        """Initialize the error."""
        self.status = status
        meaning = STATUS_MEANING.get(status, "unexpected response")
        super().__init__(f"{method} /{path}: HTTP {status} ({meaning})")


class LiebherrClient:
    """Talk to one appliance on its LocalAPI port."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        timeout: float = 10,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        # The SmartModule's HTTP server copes badly with concurrent requests
        self._lock = asyncio.Lock()

    async def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> aiohttp.ClientResponse:
        """Send one request and return the read response."""
        async with self._lock:
            try:
                async with self._session.request(
                    method,
                    f"{self._base_url}/{path}",
                    json=body,
                    timeout=self._timeout,
                ) as response:
                    await response.read()
                    return response
            except (aiohttp.ClientError, TimeoutError) as err:
                raise LiebherrConnectionError(
                    f"{method} /{path}: {str(err) or type(err).__name__}"
                ) from err

    async def get(self, path: str) -> dict[str, Any]:
        """GET a JSON document."""
        response = await self._request("GET", path)
        if response.status != 200:
            raise LiebherrResponseError("GET", path, response.status)
        try:
            data = await response.json(content_type=None)
        except ValueError as err:
            raise LiebherrError(f"GET /{path}: invalid JSON") from err
        if not isinstance(data, dict):
            raise LiebherrError(f"GET /{path}: expected a JSON object")
        return data

    async def put(self, path: str, body: dict[str, Any]) -> None:
        """PUT a JSON body."""
        response = await self._request("PUT", path, body)
        if response.status not in (200, 202):
            raise LiebherrResponseError("PUT", path, response.status)

    async def delete(self, path: str) -> None:
        """DELETE a resource (confirms an alarm)."""
        response = await self._request("DELETE", path)
        if response.status != 200:
            raise LiebherrResponseError("DELETE", path, response.status)

    async def allowed_methods(self, path: str) -> frozenset[str]:
        """Return the methods the firmware registers for a route.

        404 means the route is not registered on this firmware. Any other error
        (e.g. 504 while the appliance bus starts up) is raised, so setup retries
        instead of leaving out the controls for that route until a reload.
        """
        response = await self._request("OPTIONS", path)
        if response.status in (404, 405):
            return frozenset()
        if response.status != 200:
            raise LiebherrResponseError("OPTIONS", path, response.status)
        allow = response.headers.get("Allow", "")
        return frozenset(m.strip().upper() for m in allow.split(",") if m.strip())

    async def appliance_info(self) -> dict[str, Any]:
        """Return appliance identity and capabilities."""
        return await self.get("appliance/info")

    async def appliance_state(self) -> dict[str, Any]:
        """Return appliance-wide state."""
        return await self.get("appliance/state")

    async def zone_info(self, zone: int) -> dict[str, Any]:
        """Return a zone's ranges and capabilities."""
        return await self.get(f"zones/{zone}/info")

    async def zone_state(self, zone: int) -> dict[str, Any]:
        """Return a zone's state."""
        return await self.get(f"zones/{zone}/state")
