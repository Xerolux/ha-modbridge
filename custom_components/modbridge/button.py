"""Button platform: restart actions for ModBridge."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ModBridgeApiError
from .const import DOMAIN
from .coordinator import ModBridgeDataUpdateCoordinator
from .entity import ModBridgeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ModBridge buttons."""
    coordinator: ModBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities(
        [
            ModBridgeRestartButton(coordinator),
            ModBridgeRestartAllProxiesButton(coordinator),
        ]
    )


class ModBridgeRestartButton(ModBridgeEntity, ButtonEntity):
    """Restart the ModBridge server process."""

    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "restart_server"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_restart_server"

    async def async_press(self) -> None:
        """Send the restart command."""
        try:
            await self.coordinator.client.async_restart_system()
        except ModBridgeApiError as err:
            raise HomeAssistantError(f"ModBridge restart failed: {err}") from err


class ModBridgeRestartAllProxiesButton(ModBridgeEntity, ButtonEntity):
    """Restart all ModBridge proxies."""

    _attr_icon = "mdi:restart-alert"
    _attr_translation_key = "restart_all_proxies"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_restart_all_proxies"

    async def async_press(self) -> None:
        """Send the restart-all command."""
        try:
            await self.coordinator.client.async_control_all("restart_all")
        except ModBridgeApiError as err:
            raise HomeAssistantError(f"ModBridge action failed: {err}") from err
        await self.coordinator.async_request_refresh()
