"""Mission selection for DCS Server Bot."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    async_add_entities(
        [
            DCSServerMissionSelect(coordinator, server_name)
            for server_name in coordinator.data.get("servers", {})
        ]
    )


class DCSServerMissionSelect(DCSServerEntity, SelectEntity):
    _attr_translation_key = "mission_select"
    _attr_icon = "mdi:map-search"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "mission_select")

    @property
    def options(self) -> list[str]:
        return sorted(
            {
                str(item.get("name"))
                for item in self.coordinator.data.get("missions", {}).get(
                    self.server_name, []
                )
                if item.get("name")
            }
        )

    @property
    def current_option(self) -> str | None:
        name = (self.server.get("mission") or {}).get("name")
        return str(name) if name in self.options else None

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_mission",
                translation_placeholders={"mission_name": option},
            )
        try:
            await self.coordinator.client.async_control(
                "/instance/mission/load",
                self.server_name,
                mission_name=option,
            )
        except DCSServerBotError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()

