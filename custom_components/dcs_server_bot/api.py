"""Asynchronous client for the DCSServerBot RestAPI plugin."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import CONTROL_TIMEOUT, DEFAULT_TIMEOUT

MISSION_RESTART_ENDPOINT = "/instance/mission/restart"
SERVER_RESTART_ENDPOINT = "/instance/restart"
LONG_RUNNING_CONTROL_ENDPOINTS = {
    "/instance/start",
    "/instance/stop",
    SERVER_RESTART_ENDPOINT,
    MISSION_RESTART_ENDPOINT,
    "/instance/mission/load",
}


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
        moderation_url: str | None = None,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=timeout)
        self._moderation_url = moderation_url.rstrip("/") if moderation_url else None

    @property
    def base_url(self) -> str:
        """Return the configured API base URL."""
        return self._base_url

    @property
    def moderation_url(self) -> str | None:
        """Return the optional companion moderation endpoint."""
        return self._moderation_url

    async def async_check_moderation(self) -> bool:
        """Validate that the optional moderation bridge is reachable."""
        payload = await self._async_request("GET", "/health", moderation=True)
        return isinstance(payload, Mapping) and payload.get("status") == "ok"

    async def async_moderate(
        self,
        action: str,
        player_name: str,
        *,
        server_name: str | None = None,
        reason: str = "Moderation by Home Assistant",
        days: int = 0,
    ) -> dict[str, Any]:
        """Kick, ban, or unban a player through the companion bridge."""
        body: dict[str, Any] = {
            "player_name": player_name,
            "reason": reason,
        }
        if server_name:
            body["server_name"] = server_name
        if action == "ban":
            body["days"] = days
        payload = await self._async_request("POST", f"/{action}", json_data=body, moderation=True)
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError("Moderation endpoint returned invalid data")
        return dict(payload)

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
                dict(player) for player in server.get("players", []) if isinstance(player, Mapping)
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

    async def async_get_server_attendance(self, server_name: str) -> dict[str, Any]:
        """Return attendance statistics for one DCS server."""
        payload = await self._async_request(
            "GET", "/server_attendance", params={"server_name": server_name}
        )
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError(
                "The /server_attendance endpoint returned an invalid response"
            )
        return dict(payload)

    async def async_get_top_kills(
        self, *, limit: int = 10, server_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Return the kill leaderboard."""
        params = {"limit": str(limit)}
        if server_name:
            params["server_name"] = server_name
        payload = await self._async_request("GET", "/topkills", params=params)
        if not isinstance(payload, list):
            raise DCSServerBotResponseError("The /topkills endpoint did not return a list")
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    async def async_get_top_kdr(
        self, *, limit: int = 10, server_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Return the K/D leaderboard."""
        params = {"limit": str(limit)}
        if server_name:
            params["server_name"] = server_name
        payload = await self._async_request("GET", "/topkdr", params=params)
        if not isinstance(payload, list):
            raise DCSServerBotResponseError("The /topkdr endpoint did not return a list")
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    async def async_get_highscore(self, *, limit: int = 5, period: str = "all") -> dict[str, Any]:
        """Return high-score categories."""
        payload = await self._async_request(
            "GET", "/highscore", params={"limit": str(limit), "period": period}
        )
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError("The /highscore endpoint returned invalid data")
        return dict(payload)

    async def async_get_airbases(self, server_name: str) -> list[dict[str, Any]]:
        """Return airbases in the active mission."""
        payload = await self._async_request("GET", "/airbases", params={"server_name": server_name})
        if not isinstance(payload, Mapping) or not isinstance(payload.get("airbases"), list):
            raise DCSServerBotResponseError("The /airbases endpoint returned invalid data")
        return [dict(item) for item in payload["airbases"] if isinstance(item, Mapping)]

    async def async_get_airbase_warehouse(
        self, server_name: str, airbase_name: str
    ) -> dict[str, Any]:
        """Return stock information for one selected airbase."""
        payload = await self._async_request(
            "GET",
            "/airbase/warehouse",
            params={"server_name": server_name, "airbase_name": airbase_name},
            timeout=ClientTimeout(total=75),
        )
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError("The /airbase/warehouse endpoint returned invalid data")
        return dict(payload)

    async def async_get_operations_snapshot(self) -> dict[str, Any]:
        """Return read-only performance, VIP and mission-history data."""
        payload = await self._async_request("GET", "/operations/snapshot", moderation=True)
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError(
                "The operations companion endpoint returned invalid data"
            )
        return dict(payload)

    async def async_get_greenieboard(self, server_name: str) -> dict[str, Any]:
        """Return recent carrier-landing grades for one server."""
        payload = await self._async_request(
            "POST",
            "/greenieboard",
            form_data={"server_name": server_name},
            timeout=ClientTimeout(total=30),
        )
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError("The /greenieboard endpoint returned invalid data")
        players = payload.get("players", [])
        if not isinstance(players, list):
            payload = dict(payload)
            payload["players"] = []
        return dict(payload)

    async def async_get_mission_bullseyes(self, server_name: str) -> list[dict[str, Any]]:
        """Return coalition bullseye coordinates for the active mission."""
        payload = await self._async_request(
            "GET",
            "/mission/bullseyes",
            params={"server_name": server_name},
            timeout=ClientTimeout(total=15),
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("bullseyes"), list):
            raise DCSServerBotResponseError(
                "The /mission/bullseyes endpoint returned invalid data"
            )
        return [dict(item) for item in payload["bullseyes"] if isinstance(item, Mapping)]

    async def async_get_mission_drawings(self, server_name: str) -> dict[str, list[dict[str, Any]]]:
        """Return mission drawing objects grouped by layer."""
        payload = await self._async_request(
            "GET",
            "/mission/drawings",
            params={"server_name": server_name},
            timeout=ClientTimeout(total=15),
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("drawings"), Mapping):
            raise DCSServerBotResponseError(
                "The /mission/drawings endpoint returned invalid data"
            )
        return {
            str(layer): [dict(item) for item in items if isinstance(item, Mapping)]
            for layer, items in payload["drawings"].items()
            if isinstance(items, list)
        }

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
        timeout = (
            ClientTimeout(total=CONTROL_TIMEOUT)
            if endpoint in LONG_RUNNING_CONTROL_ENDPOINTS
            else None
        )
        try:
            payload = await self._async_request("POST", endpoint, params=params, timeout=timeout)
        except DCSServerBotResponseError as err:
            if not (
                endpoint == MISSION_RESTART_ENDPOINT
                and str(err) == "Timeout while restarting mission."
            ):
                raise
            payload = await self._async_request(
                "POST",
                SERVER_RESTART_ENDPOINT,
                params={"server_name": server_name},
                timeout=ClientTimeout(total=CONTROL_TIMEOUT),
            )
            if isinstance(payload, Mapping):
                payload = dict(payload)
                payload["fallback"] = "server_restart"
        if not isinstance(payload, Mapping):
            raise DCSServerBotResponseError("Control endpoint returned invalid data")
        return dict(payload)

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_data: Mapping[str, Any] | None = None,
        form_data: Mapping[str, str] | None = None,
        moderation: bool = False,
        timeout: ClientTimeout | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        base_url = self._moderation_url if moderation else self._base_url
        if not base_url:
            raise DCSServerBotConnectionError("Moderation bridge is not configured")
        try:
            async with self._session.request(
                method,
                f"{base_url}{path}",
                headers=headers,
                params=params,
                json=json_data,
                data=form_data,
                ssl=self._verify_ssl,
                timeout=timeout or self._timeout,
            ) as response:
                await self._raise_for_status(response)
                try:
                    return await response.json(content_type=None)
                except (ValueError, TypeError) as err:
                    raise DCSServerBotResponseError(f"Invalid JSON returned by {path}") from err
        except DCSServerBotError:
            raise
        except (TimeoutError, ClientError, OSError) as err:
            raise DCSServerBotConnectionError(
                f"Cannot connect to DCSServerBot at {base_url}"
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
