"""DCS Server Bot Operations Center integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DCSServerBotClient, DCSServerBotError
from .const import (
    ATTR_DAYS,
    ATTR_ENTRY_ID,
    ATTR_MISSION_NAME,
    ATTR_PLAYER_NAME,
    ATTR_REASON,
    ATTR_SERVER_NAME,
    CONF_API_KEY,
    CONF_MODERATION_URL,
    CONF_URL,
    CONF_VERIFY_SSL,
    CONTROL_ENDPOINTS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SERVICE_BAN_PLAYER,
    SERVICE_KICK_PLAYER,
    SERVICE_LOAD_MISSION,
    SERVICE_UNBAN_PLAYER,
)
from .coordinator import DCSServerBotCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
]

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SERVER_NAME): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(ATTR_MISSION_NAME): cv.string,
    }
)

MODERATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PLAYER_NAME): cv.string,
        vol.Optional(ATTR_SERVER_NAME): cv.string,
        vol.Optional(ATTR_REASON, default="Moderation by Home Assistant"): cv.string,
        vol.Optional(ATTR_DAYS, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=3650)
        ),
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration actions once per Home Assistant instance."""

    async def async_handle_control(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get(ATTR_ENTRY_ID)
        coordinators: list[DCSServerBotCoordinator] = list(
            hass.data.get(DOMAIN, {}).values()
        )
        if entry_id:
            coordinators = [
                item for item in coordinators if item.entry.entry_id == entry_id
            ]

        server_name = call.data[ATTR_SERVER_NAME]
        coordinator = next(
            (
                item
                for item in coordinators
                if server_name in item.data.get("servers", {})
            ),
            None,
        )
        if coordinator is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="server_not_found",
                translation_placeholders={"server_name": server_name},
            )
        if not coordinator.enable_control:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="control_disabled",
            )

        endpoint = CONTROL_ENDPOINTS[call.service]
        mission_name = call.data.get(ATTR_MISSION_NAME)
        if call.service == SERVICE_LOAD_MISSION and not mission_name:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mission_required",
            )
        try:
            result = await coordinator.client.async_control(
                endpoint,
                server_name,
                mission_name=mission_name,
            )
        except DCSServerBotError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await coordinator.async_request_refresh()
        return result

    for service in CONTROL_ENDPOINTS:
        if not hass.services.has_service(DOMAIN, service):
            hass.services.async_register(
                DOMAIN,
                service,
                async_handle_control,
                schema=SERVICE_SCHEMA,
                supports_response=SupportsResponse.OPTIONAL,
            )

    async def async_handle_moderation(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get(ATTR_ENTRY_ID)
        coordinators: list[DCSServerBotCoordinator] = list(
            hass.data.get(DOMAIN, {}).values()
        )
        if entry_id:
            coordinators = [
                item for item in coordinators if item.entry.entry_id == entry_id
            ]
        coordinator = next(
            (item for item in coordinators if item.enable_moderation), None
        )
        if coordinator is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="moderation_disabled",
            )
        server_name = call.data.get(ATTR_SERVER_NAME)
        if call.service == SERVICE_KICK_PLAYER and not server_name:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="server_required",
            )
        if server_name and server_name not in coordinator.data.get("servers", {}):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="server_not_found",
                translation_placeholders={"server_name": server_name},
            )
        try:
            result = await coordinator.client.async_moderate(
                call.service.removesuffix("_player"),
                call.data[ATTR_PLAYER_NAME],
                server_name=server_name,
                reason=call.data[ATTR_REASON],
                days=call.data[ATTR_DAYS],
            )
        except DCSServerBotError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="moderation_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await coordinator.async_request_refresh()
        return result

    for service in (SERVICE_KICK_PLAYER, SERVICE_BAN_PLAYER, SERVICE_UNBAN_PLAYER):
        if not hass.services.has_service(DOMAIN, service):
            hass.services.async_register(
                DOMAIN,
                service,
                async_handle_moderation,
                schema=MODERATION_SCHEMA,
                supports_response=SupportsResponse.OPTIONAL,
            )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one DCSServerBot connection."""
    session = async_get_clientsession(
        hass,
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    client = DCSServerBotClient(
        session,
        entry.data[CONF_URL],
        entry.data.get(CONF_API_KEY, ""),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        moderation_url=entry.options.get(CONF_MODERATION_URL) or None,
    )
    coordinator = DCSServerBotCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry cleanly."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
