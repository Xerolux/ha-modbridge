"""Shared entity classes for the ModBridge integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModBridgeDataUpdateCoordinator


class ModBridgeEntity(CoordinatorEntity[ModBridgeDataUpdateCoordinator]):
    """Base entity for entities on the ModBridge server device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the server entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.server_device_info()


class ModBridgeProxyEntity(CoordinatorEntity[ModBridgeDataUpdateCoordinator]):
    """Base entity for entities bound to a single ModBridge proxy."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ModBridgeDataUpdateCoordinator,
        proxy_id: str,
    ) -> None:
        """Initialize the proxy entity."""
        super().__init__(coordinator)
        self.proxy_id = proxy_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.entry.entry_id}_{proxy_id}")},
            name=self.proxy_name or f"Proxy {proxy_id[:8]}",
            manufacturer="Xerolux",
            model="Modbus TCP Proxy",
            via_device=(DOMAIN, coordinator.entry.entry_id),
        )

    @property
    def proxy(self) -> dict[str, Any] | None:
        """Return the current proxy data."""
        return self.coordinator.get_proxy(self.proxy_id)

    @property
    def proxy_name(self) -> str | None:
        """Return the configured proxy name."""
        if (proxy := self.proxy) is not None:
            return str(proxy.get("name") or "") or None
        return None

    @property
    def available(self) -> bool:
        """Return availability: coordinator healthy and proxy present."""
        return self.coordinator.last_update_success and self.proxy is not None
