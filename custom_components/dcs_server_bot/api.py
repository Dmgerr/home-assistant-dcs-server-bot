"""Asynchronous client for the DCSServerBot RestAPI plugin."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import DEFAULT_TIMEOUT


class DCSServerBotError(Exception):
    """Base exception for DCSServerBot API failures."""


class DCSServerBotConnectionError(DCSServerBotError):
    """Raised when the API cannot be reached."""


class DCSServerBotAuthenticationError(DCSServerBotError):
    """Raised when the API rejects the API key."""


class DCSServerBotResponseError(DCSServerBotError):
    """Raised when the API returns an invalid response."""


class DCSServerBotClient:
    """Small, dependency-free wrapper around DCSServerBot's REST API."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        api_key: str,
        *,
        verify_ssl: bool = True,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=timeout)

    @property
    def base_url(self) -> str:
        """Return the configured API base URL."""
        return self._base_url

    async def async_get_servers(self) -> list[dict[str, Any]]:
        """Return all servers while dropping secrets from the response."""
        payload = await self._async_request("GET", "/servers")
        if not isinstance(payload, list):
            raise DCSServerBotResponseError("The /servers endpoint did not return a list")

        servers: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, Mapping) or not item.get("name"):
                continue
            server = dict(item)
            server.pop("password", None)
            server["players"] = [
                dict(player)
                for player in server.get("players", [])
                if isinstance(player, Mapping)
            ]
            server["extensions"] = [
                dict(extension)
                for extension in server.get("extensions", [])
                if isinstance(extension, Mapping)
            ]
            servers.append(server)
        return servers

    async def async_get_missions(self, server_name: str) -> list[dict[str, Any]]:
        """Return missions available to one server."""
        payload = await self._async_request(
            "GET", "/instance/missions", params={"server_name": server_name}
        )
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError(
                "The /instance/missions endpoint returned an invalid response"
            )
        missions = payload.get("missions", [])
        if not isinstance(missions, list):
            return []
        return [dict(item) for item in missions if isinstance(item, Mapping)]

    async def async_get_server_stats(self) -> dict[str, Any]:
        """Return aggregate statistics collected by DCSServerBot."""
        payload = await self._async_request("GET", "/serverstats")
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError(
                "The /serverstats endpoint returned an invalid response"
            )
        return dict(payload)

    async def async_get_server_attendance(
        self, server_name: str
    ) -> dict[str, Any]:
        """Return attendance statistics for one DCS server."""
        payload = await self._async_request(
            "GET", "/server_attendance", params={"server_name": server_name}
        )
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError(
                "The /server_attendance endpoint returned an invalid response"
            )
        return dict(payload)

    async def async_control(
        self,
        endpoint: str,
        server_name: str,
        *,
        mission_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute an explicitly enabled server control action."""
        params: dict[str, str] = {"server_name": server_name}
        if mission_name is not None:
            params["mission_name"] = mission_name
        payload = await self._async_request("POST", endpoint, params=params)
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError("Control endpoint returned invalid data")
        return dict(payload)

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                headers=headers,
                params=params,
                ssl=self._verify_ssl,
                timeout=self._timeout,
            ) as response:
                await self._raise_for_status(response)
                try:
                    return await response.json(content_type=None)
                except (ValueError, TypeError) as err:
                    raise DCSServerBotResponseError(
                        f"Invalid JSON returned by {path}"
                    ) from err
        except DCSServerBotError:
            raise
        except (TimeoutError, ClientError, OSError) as err:
            raise DCSServerBotConnectionError(
                f"Cannot connect to DCSServerBot at {self._base_url}"
            ) from err

    @staticmethod
    async def _raise_for_status(response: ClientResponse) -> None:
        if response.status in (401, 403):
            raise DCSServerBotAuthenticationError("The DCSServerBot API key was rejected")
        if response.status < 400:
            return

        detail = f"HTTP {response.status}"
        try:
            body = await response.json(content_type=None)
            if isinstance(body, Mapping) and body.get("detail"):
                detail = str(body["detail"])
        except (ValueError, TypeError, ClientError):
            pass
        raise DCSServerBotResponseError(detail)
