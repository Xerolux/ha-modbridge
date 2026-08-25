"""Switch platform: start/stop ModBridge proxies."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ModBridgeApiError
from .const import DOMAIN, STATUS_RUNNING
from .coordinator import ModBridgeDataUpdateCoordinator
from .entity import ModBridgeProxyEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ModBridge proxy switches, dynamically following proxies."""
    coordinator: ModBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    known: set[str] = set()

    def _unique_id(proxy_id: str) -> str:
        return f"{entry.entry_id}_{proxy_id}_switch"

    @callback
    def _sync_entities() -> None:
        current = set(coordinator.proxy_ids)

        new_entities = [
            ModBridgeProxySwitch(coordinator, proxy_id)
            for proxy_id in sorted(current - known)
        ]
        if new_entities:
            known.update(e.proxy_id for e in new_entities)
            async_add_entities(new_entities)

        # Remove switches for proxies that no longer exist.
        registry = er.async_get(hass)
        for proxy_id in known - current:
            known.discard(proxy_id)
            entity_id = registry.async_get_entity_id(
                "switch", DOMAIN, _unique_id(proxy_id)
            )
            if entity_id:
                registry.async_remove(entity_id)

    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))
    _sync_entities()


class ModBridgeProxySwitch(ModBridgeProxyEntity):
    """Switch to start/stop a single ModBridge proxy."""

    _attr_icon = "mdi:lan"

    def __init__(
        self,
        coordinator: ModBridgeDataUpdateCoordinator,
        proxy_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, proxy_id)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{proxy_id}_switch"
        self._attr_name = "Proxy"

    @property
    def is_on(self) -> bool | None:
        """Return True while the proxy is running."""
        if (proxy := self.proxy) is None:
            return None
        return proxy.get("status") == STATUS_RUNNING

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose proxy configuration details."""
        if (proxy := self.proxy) is None:
            return {}
        return {
            key: proxy.get(key)
            for key in (
                "id",
                "name",
                "listen_addr",
                "target_addr",
                "protocol",
                "paused",
                "enabled",
                "description",
            )
            if key in proxy
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Start (or resume) the proxy."""
        await self._async_control("resume" if self._is_paused else "start")

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the proxy."""
        await self._async_control("stop")

    @property
    def _is_paused(self) -> bool:
        """Return whether the proxy is paused."""
        if (proxy := self.proxy) is None:
            return False
        return bool(proxy.get("paused"))

    async def _async_control(self, action: str) -> None:
        """Send a control action to ModBridge."""
        client = self.coordinator.client
        try:
            await client.async_control_proxy(self.proxy_id, action)
        except ModBridgeApiError as err:
            raise HomeAssistantError(f"ModBridge action failed: {err}") from err
        await self.coordinator.async_request_refresh()
