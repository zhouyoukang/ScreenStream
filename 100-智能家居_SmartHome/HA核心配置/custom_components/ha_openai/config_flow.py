"""Config flow for HomeAssistant OpenAI API integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import conversation
import homeassistant.helpers.config_validation as cv
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN, 
    DEFAULT_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    CONF_STREAM_RESPONSES,
    CONF_RATE_LIMIT,
    DEFAULT_STREAM_RESPONSES,
    DEFAULT_RATE_LIMIT,
    CONF_AGENT_ID,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    CONF_REQUEST_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    CONF_MAX_RETRIES,
    DEFAULT_MAX_RETRIES,
    CONF_RETRY_DELAY,
    DEFAULT_RETRY_DELAY,
    CONF_MAX_HISTORY_MESSAGES,
    DEFAULT_MAX_HISTORY_MESSAGES,
    CONF_TEMPERATURE,
    DEFAULT_TEMPERATURE,
    CONF_MAX_TOKENS,
    DEFAULT_MAX_TOKENS,
    CONF_TOP_P,
    DEFAULT_TOP_P,
    LOGGER,
)

class HAOpenAIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomeAssistant OpenAI API integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        # Get available conversation agents
        agents = []
        try:
            agent_info = self.hass.components.conversation.async_get_agent_info()
            for agent_id, info in agent_info.items():
                agents.append({
                    "id": agent_id,
                    "name": info.get("name", agent_id)
                })
        except Exception as e:
            LOGGER.error("Failed to get conversation agents: %s", str(e))
            agents = []

        agent_options = {agent["id"]: f"{agent['name']} ({agent['id']})" for agent in agents}

        if user_input is not None:
            # Validate the input
            try:
                # Check port availability
                port = user_input.get(CONF_PORT, DEFAULT_PORT)
                
                # Create entry
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                        CONF_HOST: user_input.get(CONF_HOST, DEFAULT_HOST),
                        CONF_PORT: port,
                        CONF_AGENT_ID: user_input.get(CONF_AGENT_ID),
                    },
                    options={
                        CONF_STREAM_RESPONSES: user_input.get(CONF_STREAM_RESPONSES, DEFAULT_STREAM_RESPONSES),
                        CONF_RATE_LIMIT: user_input.get(CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT),
                        CONF_REQUEST_TIMEOUT: user_input.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
                        CONF_MAX_RETRIES: user_input.get(CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES),
                        CONF_RETRY_DELAY: user_input.get(CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY),
                        CONF_MAX_HISTORY_MESSAGES: user_input.get(CONF_MAX_HISTORY_MESSAGES, DEFAULT_MAX_HISTORY_MESSAGES),
                        CONF_TEMPERATURE: user_input.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                        CONF_MAX_TOKENS: user_input.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                        CONF_TOP_P: user_input.get(CONF_TOP_P, DEFAULT_TOP_P),
                    },
                )
            except Exception as ex:
                LOGGER.error("Error setting up integration: %s", str(ex))
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_AGENT_ID): vol.In(agent_options) if agent_options else str,
                vol.Optional(CONF_STREAM_RESPONSES, default=DEFAULT_STREAM_RESPONSES): cv.boolean,
                vol.Optional(CONF_RATE_LIMIT, default=DEFAULT_RATE_LIMIT): cv.positive_int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return HAOpenAIOptionsFlow(config_entry)


class HAOpenAIOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for HomeAssistant OpenAI API integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        
        # Get available conversation agents
        agents = []
        try:
            agent_info = self.hass.components.conversation.async_get_agent_info()
            for agent_id, info in agent_info.items():
                agents.append({
                    "id": agent_id,
                    "name": info.get("name", agent_id)
                })
        except Exception as e:
            LOGGER.error("Failed to get conversation agents: %s", str(e))
            agents = []

        agent_options = {agent["id"]: f"{agent['name']} ({agent['id']})" for agent in agents}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_AGENT_ID,
                    default=self.config_entry.data.get(CONF_AGENT_ID),
                ): vol.In(agent_options) if agent_options else str,
                vol.Optional(
                    CONF_STREAM_RESPONSES,
                    default=options.get(CONF_STREAM_RESPONSES, DEFAULT_STREAM_RESPONSES),
                ): cv.boolean,
                vol.Optional(
                    CONF_RATE_LIMIT, 
                    default=options.get(CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT)
                ): cv.positive_int,
                vol.Optional(
                    CONF_REQUEST_TIMEOUT,
                    default=options.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
                ): cv.positive_int,
                vol.Optional(
                    CONF_MAX_RETRIES,
                    default=options.get(CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES),
                ): cv.positive_int,
                vol.Optional(
                    CONF_RETRY_DELAY,
                    default=options.get(CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY),
                ): cv.positive_float,
                vol.Optional(
                    CONF_MAX_HISTORY_MESSAGES,
                    default=options.get(CONF_MAX_HISTORY_MESSAGES, DEFAULT_MAX_HISTORY_MESSAGES),
                ): cv.positive_int,
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                ): cv.positive_int,
                vol.Optional(
                    CONF_TOP_P,
                    default=options.get(CONF_TOP_P, DEFAULT_TOP_P),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema) 