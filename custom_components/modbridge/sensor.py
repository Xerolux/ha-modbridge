"""Sensor platform: ModBridge server diagnostics and proxy statistics."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, STATUS_RUNNING
from .coordinator import ModBridgeDataUpdateCoordinator
from .entity import ModBridgeEntity, ModBridgeProxyEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ModBridge sensors."""
    coordinator: ModBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    server_sensors = [
        ModBridgeRunningProxiesSensor(coordinator),
        ModBridgeTotalProxiesSensor(coordinator),
        ModBridgeActiveConnectionsSensor(coordinator),
        ModBridgeRequestsSensor(coordinator),
        ModBridgeErrorsSensor(coordinator),
        ModBridgeUptimeSensor(coordinator),
        ModBridgeMemorySensor(coordinator),
    ]
    async_add_entities(server_sensors)

    known: set[str] = set()

    def _unique_id(proxy_id: str, kind: str) -> str:
        return f"{entry.entry_id}_{proxy_id}_{kind}"

    @callback
    def _sync_entities() -> None:
        current = set(coordinator.proxy_ids)

        new_entities: list[SensorEntity] = []
        for proxy_id in sorted(current - known):
            new_entities.extend(
                [
                    ModBridgeProxyStatusSensor(coordinator, proxy_id),
                    ModBridgeProxyRequestsSensor(coordinator, proxy_id),
                    ModBridgeProxyErrorsSensor(coordinator, proxy_id),
                    ModBridgeProxyConnectionsSensor(coordinator, proxy_id),
                    ModBridgeProxyLatencySensor(coordinator, proxy_id),
                    ModBridgeProxyUptimeSensor(coordinator, proxy_id),
                ]
            )
        if new_entities:
            known.update(e.proxy_id for e in new_entities)
            async_add_entities(new_entities)

        registry = er.async_get(hass)
        for proxy_id in known - current:
            known.discard(proxy_id)
            for kind in ("status", "requests", "errors", "connections", "latency", "uptime"):
                entity_id = registry.async_get_entity_id(
                    "sensor", DOMAIN, _unique_id(proxy_id, kind)
                )
                if entity_id:
                    registry.async_remove(entity_id)

    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))
    _sync_entities()


def _sum_proxies(coordinator: ModBridgeDataUpdateCoordinator, key: str) -> int:
    """Sum a numeric proxy stat over all proxies."""
    total = 0
    for proxy in coordinator.data.get("proxies", []):
        try:
            total += int(proxy.get(key) or 0)
        except (TypeError, ValueError):
            pass
    return total


class ModBridgeServerSensor(ModBridgeEntity, SensorEntity):
    """Base class for server-level diagnostic sensors."""

    _attr_entity_category = None


class ModBridgeRunningProxiesSensor(ModBridgeServerSensor):
    """Number of currently running proxies."""

    _attr_icon = "mdi:play-network"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "running_proxies"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_running_proxies"

    @property
    def native_value(self) -> StateType:
        """Return the number of running proxies."""
        return sum(
            1
            for p in self.coordinator.data.get("proxies", [])
            if p.get("status") == STATUS_RUNNING
        )


class ModBridgeTotalProxiesSensor(ModBridgeServerSensor):
    """Total number of configured proxies."""

    _attr_icon = "mdi:network"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "total_proxies"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_proxies"

    @property
    def native_value(self) -> StateType:
        """Return the number of configured proxies."""
        return len(self.coordinator.data.get("proxies", []))


class ModBridgeActiveConnectionsSensor(ModBridgeServerSensor):
    """Sum of active connections across all proxies."""

    _attr_icon = "mdi:connection"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "active_connections"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_connections"

    @property
    def native_value(self) -> StateType:
        """Return the number of active connections."""
        return _sum_proxies(self.coordinator, "active_connections")


class ModBridgeRequestsSensor(ModBridgeServerSensor):
    """Total requests processed across all proxies."""

    _attr_icon = "mdi:swap-horizontal"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_translation_key = "requests"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_requests"

    @property
    def native_value(self) -> StateType:
        """Return the total number of requests."""
        return _sum_proxies(self.coordinator, "requests")


class ModBridgeErrorsSensor(ModBridgeServerSensor):
    """Total errors across all proxies."""

    _attr_icon = "mdi:alert-circle"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_translation_key = "errors"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_errors"

    @property
    def native_value(self) -> StateType:
        """Return the total number of errors."""
        return _sum_proxies(self.coordinator, "errors")


class ModBridgeUptimeSensor(ModBridgeServerSensor):
    """ModBridge server uptime as a timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "uptime"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_uptime"

    @property
    def native_value(self) -> datetime | None:
        """Return the server start time."""
        info: dict[str, Any] = self.coordinator.data.get("system", {})
        uptime = info.get("uptime_seconds")
        if not isinstance(uptime, (int, float)) or uptime < 0:
            return None
        return datetime.now().replace(microsecond=0) - timedelta(seconds=int(uptime))


class ModBridgeMemorySensor(ModBridgeServerSensor):
    """Memory allocated by the ModBridge process."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfInformation.MEBIBYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "memory"

    def __init__(self, coordinator: ModBridgeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_memory"

    @property
    def native_value(self) -> StateType:
        """Return allocated memory in MiB."""
        info: dict[str, Any] = self.coordinator.data.get("system", {})
        memory = info.get("memory_alloc_mb")
        if isinstance(memory, (int, float)):
            return round(float(memory), 1)
        return None


class ModBridgeProxySensor(ModBridgeProxyEntity, SensorEntity):
    """Base class for per-proxy sensors."""


class ModBridgeProxyStatusSensor(ModBridgeProxySensor):
    """Status of a single proxy."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["Running", "Stopped", "Error"]
    _attr_translation_key = "proxy_status"

    STATUS_ICONS = {
        "Running": "mdi:lan-check",
        "Stopped": "mdi:lan-pending",
        "Error": "mdi:lan-disconnect",
    }

    def __init__(
        self, coordinator: ModBridgeDataUpdateCoordinator, proxy_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, proxy_id)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{proxy_id}_status"

    @property
    def native_value(self) -> str | None:
        """Return the proxy status."""
        if (proxy := self.proxy) is None:
            return None
        return proxy.get("status")

    @property
    def icon(self) -> str | None:
        """Return an icon matching the status."""
        if (proxy := self.proxy) is not None:
            return self.STATUS_ICONS.get(proxy.get("status", ""), "mdi:lan")
        return "mdi:lan"


class ModBridgeProxyCounterSensor(ModBridgeProxySensor):
    """Base class for per-proxy counter sensors."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _key: str = ""

    def __init__(
        self, coordinator: ModBridgeDataUpdateCoordinator, proxy_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, proxy_id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{proxy_id}_{self._key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return the counter value."""
        if (proxy := self.proxy) is None:
            return None
        try:
            return int(proxy.get(self._key) or 0)
        except (TypeError, ValueError):
            return None


class ModBridgeProxyRequestsSensor(ModBridgeProxyCounterSensor):
    """Requests processed by the proxy."""

    _key = "requests"
    _attr_icon = "mdi:swap-horizontal"
    _attr_translation_key = "requests"


class ModBridgeProxyErrorsSensor(ModBridgeProxyCounterSensor):
    """Errors of the proxy."""

    _key = "errors"
    _attr_icon = "mdi:alert-circle"
    _attr_translation_key = "errors"


class ModBridgeProxyConnectionsSensor(ModBridgeProxySensor):
    """Active connections of the proxy."""

    _attr_icon = "mdi:connection"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "active_connections"

    def __init__(
        self, coordinator: ModBridgeDataUpdateCoordinator, proxy_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, proxy_id)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{proxy_id}_connections"

    @property
    def native_value(self) -> StateType:
        """Return the number of active connections."""
        if (proxy := self.proxy) is None:
            return None
        try:
            return int(proxy.get("active_connections") or 0)
        except (TypeError, ValueError):
            return None


class ModBridgeProxyLatencySensor(ModBridgeProxySensor):
    """P95 latency of the proxy in milliseconds."""

    _attr_icon = "mdi:speedometer"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_suggested_display_precision = 1
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "latency"

    def __init__(
        self, coordinator: ModBridgeDataUpdateCoordinator, proxy_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, proxy_id)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{proxy_id}_latency"

    @property
    def native_value(self) -> StateType:
        """Return the mean latency."""
        if (proxy := self.proxy) is None:
            return None
        try:
            return round(float(proxy.get("latency_mean_ms") or 0), 2)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose additional latency percentiles."""
        if (proxy := self.proxy) is None:
            return {}
        return {
            "p50_ms": proxy.get("latency_p50_ms"),
            "p95_ms": proxy.get("latency_p95_ms"),
            "p99_ms": proxy.get("latency_p99_ms"),
        }


class ModBridgeProxyUptimeSensor(ModBridgeProxySensor):
    """Uptime of the proxy in seconds."""

    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "uptime"

    def __init__(
        self, coordinator: ModBridgeDataUpdateCoordinator, proxy_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, proxy_id)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{proxy_id}_uptime"

    @property
    def native_value(self) -> StateType:
        """Return the proxy uptime in seconds."""
        if (proxy := self.proxy) is None:
            return None
        try:
            return int(float(proxy.get("uptime_s") or 0))
        except (TypeError, ValueError):
            return None
