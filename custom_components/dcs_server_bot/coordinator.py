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
    EVENT_IMPORTANT_PLAYER_JOINED,
    EVENT_MISSION_ENDED,
    EVENT_PERFORMANCE_ALERT,
    EVENT_PLAYER_JOINED,
    EVENT_PLAYER_LEFT,
    EVENT_SERVER_STATUS_CHANGED,
    EXTENDED_DATA_INTERVAL,
    LOW_FPS_DURATION,
    LOW_FPS_THRESHOLD,
    MISSION_STALL_DURATION,
    STATISTICS_INTERVAL,
    TELEMETRY_STALE_AFTER,
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
        self.enable_control = bool(entry.options.get(CONF_ENABLE_CONTROL, DEFAULT_ENABLE_CONTROL))
        self.enable_moderation = bool(
            entry.options.get(CONF_ENABLE_MODERATION, DEFAULT_ENABLE_MODERATION)
        )
        self.selected_players: dict[str, str] = {}
        self.selected_airbases: dict[str, str] = {}
        scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self._previous: dict[str, dict[str, Any]] | None = None
        self._statistics: dict[str, Any] = {}
        self._attendance: dict[str, dict[str, Any]] = {}
        self._rankings: dict[str, Any] = {}
        self._airbases: dict[str, list[dict[str, Any]]] = {}
        self._warehouses: dict[str, dict[str, Any]] = {}
        self._operations: dict[str, Any] = {}
        self._alerts: dict[str, dict[str, bool]] = {}
        self._previous_alerts: dict[str, dict[str, bool]] = {}
        self._low_fps_since: dict[str, datetime] = {}
        self._mission_progress: dict[str, tuple[str, int, datetime]] = {}
        self._active_mission_ids: dict[str, int] = {}
        self._statistics_updated_at: datetime | None = None
        self._extended_updated_at: datetime | None = None
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
                        missions[server_name] = await self.client.async_get_missions(server_name)
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
                    self._operations = await self.client.async_get_operations_snapshot()
                except DCSServerBotError as err:
                    _LOGGER.warning("Moderation bridge is unavailable: %s", err)
            if (
                self._statistics_updated_at is None
                or now - self._statistics_updated_at >= STATISTICS_INTERVAL
            ):
                await self._async_update_statistics(servers)
                self._statistics_updated_at = now

            if (
                self._extended_updated_at is None
                or now - self._extended_updated_at >= EXTENDED_DATA_INTERVAL
            ):
                await self._async_update_extended_data(servers)
                self._extended_updated_at = now

            self._alerts = self._build_alerts(servers, now)

            self._fire_transition_events(servers)
            self._previous = servers
            self._previous_alerts = {key: dict(value) for key, value in self._alerts.items()}
            return {
                "servers": servers,
                "missions": missions,
                "statistics": self._statistics,
                "attendance": self._attendance,
                "rankings": self._rankings,
                "airbases": self._airbases,
                "warehouses": self._warehouses,
                "operations": self._operations,
                "alerts": self._alerts,
                "moderation_available": moderation_available,
                "operations_available": bool(self._operations),
                "summary": {
                    "server_count": len(servers),
                    "online_count": sum(
                        str(item.get("status", "")).lower() in {"running", "paused"}
                        for item in servers.values()
                    ),
                    "player_count": sum(len(item.get("players", [])) for item in servers.values()),
                },
            }
        except DCSServerBotAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except DCSServerBotError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_statistics(self, servers: dict[str, dict[str, Any]]) -> None:
        """Refresh slower database-backed statistics without failing core status."""
        try:
            self._statistics = await self.client.async_get_server_stats()
        except DCSServerBotError as err:
            _LOGGER.debug("Unable to update global server statistics: %s", err)

        attendance: dict[str, dict[str, Any]] = {}
        for server_name in servers:
            try:
                attendance[server_name] = await self.client.async_get_server_attendance(server_name)
            except DCSServerBotError as err:
                _LOGGER.debug("Unable to update attendance for %s: %s", server_name, err)
        if attendance:
            self._attendance = attendance

    async def _async_update_extended_data(self, servers: dict[str, dict[str, Any]]) -> None:
        """Refresh read-only Operations Center datasets."""
        try:
            self._rankings = {
                "top_kills": await self.client.async_get_top_kills(limit=10),
                "top_kdr": await self.client.async_get_top_kdr(limit=10),
                "highscore": await self.client.async_get_highscore(limit=5),
            }
        except DCSServerBotError as err:
            _LOGGER.debug("Unable to update rankings: %s", err)

        for server_name, server in servers.items():
            if str(server.get("status", "")).lower() not in {"running", "paused"}:
                continue
            try:
                airbases = await self.client.async_get_airbases(server_name)
                self._airbases[server_name] = airbases
                names = [str(item["name"]) for item in airbases if item.get("name")]
                selected = self.selected_airbases.get(server_name)
                if selected not in names:
                    selected = names[0] if names else None
                    if selected:
                        self.selected_airbases[server_name] = selected
                if selected:
                    self._warehouses[server_name] = await self.client.async_get_airbase_warehouse(
                        server_name, selected
                    )
            except DCSServerBotError as err:
                _LOGGER.debug("Unable to update airbases for %s: %s", server_name, err)

    def _build_alerts(
        self, servers: dict[str, dict[str, Any]], now: datetime
    ) -> dict[str, dict[str, bool]]:
        """Build debounced performance alerts from bridge telemetry."""
        performance = self._operations.get("performance", {})
        alerts: dict[str, dict[str, bool]] = {}
        for server_name, server in servers.items():
            item = performance.get(server_name, {})
            fps = item.get("fps")
            if isinstance(fps, int | float) and fps < LOW_FPS_THRESHOLD:
                self._low_fps_since.setdefault(server_name, now)
            else:
                self._low_fps_since.pop(server_name, None)
            low_fps = (
                server_name in self._low_fps_since
                and now - self._low_fps_since[server_name] >= LOW_FPS_DURATION
            )

            mission = server.get("mission") or {}
            mission_name = str(mission.get("name") or "")
            mission_time = item.get("mission_time")
            progress = self._mission_progress.get(server_name)
            if isinstance(mission_time, int | float):
                current_time = int(mission_time)
                if progress is None or progress[0] != mission_name or current_time > progress[1]:
                    self._mission_progress[server_name] = (
                        mission_name,
                        current_time,
                        now,
                    )
                    progress = self._mission_progress[server_name]
            sample_age = item.get("sample_age_seconds")
            telemetry_fresh = (
                isinstance(sample_age, int | float)
                and sample_age <= TELEMETRY_STALE_AFTER.total_seconds()
            )
            running = str(server.get("status", "")).lower() == "running"
            stalled = bool(
                running
                and mission_name
                and telemetry_fresh
                and progress
                and now - progress[2] >= MISSION_STALL_DURATION
            )
            alerts[server_name] = {"low_fps": low_fps, "mission_stalled": stalled}
        return alerts

    def _fire_transition_events(self, servers: dict[str, dict[str, Any]]) -> None:
        """Emit useful HA events only after the initial successful poll."""
        if self._previous is None:
            self._active_mission_ids = self._current_active_mission_ids()
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
                vip_players = {
                    str(name).casefold() for name in self._operations.get("vip_players", [])
                }
                if player.casefold() in vip_players:
                    self.hass.bus.async_fire(
                        EVENT_IMPORTANT_PLAYER_JOINED,
                        {"server_name": server_name, "player": player},
                    )
            for player in sorted(old_players - new_players):
                self.hass.bus.async_fire(
                    EVENT_PLAYER_LEFT,
                    {"server_name": server_name, "player": player},
                )

            old_mission = (previous.get("mission") or {}).get("name")
            new_mission = (current.get("mission") or {}).get("name")
            current_ids = self._current_active_mission_ids()
            old_mission_id = self._active_mission_ids.get(server_name)
            new_mission_id = current_ids.get(server_name)
            if old_mission and (old_mission != new_mission or old_mission_id != new_mission_id):
                history = self._operations.get("missions", [])
                summary = next(
                    (
                        item
                        for item in history
                        if item.get("server_name") == server_name
                        and (
                            item.get("id") == old_mission_id
                            or (old_mission_id is None and item.get("mission_name") == old_mission)
                        )
                    ),
                    {},
                )
                self.hass.bus.async_fire(
                    EVENT_MISSION_ENDED,
                    {
                        "server_name": server_name,
                        "mission_name": old_mission,
                        "next_mission": new_mission,
                        "summary": summary,
                    },
                )

            previous_alerts = self._previous_alerts.get(server_name, {})
            current_alerts = self._alerts.get(server_name, {})
            for alert_type in ("low_fps", "mission_stalled"):
                if current_alerts.get(alert_type) and not previous_alerts.get(alert_type):
                    performance = self._operations.get("performance", {}).get(server_name, {})
                    self.hass.bus.async_fire(
                        EVENT_PERFORMANCE_ALERT,
                        {
                            "server_name": server_name,
                            "alert_type": alert_type,
                            "fps": performance.get("fps"),
                            "cpu": performance.get("cpu"),
                            "memory_percent": performance.get("memory_percent"),
                        },
                    )

        self._active_mission_ids = self._current_active_mission_ids()

    def _current_active_mission_ids(self) -> dict[str, int]:
        """Return current mission database IDs grouped by server."""
        return {
            str(item["server_name"]): int(item["id"])
            for item in self._operations.get("missions", [])
            if item.get("server_name")
            and item.get("id") is not None
            and not item.get("mission_end")
        }

    def server(self, server_name: str) -> dict[str, Any]:
        """Return one server record."""
        return self.data.get("servers", {}).get(server_name, {})

    async def async_select_airbase(self, server_name: str, airbase_name: str) -> None:
        """Select one airbase and refresh its warehouse immediately."""
        self.selected_airbases[server_name] = airbase_name
        self._warehouses[server_name] = await self.client.async_get_airbase_warehouse(
            server_name, airbase_name
        )
        await self.async_request_refresh()
