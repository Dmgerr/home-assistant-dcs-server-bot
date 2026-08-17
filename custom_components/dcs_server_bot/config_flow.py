"""Config flow for DCS Server Bot Operations Center."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DCSServerBotAuthenticationError,
    DCSServerBotClient,
    DCSServerBotConnectionError,
    DCSServerBotError,
)
from .const import (
    CONF_API_KEY,
    CONF_ENABLE_CONTROL,
    CONF_ENABLE_MODERATION,
    CONF_MODERATION_URL,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_ENABLE_CONTROL,
    DEFAULT_ENABLE_MODERATION,
    DEFAULT_MODERATION_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_URL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    NAME,
)


def _normalise_url(value: str) -> str:
    return value.strip().rstrip("/")


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_NAME, default=defaults.get(CONF_NAME, NAME)
            ): str,
            vol.Required(
                CONF_URL, default=defaults.get(CONF_URL, DEFAULT_URL)
            ): str,
            vol.Required(
                CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")
            ): str,
            vol.Required(
                CONF_VERIFY_SSL,
                default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): bool,
        }
    )


class DCSServerBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup and reauthentication."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = _normalise_url(user_input[CONF_URL])
            error = await self._async_validate(user_input)
            if error is None:
                await self.async_set_unique_id(user_input[CONF_URL].lower())
                self._abort_if_unique_id_configured()
                title = user_input.pop(CONF_NAME, NAME)
                return self.async_create_entry(title=title, data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input), errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None
        if user_input is not None:
            data = {**self._reauth_entry.data, **user_input}
            error = await self._async_validate(data)
            if error is None:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=data
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_KEY, default=""): str}
            ),
            errors=errors,
        )

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        parsed = urlparse(data[CONF_URL])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "invalid_url"
        session = async_get_clientsession(
            self.hass, verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        )
        client = DCSServerBotClient(
            session,
            data[CONF_URL],
            data.get(CONF_API_KEY, ""),
            verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        try:
            await client.async_get_servers()
        except DCSServerBotAuthenticationError:
            return "invalid_auth"
        except DCSServerBotConnectionError:
            return "cannot_connect"
        except DCSServerBotError:
            return "invalid_response"
        return None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DCSServerBotOptionsFlow:
        return DCSServerBotOptionsFlow()


class DCSServerBotOptionsFlow(config_entries.OptionsFlowWithReload):
    """Control polling and dangerous actions separately from credentials."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_MODERATION_URL] = _normalise_url(
                user_input.get(CONF_MODERATION_URL, "")
            )
            if user_input.get(CONF_ENABLE_MODERATION):
                parsed = urlparse(user_input[CONF_MODERATION_URL])
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    errors[CONF_MODERATION_URL] = "invalid_url"
                else:
                    entry = self.config_entry
                    session = async_get_clientsession(
                        self.hass,
                        verify_ssl=entry.data.get(
                            CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                        ),
                    )
                    client = DCSServerBotClient(
                        session,
                        entry.data[CONF_URL],
                        entry.data.get(CONF_API_KEY, ""),
                        verify_ssl=entry.data.get(
                            CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                        ),
                        moderation_url=user_input[CONF_MODERATION_URL],
                    )
                    try:
                        if not await client.async_check_moderation():
                            errors[CONF_MODERATION_URL] = "invalid_response"
                    except DCSServerBotAuthenticationError:
                        errors[CONF_MODERATION_URL] = "invalid_auth"
                    except DCSServerBotError:
                        errors[CONF_MODERATION_URL] = "cannot_connect"
            if not errors:
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_CONTROL,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_CONTROL, DEFAULT_ENABLE_CONTROL
                        ),
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_MODERATION,
                        default=(user_input or self.config_entry.options).get(
                            CONF_ENABLE_MODERATION, DEFAULT_ENABLE_MODERATION
                        ),
                    ): bool,
                    vol.Required(
                        CONF_MODERATION_URL,
                        default=(user_input or self.config_entry.options).get(
                            CONF_MODERATION_URL, DEFAULT_MODERATION_URL
                        ),
                    ): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=(user_input or self.config_entry.options).get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
            errors=errors,
        )
