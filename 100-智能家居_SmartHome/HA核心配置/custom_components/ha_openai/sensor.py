"""Sensor platform for ha_openai."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    LOGGER,
    STATE_READY,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ha_openai sensor platform."""
    name = entry.data.get("name", DEFAULT_NAME)
    
    # Get the API server instance
    server = hass.data[DOMAIN].get("server")
    if not server:
        LOGGER.error("Cannot find API server instance")
        return
    
    # Add the status entity
    LOGGER.info("Adding HAOpenAI sensor entities")
    entities = [HAOpenAIStatusSensor(hass, entry, name, server)]
    
    LOGGER.info("Created %d entities: %s", len(entities), [entity._attr_name for entity in entities])
    
    # Register with meaningful entity IDs
    for entity in entities:
        entity._attr_has_entity_name = True
        entity.entity_id = f"sensor.{DOMAIN}_{entity._attr_name.lower().replace(' ', '_')}"
        LOGGER.info("Registering entity: %s (ID: %s)", entity._attr_name, entity.entity_id)
    
    async_add_entities(entities)

class HAOpenAIStatusSensor(SensorEntity):
    """Sensor for monitoring ha_openai status."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    
    def __init__(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry, 
        name: str,
        server: Any,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.entry = entry
        self.server = server
        
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_icon = "mdi:api"
        self._attr_native_value = STATE_READY
        self._attr_available = True
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
            manufacturer="Home Assistant Community",
            model="OpenAI API",
            sw_version=server.api_version,
        )
        
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_schedule_update_ha_state(True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "host": self.server.host,
            "port": self.server.port,
            "stream_responses": self.server.stream_responses,
            "rate_limit": self.server.rate_limit,
            "agent_id": self.server.agent_id,
            "ssl_enabled": self.server.ssl_context is not None,
            "uptime": dt_util.utcnow().timestamp() - getattr(self.server, "start_time", dt_util.utcnow()).timestamp(),
            "api_version": self.server.api_version,
        } 