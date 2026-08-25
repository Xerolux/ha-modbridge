"""Data update coordinator for ModBridge."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ModBridgeApiError,
    ModBridgeAuthError,
    ModBridgeClient,
    ModBridgeConnectionError,
)
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

VERSION_CHECK_INTERVAL = 3600  # seconds between /api/update/check calls


class ModBridgeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate ModBridge data (proxies + server info)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ModBridgeClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.entry = entry
        self.server_version: str | None = None
        self._last_version_check = 0.0

        interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
            update_interval=timedelta(seconds=interval),
        )

    @property
    def proxy_ids(self) -> list[str]:
        """Return the IDs of all known proxies."""
        return [p.get("id") for p in self.data.get("proxies", []) if p.get("id")]

    def get_proxy(self, proxy_id: str) -> dict[str, Any] | None:
        """Return a single proxy by ID."""
        for proxy in self.data.get("proxies", []):
            if proxy.get("id") == proxy_id:
                return proxy
        return None

    def server_device_info(self) -> dict[str, Any]:
        """Return device info for the ModBridge server device."""
        from homeassistant.helpers.device_registry import DeviceInfo

        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="ModBridge",
            manufacturer="Xerolux",
            model="Modbus TCP Proxy Manager",
            sw_version=self.server_version or self.entry.version,
            configuration_url=self.client.base_url,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest state from ModBridge."""
        try:
            proxies = await self.client.async_get_proxies()
        except ModBridgeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (ModBridgeConnectionError, ModBridgeApiError) as err:
            raise UpdateFailed(str(err)) from err

        data: dict[str, Any] = {"proxies": proxies}

        # Server info is less critical; failures fall back to empty data.
        try:
            data["system"] = await self.client.async_get_system_info()
        except ModBridgeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (ModBridgeConnectionError, ModBridgeApiError) as err:
            _LOGGER.debug("System info unavailable: %s", err)
            data["system"] = {}

        # The version endpoint contacts GitHub and may fail; check it only
        # occasionally and cache the result.
        if time.monotonic() - self._last_version_check > VERSION_CHECK_INTERVAL:
            self._last_version_check = time.monotonic()
            version = await self.client.async_get_version()
            if version:
                self.server_version = version
                _LOGGER.debug("ModBridge server version: %s", version)

        return data
