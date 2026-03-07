"""Conversation implementation for ha_openai."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

from .const import (
    CONF_AGENT_ID,
    CONF_MAX_HISTORY_MESSAGES,
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_MAX_HISTORY_MESSAGES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
    LOGGER,
    STATE_ERROR,
    STATE_PROCESSING,
    STATE_READY,
)

class HAOpenAIConversationEntity(conversation.ConversationEntity, conversation.AbstractConversationAgent):
    """OpenAI conversation entity."""

    _attr_has_entity_name = True
    _attr_name = "Conversation"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, hass: HomeAssistant) -> None:
        """Initialize the conversation entity."""
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        self.conversation_id = None
        self._attr_unique_id = f"{entry.entry_id}_conversation"
        self._attr_native_value = STATE_READY
        self._conversation_history = []
        self._last_user_message = ""
        self._last_ai_response = ""
        self._timestamp = datetime.now().isoformat()
        
        # Load config from entry
        self.options = entry.options
        self.agent_id = self.options.get(CONF_AGENT_ID)
        self.max_history_messages = self.options.get(CONF_MAX_HISTORY_MESSAGES, DEFAULT_MAX_HISTORY_MESSAGES)
        self.temperature = self.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        self.max_tokens = self.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        self.top_p = self.options.get(CONF_TOP_P, DEFAULT_TOP_P)

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return ["en", "zh-Hans"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "last_message": self._last_user_message,
            "last_response": self._last_ai_response,
            "agent_id": self.agent_id,
            "timestamp": self._timestamp,
            "conversation_id": self.conversation_id,
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_write_ha_state()
        # Register self as a conversation agent
        conversation.async_set_agent(self.hass, self.entry_id, self)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        # Unregister self as a conversation agent
        conversation.async_unset_agent(self.hass, self.entry_id)

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        if not user_input.text.strip():
            return conversation.ConversationResult(
                response=conversation.ConversationResponse(
                    speech={"plain": "Please provide a message."},
                    response_type="error",
                ),
                conversation_id=user_input.conversation_id,
            )

        # Create a new conversation ID if none exists
        conversation_id = user_input.conversation_id
        if conversation_id is None:
            conversation_id = ulid.ulid()
            self.conversation_id = conversation_id
        
        try:
            self._attr_native_value = STATE_PROCESSING
            self._last_user_message = user_input.text
            self._timestamp = datetime.now().isoformat()
            self.async_write_ha_state()
            
            # Add the user message to conversation history
            self._conversation_history.append({
                "role": "user",
                "content": user_input.text,
                "timestamp": self._timestamp,
            })
            
            # Limit the conversation history
            if len(self._conversation_history) > self.max_history_messages:
                self._conversation_history = self._conversation_history[-self.max_history_messages:]
            
            # Process the conversation with Home Assistant's conversation agent
            result = await conversation.async_converse(
                self.hass,
                user_input.text,
                conversation_id=conversation_id,
                context=user_input.context,
                agent_id=self.agent_id,
            )
            
            # Store the response
            self._last_ai_response = result.response.speech.get("plain", "")
            
            # Add the assistant response to conversation history
            self._conversation_history.append({
                "role": "assistant",
                "content": self._last_ai_response,
                "timestamp": datetime.now().isoformat(),
            })
            
            self._attr_native_value = STATE_READY
            self.async_write_ha_state()
            
            return result
            
        except Exception as e:
            LOGGER.error("Error processing conversation: %s", str(e))
            self._attr_native_value = STATE_ERROR
            self._last_ai_response = f"Error: {str(e)}"
            self.async_write_ha_state()
            
            return conversation.ConversationResult(
                response=conversation.ConversationResponse(
                    speech={"plain": f"Error: {str(e)}"},
                    response_type="error",
                ),
                conversation_id=conversation_id,
            )

    async def async_set_native_value(self, value: str) -> None:
        """Set the native value - this allows using it as a service."""
        if not value or not isinstance(value, str):
            return
        
        self._attr_native_value = STATE_PROCESSING
        self._last_user_message = value
        self._timestamp = datetime.now().isoformat()
        self.async_write_ha_state()
        
        try:
            # Create conversation input
            user_input = conversation.ConversationInput(
                text=value,
                conversation_id=self.conversation_id,
            )
            
            # Process the conversation
            result = await self.async_process(user_input)
            
            # Update state
            self._attr_native_value = STATE_READY
            self._last_ai_response = result.response.speech.get("plain", "")
            self.async_write_ha_state()
            
        except Exception as e:
            LOGGER.error("Error setting native value: %s", str(e))
            self._attr_native_value = STATE_ERROR
            self._last_ai_response = f"Error: {str(e)}"
            self.async_write_ha_state()

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenAI Conversation platform."""
    entity = HAOpenAIConversationEntity(config_entry, hass)
    async_add_entities([entity])
    
    # Register the conversation agent
    conversation.async_set_agent(hass, config_entry.entry_id, entity)
    
    # Register a cleanup function
    config_entry.async_on_unload(
        lambda: conversation.async_unset_agent(hass, config_entry.entry_id)
    ) 