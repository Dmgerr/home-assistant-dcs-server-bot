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
    entities: list[SelectEntity] = []
    if coordinator.enable_control:
        entities.extend(
            [
            DCSServerMissionSelect(coordinator, server_name)
            for server_name in coordinator.data.get("servers", {})
            ]
        )
    if coordinator.enable_moderation:
        entities.extend(
            [
                DCSServerPlayerSelect(coordinator, server_name)
                for server_name in coordinator.data.get("servers", {})
            ]
        )
    async_add_entities(entities)


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


class DCSServerPlayerSelect(DCSServerEntity, SelectEntity):
    """Select an active player for an explicit moderation action."""

    _attr_translation_key = "player_select"
    _attr_icon = "mdi:account-search"

    def __init__(self, coordinator: DCSServerBotCoordinator, server_name: str) -> None:
        super().__init__(coordinator, server_name, "player_select")

    @property
    def available(self) -> bool:
        return (
            super().available
            and bool(self.coordinator.data.get("moderation_available"))
            and bool(self.options)
        )

    @property
    def options(self) -> list[str]:
        return sorted(
            {
                str(player.get("nick"))
                for player in self.server.get("players", [])
                if player.get("nick")
            }
        )

    @property
    def current_option(self) -> str | None:
        selected = self.coordinator.selected_players.get(self.server_name)
        return selected if selected in self.options else None

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_player",
                translation_placeholders={"player_name": option},
            )
        self.coordinator.selected_players[self.server_name] = option
        self.async_write_ha_state()
