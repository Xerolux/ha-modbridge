"""Binary sensor platform: ModBridge connectivity."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ModBridgeDataUpdateCoordinator
from .entity import ModBridgeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ModBridge connectivity binary sensor."""
    coordinator: ModBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([ModBridgeConnectivitySensor(coordinator)])


class ModBridgeConnectivitySensor(ModBridgeEntity, BinarySensorEntity):
    """Reports whether the ModBridge server is reachable and authenticated."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connectivity"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_connectivity"

    @property
    def is_on(self) -> bool:
        """Return True when the last update succeeded."""
        return self.coordinator.last_update_success

    @property
    def available(self) -> bool:
        """Always available so it can report the offline state."""
        return True
