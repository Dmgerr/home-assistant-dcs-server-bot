"""Data coordinator for DCS Server Bot."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    DCSServerBotAuthenticationError,
    DCSServerBotClient,
    DCSServerBotError,
)
from .const import (
    CONF_ENABLE_CONTROL,
    CONF_ENABLE_MODERATION,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_CONTROL,
    DEFAULT_ENABLE_MODERATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_PLAYER_JOINED,
    EVENT_PLAYER_LEFT,
    EVENT_SERVER_STATUS_CHANGED,
    STATISTICS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class DCSServerBotCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate polling and state-transition events."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DCSServerBotClient,
    ) -> None:
        self.entry = entry
        self.client = client
        self.enable_control = bool(
            entry.options.get(CONF_ENABLE_CONTROL, DEFAULT_ENABLE_CONTROL)
        )
        self.enable_moderation = bool(
            entry.options.get(CONF_ENABLE_MODERATION, DEFAULT_ENABLE_MODERATION)
        )
        self.selected_players: dict[str, str] = {}
        scan_interval = int(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        self._previous: dict[str, dict[str, Any]] | None = None
        self._statistics: dict[str, Any] = {}
        self._attendance: dict[str, dict[str, Any]] = {}
        self._statistics_updated_at: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            server_list = await self.client.async_get_servers()
            servers = {str(server["name"]): server for server in server_list}
            missions: dict[str, list[dict[str, Any]]] = {}
            if self.enable_control:
                for server_name in servers:
                    try:
                        missions[server_name] = await self.client.async_get_missions(
                            server_name
                        )
                    except DCSServerBotError as err:
                        _LOGGER.debug(
                            "Unable to update mission list for %s: %s",
                            server_name,
                            err,
                        )

            now = datetime.now(UTC)
            moderation_available = False
            if self.enable_moderation:
                try:
                    moderation_available = await self.client.async_check_moderation()
                except DCSServerBotError as err:
                    _LOGGER.warning("Moderation bridge is unavailable: %s", err)
            if (
                self._statistics_updated_at is None
                or now - self._statistics_updated_at >= STATISTICS_INTERVAL
            ):
                await self._async_update_statistics(servers)
                self._statistics_updated_at = now

            self._fire_transition_events(servers)
            self._previous = servers
            return {
                "servers": servers,
                "missions": missions,
                "statistics": self._statistics,
                "attendance": self._attendance,
                "moderation_available": moderation_available,
                "summary": {
                    "server_count": len(servers),
                    "online_count": sum(
                        str(item.get("status", "")).lower() in {"running", "paused"}
                        for item in servers.values()
                    ),
                    "player_count": sum(
                        len(item.get("players", [])) for item in servers.values()
                    ),
                },
            }
        except DCSServerBotAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except DCSServerBotError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_statistics(
        self, servers: dict[str, dict[str, Any]]
    ) -> None:
        """Refresh slower database-backed statistics without failing core status."""
        try:
            self._statistics = await self.client.async_get_server_stats()
        except DCSServerBotError as err:
            _LOGGER.debug("Unable to update global server statistics: %s", err)

        attendance: dict[str, dict[str, Any]] = {}
        for server_name in servers:
            try:
                attendance[server_name] = (
                    await self.client.async_get_server_attendance(server_name)
                )
            except DCSServerBotError as err:
                _LOGGER.debug(
                    "Unable to update attendance for %s: %s", server_name, err
                )
        if attendance:
            self._attendance = attendance

    def _fire_transition_events(self, servers: dict[str, dict[str, Any]]) -> None:
        """Emit useful HA events only after the initial successful poll."""
        if self._previous is None:
            return

        for server_name, current in servers.items():
            previous = self._previous.get(server_name, {})
            old_status = str(previous.get("status", "unknown"))
            new_status = str(current.get("status", "unknown"))
            if old_status != new_status:
                self.hass.bus.async_fire(
                    EVENT_SERVER_STATUS_CHANGED,
                    {
                        "entry_id": self.entry.entry_id,
                        "server_name": server_name,
                        "old_status": old_status,
                        "new_status": new_status,
                    },
                )

            old_players = {
                str(player.get("nick"))
                for player in previous.get("players", [])
                if player.get("nick")
            }
            new_players = {
                str(player.get("nick"))
                for player in current.get("players", [])
                if player.get("nick")
            }
            for player in sorted(new_players - old_players):
                self.hass.bus.async_fire(
                    EVENT_PLAYER_JOINED,
                    {"server_name": server_name, "player": player},
                )
            for player in sorted(old_players - new_players):
                self.hass.bus.async_fire(
                    EVENT_PLAYER_LEFT,
                    {"server_name": server_name, "player": player},
                )

    def server(self, server_name: str) -> dict[str, Any]:
        """Return one server record."""
        return self.data.get("servers", {}).get(server_name, {})
