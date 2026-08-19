"""Binary sensors for DCS Server Bot."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RUNNING_STATES
from .coordinator import DCSServerBotCoordinator
from .entity import DCSServerBotEntity, DCSServerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DCSServerBotCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [DCSAPIConnectedSensor(coordinator)]
    if coordinator.enable_moderation:
        entities.extend(
            [
                DCSModerationConnectedSensor(coordinator),
                DCSOperationsConnectedSensor(coordinator),
            ]
        )
    for server_name in coordinator.data.get("servers", {}):
        entities.extend(
            [
                DCSServerRunningSensor(coordinator, server_name),
                DCSServerPausedSensor(coordinator, server_name),
                DCSServerLowFPSSensor(coordinator, server_name),
                DCSServerMissionStalledSensor(coordinator, server_name),
            ]
        )
    async_add_entities(entities)


class DCSAPIConnectedSensor(DCSServerBotEntity, BinarySensorEntity):
    _attr_translation_key = "api_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "api_connected")

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success


class DCSModerationConnectedSensor(DCSServerBotEntity, BinarySensorEntity):
    _attr_translation_key = "moderation_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "moderation_connected")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("moderation_available"))


class DCSOperationsConnectedSensor(DCSServerBotEntity, BinarySensorEntity):
    _attr_translation_key = "operations_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: DCSServerBotCoordinator) -> None:
        super().__init__(coordinator, "operations_connected")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("operations_available"))


class DCSServerRunningSensor(DCSServerEntity, BinarySensorEntity):
    _attr_translation_key = "running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "running")

    @property
    def is_on(self) -> bool:
        return str(self.server.get("status", "")).lower() in RUNNING_STATES


class DCSServerPausedSensor(DCSServerEntity, BinarySensorEntity):
    _attr_translation_key = "paused"
    _attr_icon = "mdi:pause-circle"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "paused")

    @property
    def is_on(self) -> bool:
        return str(self.server.get("status", "")).lower() == "paused"


class DCSServerLowFPSSensor(DCSServerEntity, BinarySensorEntity):
    _attr_translation_key = "low_fps"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "low_fps")

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data.get("alerts", {}).get(self.server_name, {}).get("low_fps")
        )


class DCSServerMissionStalledSensor(DCSServerEntity, BinarySensorEntity):
    _attr_translation_key = "mission_stalled"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "mission_stalled")

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data.get("alerts", {}).get(self.server_name, {}).get("mission_stalled")
        )
