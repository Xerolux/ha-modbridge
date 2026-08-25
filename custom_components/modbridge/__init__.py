"""The ModBridge integration for Home Assistant.

Connects to a running ModBridge server (https://github.com/Xerolux/modbridge)
and exposes its Modbus proxies as switches, sensors, buttons and services.
"""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ModBridgeApiError, ModBridgeClient
from .const import (
    CONF_USE_TLS,
    CONF_VERIFY_SSL,
    DOMAIN,
    SERVICE_PAUSE_PROXY,
    SERVICE_RESTART_ALL,
    SERVICE_RESTART_PROXY,
    SERVICE_RESTART_SYSTEM,
    SERVICE_RESUME_PROXY,
    SERVICE_START_ALL,
    SERVICE_START_PROXY,
    SERVICE_STOP_ALL,
    SERVICE_STOP_PROXY,
)
from .coordinator import ModBridgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "button", "sensor", "switch"]

PROXY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Exclusive("proxy_id", "proxy_selection"): cv.string,
        vol.Exclusive("proxy_name", "proxy_selection"): cv.string,
        vol.Optional("config_entry_id"): cv.string,
    }
)

BULK_SERVICE_SCHEMA = vol.Schema({vol.Optional("config_entry_id"): cv.string})


def _select_entry(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Pick the config entry data a service call targets."""
    entry_id: str | None = call.data.get("config_entry_id")
    entries = hass.data[DOMAIN]

    if entry_id:
        if entry_id not in entries:
            raise ServiceValidationError(f"Unknown config entry: {entry_id}")
        return entries[entry_id]

    if len(entries) == 1:
        return next(iter(entries.values()))

    raise ServiceValidationError(
        "Multiple ModBridge servers configured; specify config_entry_id"
    )


def _resolve_proxy_id(
    coordinator: ModBridgeDataUpdateCoordinator, call: ServiceCall
) -> str:
    """Resolve the target proxy of a service call."""
    proxy_id: str | None = call.data.get("proxy_id")
    proxy_name: str | None = call.data.get("proxy_name")

    if not proxy_id and not proxy_name:
        raise ServiceValidationError("proxy_id or proxy_name is required")

    for proxy in coordinator.data.get("proxies", []):
        if proxy_id and proxy.get("id") == proxy_id:
            return proxy_id
        if (
            proxy_name
            and str(proxy.get("name", "")).casefold() == proxy_name.casefold()
        ):
            return str(proxy["id"])

    raise ServiceValidationError(f"Proxy not found: {proxy_id or proxy_name}")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the ModBridge integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ModBridge from a config entry."""
    client = ModBridgeClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        use_tls=entry.data.get(CONF_USE_TLS, False),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
    )

    coordinator = ModBridgeDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_platform_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_register_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()
        if not hass.data[DOMAIN]:
            _async_remove_services(hass)
    return unload_ok


def _async_remove_services(hass: HomeAssistant) -> None:
    """Remove integration-level services when the last entry is unloaded."""
    for service in (
        SERVICE_START_PROXY,
        SERVICE_STOP_PROXY,
        SERVICE_RESTART_PROXY,
        SERVICE_PAUSE_PROXY,
        SERVICE_RESUME_PROXY,
        SERVICE_START_ALL,
        SERVICE_STOP_ALL,
        SERVICE_RESTART_ALL,
        SERVICE_RESTART_SYSTEM,
    ):
        hass.services.async_remove(DOMAIN, service)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration-level services (idempotent)."""

    def _make_proxy_handler(action: str):
        async def _handler(call: ServiceCall) -> None:
            entry_data = _select_entry(hass, call)
            coordinator: ModBridgeDataUpdateCoordinator = entry_data["coordinator"]
            proxy_id = _resolve_proxy_id(coordinator, call)
            try:
                await entry_data["client"].async_control_proxy(proxy_id, action)
            except ModBridgeApiError as err:
                raise HomeAssistantError(f"ModBridge action failed: {err}") from err
            await coordinator.async_request_refresh()

        return _handler

    for action, service in (
        ("start", SERVICE_START_PROXY),
        ("stop", SERVICE_STOP_PROXY),
        ("restart", SERVICE_RESTART_PROXY),
        ("pause", SERVICE_PAUSE_PROXY),
        ("resume", SERVICE_RESUME_PROXY),
    ):
        hass.services.async_register(
            DOMAIN, service, _make_proxy_handler(action), schema=PROXY_SERVICE_SCHEMA
        )

    def _make_bulk_handler(action: str):
        async def _handler(call: ServiceCall) -> None:
            entry_data = _select_entry(hass, call)
            try:
                await entry_data["client"].async_control_all(action)
            except ModBridgeApiError as err:
                raise HomeAssistantError(f"ModBridge action failed: {err}") from err
            await entry_data["coordinator"].async_request_refresh()

        return _handler

    for action, service in (
        ("start_all", SERVICE_START_ALL),
        ("stop_all", SERVICE_STOP_ALL),
        ("restart_all", SERVICE_RESTART_ALL),
    ):
        hass.services.async_register(
            DOMAIN, service, _make_bulk_handler(action), schema=BULK_SERVICE_SCHEMA
        )

    async def _restart_system(call: ServiceCall) -> None:
        entry_data = _select_entry(hass, call)
        try:
            await entry_data["client"].async_restart_system()
        except ModBridgeApiError as err:
            raise HomeAssistantError(f"ModBridge restart failed: {err}") from err

    hass.services.async_register(
        DOMAIN, SERVICE_RESTART_SYSTEM, _restart_system, schema=BULK_SERVICE_SCHEMA
    )
