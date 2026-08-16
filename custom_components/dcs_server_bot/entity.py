"""Entity helpers for DCS Server Bot."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DCSServerBotCoordinator


class DCSServerBotEntity(CoordinatorEntity[DCSServerBotCoordinator]):
    """Base entity associated with the DCSServerBot hub."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DCSServerBotCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Special-K's Flightsim Bots",
            model="DCSServerBot REST API",
            configuration_url=coordinator.client.base_url,
        )


class DCSServerEntity(CoordinatorEntity[DCSServerBotCoordinator]):
    """Base entity associated with a single DCS server."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DCSServerBotCoordinator,
        server_name: str,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self.server_name = server_name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{server_name}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{coordinator.entry.entry_id}:{server_name}")
            },
            name=server_name,
            manufacturer="Eagle Dynamics / DCSServerBot",
            model="DCS Dedicated Server",
            via_device=(DOMAIN, coordinator.entry.entry_id),
            configuration_url=coordinator.client.base_url,
        )

    @property
    def server(self) -> dict:
        """Return current server data."""
        return self.coordinator.server(self.server_name)

