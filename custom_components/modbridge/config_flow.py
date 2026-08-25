"""Config flow for ModBridge."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .api import (
    ModBridgeApiError,
    ModBridgeAuthError,
    ModBridgeClient,
    ModBridgeConnectionError,
    ModBridgePasswordChangeRequiredError,
)
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_USE_TLS,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_USE_TLS, default=False): bool,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the connection settings by logging in and reading status."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    client = ModBridgeClient(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        use_tls=data[CONF_USE_TLS],
        verify_ssl=data[CONF_VERIFY_SSL],
    )
    errors: dict[str, str] = {}
    try:
        await client.login()
        # Probe an authenticated endpoint so we also detect accounts that
        # still require a password change or lack permissions.
        await client.async_get_proxies()
    except ModBridgePasswordChangeRequiredError:
        errors["base"] = "password_change_required"
    except ModBridgeAuthError:
        errors["base"] = "invalid_auth"
    except ModBridgeConnectionError:
        errors["base"] = "cannot_connect"
    except ModBridgeApiError as err:
        _LOGGER.debug("ModBridge validation error: %s", err)
        errors["base"] = "cannot_connect"
    finally:
        await client.close()
    return errors


class ModBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the ModBridge config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate_connection(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ModBridge {user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Start the reauth flow after an auth failure."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for new credentials."""
        errors: dict[str, str] = {}
        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_failed")

        if user_input is not None:
            data = {**self._reauth_entry.data, **user_input}
            errors = await _validate_connection(self.hass, data)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._reauth_entry, data=data
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                "host": self._reauth_entry.data.get(CONF_HOST, ""),
                "port": str(self._reauth_entry.data.get(CONF_PORT, DEFAULT_PORT)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ModBridgeOptionsFlow:
        """Create the options flow handler."""
        return ModBridgeOptionsFlow(config_entry)


class ModBridgeOptionsFlow(config_entries.OptionsFlow):
    """Handle ModBridge options (poll interval)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current,
                    description={
                        "suggested_value": current,
                        "value_min": MIN_SCAN_INTERVAL,
                        "value_max": MAX_SCAN_INTERVAL,
                    },
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
