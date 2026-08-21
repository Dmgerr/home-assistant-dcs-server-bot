"""Sensors for DCS Server Bot Operations Center."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DCSServerBotCoordinator
from .entity import DCSServerBotEntity, DCSServerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create hub and per-server sensors."""
    coordinator: DCSServerBotCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        DCSServerCountSensor(coordinator),
        DCSOnlineServerCountSensor(coordinator),
        DCSTotalPlayerCountSensor(coordinator),
        DCSRegisteredPilotCountSensor(coordinator),
        DCSTotalSortiesSensor(coordinator),
        DCSTotalKillsSensor(coordinator),
        DCSTotalDeathsSensor(coordinator),
        DCSTotalPlaytimeSensor(coordinator),
        DCSRankingsSensor(coordinator),
        DCSMissionHistorySensor(coordinator),
        DCSVIPPlayersSensor(coordinator),
        DCSMissionActivitySensor(coordinator),
        DCSFirewallStatusSensor(coordinator),
        DCSBlockedAddressesSensor(coordinator),
        DCSNetworkReceiveSensor(coordinator),
        DCSNetworkTransmitSensor(coordinator),
        DCSNUMATopologySensor(coordinator),
    ]
    for server_name in coordinator.data.get("servers", {}):
        entities.extend(
            [
                DCSServerStatusSensor(coordinator, server_name),
                DCSServerPlayersSensor(coordinator, server_name),
                DCSServerMissionSensor(coordinator, server_name),
                DCSServerMissionUptimeSensor(coordinator, server_name),
                DCSServerTemperatureSensor(coordinator, server_name),
                DCSServerWindSpeedSensor(coordinator, server_name),
                DCSServerExtensionsSensor(coordinator, server_name),
                DCSServerAddressSensor(coordinator, server_name),
                DCSServerRestartTimeSensor(coordinator, server_name),
                DCSServerUniquePilots24hSensor(coordinator, server_name),
                DCSServerUniquePilots7dSensor(coordinator, server_name),
                DCSServerUniquePilots30dSensor(coordinator, server_name),
                DCSServerAttendanceSensor(coordinator, server_name),
                DCSServerFPSSensor(coordinator, server_name),
                DCSServerCPUSensor(coordinator, server_name),
                DCSServerMemorySensor(coordinator, server_name),
                DCSServerPingSensor(coordinator, server_name),
                DCSServerTelemetryTimeSensor(coordinator, server_name),
                DCSServerAirbasesSensor(coordinator, server_name),
                DCSServerWarehouseSensor(coordinator, server_name),
                DCSServerLastAARSensor(coordinator, server_name),
                DCSServerMissionWeatherSensor(coordinator, server_name),
                DCSServerGreenieboardSensor(coordinator, server_name),
                DCSServerBullseyesSensor(coordinator, server_name),
                DCSServerMissionDrawingsSensor(coordinator, server_name),
                DCSServerCPUAffinitySensor(coordinator, server_name),
            ]
        )
    async_add_entities(entities)


class DCSServerCountSensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "server_count"
    _attr_icon = "mdi:server-network"
    _attr_native_unit_of_measurement = "servers"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "server_count")

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data["summary"]["server_count"])


class DCSOnlineServerCountSensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "online_server_count"
    _attr_icon = "mdi:server-security"
    _attr_native_unit_of_measurement = "servers"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "online_server_count")

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data["summary"]["online_count"])


class DCSTotalPlayerCountSensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "total_player_count"
    _attr_icon = "mdi:account-group"
    _attr_native_unit_of_measurement = "players"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "total_player_count")

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data["summary"]["player_count"])


class DCSGlobalStatisticSensor(DCSServerBotEntity, SensorEntity):
    """Base class for aggregate DCSServerBot statistics."""

    _statistic_key: str

    def __init__(self, coordinator: DCSServerBotCoordinator, key: str) -> None:
        super().__init__(coordinator, key)

    @property
    def native_value(self) -> int | float | None:
        value = self.coordinator.data.get("statistics", {}).get(self._statistic_key)
        return value if isinstance(value, int | float) else None


class DCSRegisteredPilotCountSensor(DCSGlobalStatisticSensor):
    _attr_translation_key = "registered_pilots"
    _attr_icon = "mdi:account-group-outline"
    _attr_native_unit_of_measurement = "pilots"
    _attr_state_class = SensorStateClass.TOTAL
    _statistic_key = "totalPlayers"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "registered_pilots")


class DCSTotalSortiesSensor(DCSGlobalStatisticSensor):
    _attr_translation_key = "total_sorties"
    _attr_icon = "mdi:airplane-takeoff"
    _attr_native_unit_of_measurement = "sorties"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _statistic_key = "totalSorties"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "total_sorties")


class DCSTotalKillsSensor(DCSGlobalStatisticSensor):
    _attr_translation_key = "total_kills"
    _attr_icon = "mdi:target"
    _attr_native_unit_of_measurement = "kills"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _statistic_key = "totalKills"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "total_kills")


class DCSTotalDeathsSensor(DCSGlobalStatisticSensor):
    _attr_translation_key = "total_deaths"
    _attr_icon = "mdi:airplane-alert"
    _attr_native_unit_of_measurement = "deaths"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _statistic_key = "totalDeaths"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "total_deaths")


class DCSTotalPlaytimeSensor(DCSGlobalStatisticSensor):
    _attr_translation_key = "total_playtime"
    _attr_icon = "mdi:timer-sand-complete"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _statistic_key = "totalPlaytime"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "total_playtime")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "daily_players": self.coordinator.data.get("statistics", {}).get("daily_players", [])
        }


class DCSServerStatusSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "status"
    _attr_icon = "mdi:server"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "status")

    @property
    def native_value(self) -> str:
        return str(self.server.get("status", "unknown"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "description": self.server.get("description", ""),
            "max_players": self.server.get("max_players"),
            "require_pure_clients": self.server.get("require_pure_clients"),
            "require_pure_models": self.server.get("require_pure_models"),
            "require_pure_scripts": self.server.get("require_pure_scripts"),
            "require_pure_textures": self.server.get("require_pure_textures"),
        }


class DCSServerPlayersSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "players"
    _attr_icon = "mdi:account-multiple"
    _attr_native_unit_of_measurement = "players"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "players")

    @property
    def native_value(self) -> int:
        return len(self.server.get("players", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        players = self.server.get("players", [])[:64]
        return {
            "max_players": self.server.get("max_players"),
            "players": [
                {
                    "nick": item.get("nick"),
                    "side": item.get("side"),
                    "unit_type": item.get("unit_type"),
                    "callsign": item.get("callsign"),
                    "radios": item.get("radios", []),
                }
                for item in players
            ],
        }


class DCSServerMissionSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "mission"
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "mission")

    @property
    def native_value(self) -> str | None:
        mission = self.server.get("mission") or {}
        return mission.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mission = self.server.get("mission") or {}
        return {
            key: mission.get(key)
            for key in (
                "theatre",
                "date_time",
                "blue_slots",
                "blue_slots_used",
                "red_slots",
                "red_slots_used",
                "restart_time",
            )
            if mission.get(key) is not None
        }


class DCSServerMissionUptimeSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "mission_uptime"
    _attr_icon = "mdi:timer-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "mission_uptime")

    @property
    def native_value(self) -> int | None:
        value = (self.server.get("mission") or {}).get("uptime")
        return int(value) if value is not None else None


class DCSServerTemperatureSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "temperature")

    @property
    def native_value(self) -> float | None:
        weather = self.server.get("weather") or {}
        value = weather.get("temperature")
        return float(value) if value is not None else None


class DCSServerWindSpeedSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "wind_speed"
    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.METERS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "wind_speed")

    @property
    def native_value(self) -> float | None:
        weather = self.server.get("weather") or {}
        value = weather.get("wind_speed")
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weather = self.server.get("weather") or {}
        return {
            key: weather.get(key) for key in weather if key not in {"temperature", "wind_speed"}
        }


class DCSServerExtensionsSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "extensions"
    _attr_icon = "mdi:puzzle"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "extensions")

    @property
    def native_value(self) -> int:
        return len(self.server.get("extensions", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"extensions": self.server.get("extensions", [])}


class DCSServerAddressSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "address"
    _attr_icon = "mdi:ip-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "address")

    @property
    def native_value(self) -> str | None:
        return self.server.get("address")


class DCSServerRestartTimeSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "restart_time"
    _attr_icon = "mdi:restart-alert"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "restart_time")

    @property
    def native_value(self) -> datetime | None:
        raw = self.server.get("restart_time")
        if not raw:
            raw = (self.server.get("mission") or {}).get("restart_time")
        if raw is None:
            return None
        try:
            if isinstance(raw, int | float):
                return datetime.fromtimestamp(raw, tz=UTC)
            parsed = datetime.fromisoformat(str(raw))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
        except (ValueError, TypeError, OSError):
            return None


class DCSServerAttendanceMetricSensor(DCSServerEntity, SensorEntity):
    """Base class for one server-attendance metric."""

    _attendance_key: str

    @property
    def native_value(self) -> int | float | None:
        value = (
            self.coordinator.data.get("attendance", {})
            .get(self.server_name, {})
            .get(self._attendance_key)
        )
        return value if isinstance(value, int | float) else None


class DCSServerUniquePilots24hSensor(DCSServerAttendanceMetricSensor):
    _attr_translation_key = "unique_pilots_24h"
    _attr_icon = "mdi:account-clock"
    _attr_native_unit_of_measurement = "pilots"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attendance_key = "unique_players_24h"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "unique_pilots_24h")


class DCSServerUniquePilots7dSensor(DCSServerAttendanceMetricSensor):
    _attr_translation_key = "unique_pilots_7d"
    _attr_icon = "mdi:account-multiple-check"
    _attr_native_unit_of_measurement = "pilots"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attendance_key = "unique_players_7d"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "unique_pilots_7d")


class DCSServerUniquePilots30dSensor(DCSServerAttendanceMetricSensor):
    _attr_translation_key = "unique_pilots_30d"
    _attr_icon = "mdi:account-group"
    _attr_native_unit_of_measurement = "pilots"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attendance_key = "unique_players_30d"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "unique_pilots_30d")


class DCSServerAttendanceSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "attendance"
    _attr_icon = "mdi:chart-box-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "attendance")

    @property
    def native_value(self) -> int | None:
        value = (
            self.coordinator.data.get("attendance", {})
            .get(self.server_name, {})
            .get("unique_players_7d")
        )
        return int(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.data.get("attendance", {}).get(self.server_name, {})


class DCSRankingsSensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "rankings"
    _attr_icon = "mdi:trophy"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "rankings")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("rankings", {}).get("top_kills", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.data.get("rankings", {})


class DCSMissionHistorySensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "mission_history"
    _attr_icon = "mdi:history"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "mission_history")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("operations", {}).get("missions", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"missions": self.coordinator.data.get("operations", {}).get("missions", [])[:20]}


class DCSVIPPlayersSensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "vip_players"
    _attr_icon = "mdi:account-star"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "vip_players")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("operations", {}).get("vip_players", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"players": self.coordinator.data.get("operations", {}).get("vip_players", [])}


class DCSServerPerformanceSensor(DCSServerEntity, SensorEntity):
    """Base class for one metric from the companion bridge."""

    _performance_key: str

    @property
    def native_value(self) -> float | int | None:
        value = (
            self.coordinator.data.get("operations", {})
            .get("performance", {})
            .get(self.server_name, {})
            .get(self._performance_key)
        )
        return value if isinstance(value, int | float) else None


class DCSServerFPSSensor(DCSServerPerformanceSensor):
    _attr_translation_key = "fps"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _attr_state_class = SensorStateClass.MEASUREMENT
    _performance_key = "fps"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "fps")


class DCSServerCPUSensor(DCSServerPerformanceSensor):
    _attr_translation_key = "cpu"
    _attr_icon = "mdi:cpu-64-bit"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _performance_key = "cpu"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "cpu")


class DCSServerMemorySensor(DCSServerPerformanceSensor):
    _attr_translation_key = "memory"
    _attr_icon = "mdi:memory"
    _attr_native_unit_of_measurement = UnitOfInformation.GIBIBYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _performance_key = "memory_gib"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "memory")


class DCSServerPingSensor(DCSServerPerformanceSensor):
    _attr_translation_key = "ping"
    _attr_icon = "mdi:lan-pending"
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _performance_key = "ping"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "ping")


class DCSServerTelemetryTimeSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "telemetry_time"
    _attr_icon = "mdi:database-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "telemetry_time")

    @property
    def native_value(self) -> datetime | None:
        raw = (
            self.coordinator.data.get("operations", {})
            .get("performance", {})
            .get(self.server_name, {})
            .get("time")
        )
        if not raw:
            return None
        try:
            value = datetime.fromisoformat(str(raw))
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value
        except ValueError:
            return None


class DCSServerAirbasesSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "airbases"
    _attr_icon = "mdi:airport"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "airbases")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("airbases", {}).get(self.server_name, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        airbases = self.coordinator.data.get("airbases", {}).get(self.server_name, [])
        return {
            "airbases": [
                {
                    "name": item.get("name"),
                    "code": item.get("code"),
                    "coalition": item.get("coalition"),
                    "latitude": item.get("lat"),
                    "longitude": item.get("lng"),
                    "runways": item.get("runwayList", []),
                    "dynamic_spawn": (item.get("dynamic") or {}).get("dynamicSpawnAvailable"),
                }
                for item in airbases[:64]
            ]
        }


class DCSServerWarehouseSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "warehouse"
    _attr_icon = "mdi:warehouse"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "warehouse")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.selected_airbases.get(self.server_name)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        payload = self.coordinator.data.get("warehouses", {}).get(self.server_name, {})
        warehouse = payload.get("warehouse", {})

        def compact(category: str, limit: int = 40) -> list[dict[str, Any]]:
            values = warehouse.get(category, {})
            if not isinstance(values, dict):
                return []
            return [
                {"item": str(key).split(".")[-1], "quantity": value}
                for key, value in sorted(values.items())[:limit]
            ]

        return {
            "airbase": self.coordinator.selected_airbases.get(self.server_name),
            "unlimited": payload.get("unlimited", {}),
            "aircraft": compact("aircraft"),
            "weapons": compact("weapon"),
            "liquids": compact("liquids", 10),
            "aircraft_types": len(warehouse.get("aircraft", {})),
            "weapon_types": len(warehouse.get("weapon", {})),
        }


class DCSServerLastAARSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "last_aar"
    _attr_icon = "mdi:file-document-check-outline"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "last_aar")

    @property
    def _record(self) -> dict[str, Any]:
        return next(
            (
                item
                for item in self.coordinator.data.get("operations", {}).get("missions", [])
                if item.get("server_name") == self.server_name and item.get("mission_end")
            ),
            {},
        )

    @property
    def native_value(self) -> str | None:
        return self._record.get("mission_name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._record


class DCSMissionActivitySensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "mission_activity"
    _attr_icon = "mdi:timeline-clock-outline"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "mission_activity")

    @property
    def _events(self) -> list[dict[str, Any]]:
        return self.coordinator.data.get("operations", {}).get("events", [])[:100]

    @property
    def native_value(self) -> str | None:
        return str(self._events[0].get("event")) if self._events else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"events": self._events, "event_count": len(self._events)}


class DCSFirewallStatusSensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "firewall_status"
    _attr_icon = "mdi:shield-lock-outline"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "firewall_status")

    @property
    def native_value(self) -> str:
        firewall = self.coordinator.data.get("operations", {}).get("firewall", {})
        profiles = firewall.get("profiles") or []
        if profiles and not all(bool(item.get("enabled")) for item in profiles):
            return "firewall_disabled"
        if not firewall.get("service_configured"):
            return "monitoring_not_configured"
        return "under_attack" if firewall.get("under_attack") else "protected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        firewall = self.coordinator.data.get("operations", {}).get("firewall", {})
        return {
            "service_configured": bool(firewall.get("service_configured")),
            "profiles": firewall.get("profiles", []),
            "ports": firewall.get("ports", [])[:24],
            "under_attack": bool(firewall.get("under_attack")),
            "read_error": bool(firewall.get("read_error")),
        }


class DCSBlockedAddressesSensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "blocked_addresses"
    _attr_icon = "mdi:ip-off-outline"
    _attr_native_unit_of_measurement = "addresses"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "blocked_addresses")

    @property
    def native_value(self) -> int:
        return len(
            self.coordinator.data.get("operations", {})
            .get("firewall", {})
            .get("blocked_ips", [])
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "blocked_ips": self.coordinator.data.get("operations", {})
            .get("firewall", {})
            .get("blocked_ips", [])[:100]
        }


class DCSNetworkRateSensor(DCSServerBotEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _performance_key: str

    @property
    def native_value(self) -> float:
        performance = self.coordinator.data.get("operations", {}).get("performance", {})
        return round(
            sum(
                float(item.get(self._performance_key) or 0)
                for item in performance.values()
                if isinstance(item, dict)
            ),
            2,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        performance = self.coordinator.data.get("operations", {}).get("performance", {})
        return {
            "servers": {
                name: item.get(self._performance_key)
                for name, item in performance.items()
                if isinstance(item, dict)
            }
        }


class DCSNetworkReceiveSensor(DCSNetworkRateSensor):
    _attr_translation_key = "network_receive"
    _attr_icon = "mdi:download-network-outline"
    _performance_key = "bytes_recv"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "network_receive")


class DCSNetworkTransmitSensor(DCSNetworkRateSensor):
    _attr_translation_key = "network_transmit"
    _attr_icon = "mdi:upload-network-outline"
    _performance_key = "bytes_sent"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "network_transmit")


class DCSNUMATopologySensor(DCSServerBotEntity, SensorEntity):
    _attr_translation_key = "numa_topology"
    _attr_icon = "mdi:chip"
    _attr_native_unit_of_measurement = "nodes"

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "numa_topology")

    @property
    def _topology(self) -> dict[str, Any]:
        return (
            self.coordinator.data.get("operations", {})
            .get("system", {})
            .get("topology", {})
        )

    @property
    def native_value(self) -> int:
        return len(self._topology.get("numa_nodes", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._topology


class DCSServerMissionWeatherSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "mission_weather"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "mission_weather")

    @property
    def native_value(self) -> str | None:
        weather = self.server.get("weather") or {}
        if not weather:
            return None
        if float(weather.get("precipitation") or 0) > 0:
            return "precipitation"
        if bool(weather.get("fog_enabled")):
            return "fog"
        density = float(weather.get("clouds_density") or 0)
        return "cloudy" if density >= 7 else "partly_cloudy" if density >= 3 else "clear"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.server.get("weather") or {})


class DCSServerGreenieboardSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "greenieboard"
    _attr_icon = "mdi:airplane-marker"
    _attr_native_unit_of_measurement = "pilots"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "greenieboard")

    @property
    def _players(self) -> list[dict[str, Any]]:
        return (
            self.coordinator.data.get("greenieboards", {})
            .get(self.server_name, {})
            .get("players", [])[:20]
        )

    @property
    def native_value(self) -> int:
        return len(self._players)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "players": [
                {**player, "traps": (player.get("traps") or [])[:10]}
                for player in self._players
            ]
        }


class DCSServerBullseyesSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "bullseyes"
    _attr_icon = "mdi:bullseye-arrow"
    _attr_native_unit_of_measurement = "points"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "bullseyes")

    @property
    def _points(self) -> list[dict[str, Any]]:
        return (
            self.coordinator.data.get("mission_layers", {})
            .get(self.server_name, {})
            .get("bullseyes", [])[:4]
        )

    @property
    def native_value(self) -> int:
        return len(self._points)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"bullseyes": self._points}


class DCSServerMissionDrawingsSensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "mission_drawings"
    _attr_icon = "mdi:vector-polyline"
    _attr_native_unit_of_measurement = "objects"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "mission_drawings")

    @property
    def _drawings(self) -> dict[str, list[dict[str, Any]]]:
        return (
            self.coordinator.data.get("mission_layers", {})
            .get(self.server_name, {})
            .get("drawings", {})
        )

    @property
    def native_value(self) -> int:
        return sum(len(items) for items in self._drawings.values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        remaining = 100
        layers: dict[str, list[dict[str, Any]]] = {}
        for name, items in self._drawings.items():
            if remaining <= 0:
                break
            layers[name] = items[:remaining]
            remaining -= len(layers[name])
        return {"layers": layers, "layer_count": len(self._drawings)}


class DCSServerCPUAffinitySensor(DCSServerEntity, SensorEntity):
    _attr_translation_key = "cpu_affinity"
    _attr_icon = "mdi:chip"
    _attr_native_unit_of_measurement = "threads"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "cpu_affinity")

    @property
    def _record(self) -> dict[str, Any]:
        processes = (
            self.coordinator.data.get("operations", {})
            .get("system", {})
            .get("process_affinity", [])
        )
        return next((item for item in processes if item.get("server_name") == self.server_name), {})

    @property
    def native_value(self) -> int | None:
        cores = self._record.get("logical_processors")
        return len(cores) if isinstance(cores, list) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._record
