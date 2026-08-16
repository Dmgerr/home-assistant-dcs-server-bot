"""Optional control buttons for DCS Server Bot."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import DCSServerBotError
from .const import DOMAIN
from .coordinator import DCSServerBotCoordinator
from .entity import DCSServerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DCSServerBotCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.enable_control:
        return
    entities: list[ButtonEntity] = []
    for server_name in coordinator.data.get("servers", {}):
        entities.extend(
            [
                DCSServerControlButton(
                    coordinator, server_name, "start", "/instance/start"
                ),
                DCSServerControlButton(
                    coordinator, server_name, "stop", "/instance/stop"
                ),
                DCSServerControlButton(
                    coordinator,
                    server_name,
                    "restart",
                    "/instance/restart",
                    ButtonDeviceClass.RESTART,
                ),
                DCSServerControlButton(
                    coordinator,
                    server_name,
                    "pause_mission",
                    "/instance/mission/pause",
                ),
                DCSServerControlButton(
                    coordinator,
                    server_name,
                    "resume_mission",
                    "/instance/mission/unpause",
                ),
                DCSServerControlButton(
                    coordinator,
                    server_name,
                    "restart_mission",
                    "/instance/mission/restart",
                    ButtonDeviceClass.RESTART,
                ),
            ]
        )
    async_add_entities(entities)


class DCSServerControlButton(DCSServerEntity, ButtonEntity):
    """Execute one explicit DCSServerBot control action."""

    def __init__(
        self,
        coordinator: DCSServerBotCoordinator,
        server_name: str,
        key: str,
        endpoint: str,
        device_class: ButtonDeviceClass | None = None,
    ) -> None:
        super().__init__(coordinator, server_name, key)
        self._attr_translation_key = key
        self._attr_device_class = device_class
        self._endpoint = endpoint
        self._key = key

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        status = str(self.server.get("status", "")).lower()
        if self._key == "start":
            return status in {"shutdown", "stopped"}
        if self._key in {"stop", "pause_mission"}:
            return status == "running"
        if self._key == "resume_mission":
            return status == "paused"
        if self._key == "restart_mission":
            return status in {"running", "paused"}
        return status in {"running", "paused", "shutdown", "stopped"}

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.async_control(
                self._endpoint, self.server_name
            )
        except DCSServerBotError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
