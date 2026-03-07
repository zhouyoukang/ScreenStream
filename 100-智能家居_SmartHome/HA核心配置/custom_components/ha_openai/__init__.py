"""
HomeAssistant OpenAI Compatible API Integration.

This integration provides an OpenAI-compatible API endpoint for HomeAssistant,
allowing you to use HomeAssistant's conversation agents with any client that
supports the OpenAI API format.
"""
import logging
import os
import voluptuous as vol
from aiohttp import web
import homeassistant.helpers.config_validation as cv
from homeassistant.components import http, conversation
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_API_KEY,
    CONF_NAME,
    Platform,
)
import homeassistant.helpers.entity_registry as er
from homeassistant.exceptions import HomeAssistantError
import time

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
    DEFAULT_SSL_CERTIFICATE,
    DEFAULT_SSL_KEY,
    CONF_REQUEST_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    CONF_MAX_RETRIES,
    DEFAULT_MAX_RETRIES,
    CONF_RETRY_DELAY,
    DEFAULT_RETRY_DELAY,
    RATE_LIMIT_STORAGE,
    DEFAULT_LOG_LEVEL,
    PLATFORMS,
    LOGGER,
)

from .api_server import HAOpenAIServer
from .rate_limiter import RateLimiter

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_STREAM_RESPONSES, default=DEFAULT_STREAM_RESPONSES): cv.boolean,
                vol.Optional(CONF_RATE_LIMIT, default=DEFAULT_RATE_LIMIT): cv.positive_int,
                vol.Optional(CONF_AGENT_ID): cv.string,
                vol.Optional(CONF_SSL_CERTIFICATE): cv.isfile,
                vol.Optional(CONF_SSL_KEY): cv.isfile,
                vol.Optional(CONF_REQUEST_TIMEOUT, default=DEFAULT_REQUEST_TIMEOUT): cv.positive_int,
                vol.Optional(CONF_MAX_RETRIES, default=DEFAULT_MAX_RETRIES): cv.positive_int,
                vol.Optional(CONF_RETRY_DELAY, default=DEFAULT_RETRY_DELAY): cv.positive_float,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomeAssistant OpenAI API component."""
    if DOMAIN in config:
        conf = config[DOMAIN]
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["yaml_config"] = conf
        
        # Set up default logging level
        _setup_logger(DEFAULT_LOG_LEVEL)

    return True

def _setup_logger(log_level: str) -> None:
    """Set up logging level."""
    log_levels = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    
    level = log_levels.get(log_level.lower(), logging.INFO)
    # Only set level for our own logger, not the root logger
    LOGGER.setLevel(level)
    LOGGER.info("Setting %s logging level to %s", DOMAIN, log_level)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Merge config entry data and options
    config = {**entry.data, **entry.options}
    
    # Set up default logging level
    _setup_logger(DEFAULT_LOG_LEVEL)
    
    name = config.get(CONF_NAME, DEFAULT_NAME)
    host = config.get(CONF_HOST, DEFAULT_HOST)
    port = config.get(CONF_PORT, DEFAULT_PORT)
    stream_responses = config.get(CONF_STREAM_RESPONSES, DEFAULT_STREAM_RESPONSES)
    rate_limit = config.get(CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT)
    agent_id = config.get(CONF_AGENT_ID)
    ssl_certificate = config.get(CONF_SSL_CERTIFICATE, DEFAULT_SSL_CERTIFICATE)
    ssl_key = config.get(CONF_SSL_KEY, DEFAULT_SSL_KEY)
    request_timeout = config.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
    max_retries = config.get(CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES)
    retry_delay = config.get(CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY)

    # Check SSL configuration
    ssl_context = None
    if ssl_certificate and ssl_key:
        try:
            import ssl
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(ssl_certificate, ssl_key)
            LOGGER.info("SSL certificate loaded, HTTPS enabled")
        except Exception as e:
            LOGGER.error("Failed to load SSL certificate: %s", str(e))
            return False

    # Initialize rate limiter
    rate_limiter = RateLimiter(rate_limit)
    hass.data[DOMAIN][RATE_LIMIT_STORAGE] = rate_limiter

    try:
        # Check if conversation component is available
        if not hass.components.conversation.async_get_agent_info():
            LOGGER.warning("No valid conversation agents found, integration may not work properly")
    except Exception as e:
        LOGGER.warning("Error checking conversation agents: %s", str(e))

    # Create API server
    try:
        server = HAOpenAIServer(
            hass, 
            name, 
            host, 
            port, 
            stream_responses, 
            rate_limit, 
            agent_id,
            ssl_context,
            request_timeout,
            max_retries,
            retry_delay,
            rate_limiter
        )
        
        # Register API endpoint
        hass.http.register_view(server)
        
        # Store server instance
        hass.data[DOMAIN]["server"] = server
        hass.data[DOMAIN]["config_entry"] = entry
        
        LOGGER.info(
            "HomeAssistant OpenAI API server initialized, address: %s:%s",
            host, port
        )
        
        if ssl_context:
            LOGGER.info("HTTPS enabled using provided SSL certificate")
        
        # Register services
        register_services(hass)
        
        # Set up entity platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        return True
    except Exception as e:
        LOGGER.error("Failed to initialize API server: %s", str(e))
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if not unload_ok:
        return False
    
    # Clean up resources
    if DOMAIN in hass.data and "server" in hass.data[DOMAIN]:
        server = hass.data[DOMAIN]["server"]
        if hasattr(server, "cleanup") and callable(server.cleanup):
            await server.cleanup()
    
    # Remove data
    if DOMAIN in hass.data:
        # Keep yaml_config for reloading
        yaml_config = hass.data[DOMAIN].get("yaml_config")
        hass.data[DOMAIN] = {"yaml_config": yaml_config} if yaml_config else {}
    
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

def register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    
    @callback
    async def restart_service(call: ServiceCall) -> None:
        """Restart API server."""
        if DOMAIN not in hass.data or "server" not in hass.data[DOMAIN]:
            LOGGER.error("Cannot restart API server: server not initialized")
            return
            
        config_entry = hass.data[DOMAIN].get("config_entry")
        if not config_entry:
            LOGGER.error("Cannot restart API server: config entry not found")
            return
            
        LOGGER.info("Restarting API server...")
        await async_reload_entry(hass, config_entry)
        LOGGER.info("API server restarted")
    
    @callback
    async def clear_rate_limits_service(call: ServiceCall) -> None:
        """Clear rate limits."""
        if DOMAIN not in hass.data or RATE_LIMIT_STORAGE not in hass.data[DOMAIN]:
            LOGGER.error("Cannot clear rate limits: rate limiter not initialized")
            return
            
        rate_limiter = hass.data[DOMAIN][RATE_LIMIT_STORAGE]
        client_id = call.data.get("client_id")
        
        if client_id:
            rate_limiter.reset(client_id)
            LOGGER.info("Cleared rate limits for client %s", client_id)
        else:
            rate_limiter.reset()
            LOGGER.info("Cleared rate limits for all clients")
    
    @callback
    async def test_api_service(call: ServiceCall) -> None:
        """Test API functionality."""
        if DOMAIN not in hass.data or "server" not in hass.data[DOMAIN]:
            LOGGER.error("Cannot test API: server not initialized")
            return
            
        server = hass.data[DOMAIN]["server"]
        message = call.data.get("message")
        agent_id = call.data.get("agent_id", server.agent_id)
        
        if not message:
            LOGGER.error("Cannot test API: message cannot be empty")
            return
            
        try:
            # Send to HomeAssistant conversation agent
            result = await conversation.async_converse(
                hass,
                message,
                conversation_id=None,
                agent_id=agent_id,
                context=None,
            )
            
            # Log the result
            LOGGER.info("API test successful - Message: %s, Response: %s", message, result.response)
            
            # Notify the user
            hass.components.persistent_notification.async_create(
                f"**Test Message**: {message}\n\n**Response**: {result.response}\n\n**Agent**: {result.agent_id or agent_id}",
                title="HomeAssistant OpenAI API Test Result",
                notification_id=f"{DOMAIN}_test_{int(time.time())}",
            )
            
        except Exception as e:
            LOGGER.error("API test failed: %s", str(e))
            
            # Notify the user
            hass.components.persistent_notification.async_create(
                f"**Test Message**: {message}\n\n**Error**: {str(e)}",
                title="HomeAssistant OpenAI API Test Failed",
                notification_id=f"{DOMAIN}_test_error_{int(time.time())}",
            )
    
    # Register services
    hass.services.async_register(DOMAIN, "restart", restart_service)
    hass.services.async_register(DOMAIN, "clear_rate_limits", clear_rate_limits_service)
    hass.services.async_register(DOMAIN, "test_api", test_api_service) 