"""Constants for the HomeAssistant OpenAI API integration."""
import logging
from homeassistant.const import Platform

LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_openai"
RATE_LIMIT_STORAGE = "rate_limiter"

# Default configuration values
DEFAULT_NAME = "HomeAssistant OpenAI API"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8337
DEFAULT_STREAM_RESPONSES = True
DEFAULT_RATE_LIMIT = 60
DEFAULT_SSL_CERTIFICATE = None
DEFAULT_SSL_KEY = None
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_LOG_LEVEL = "info"

# OpenAI API default values
OPENAI_API_VERSION = "1.0.0"
DEFAULT_MODEL = "homeassistant-ai"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TOP_P = 1.0
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_MAX_HISTORY_MESSAGES = 10
DEFAULT_MAX_TOOL_ITERATIONS = 5

# Configuration keys
CONF_STREAM_RESPONSES = "stream_responses"
CONF_RATE_LIMIT = "rate_limit"
CONF_AGENT_ID = "agent_id"
CONF_SSL_CERTIFICATE = "ssl_certificate"
CONF_SSL_KEY = "ssl_key"
CONF_REQUEST_TIMEOUT = "request_timeout"
CONF_MAX_RETRIES = "max_retries"
CONF_RETRY_DELAY = "retry_delay"
CONF_MAX_HISTORY_MESSAGES = "max_history_messages"
CONF_MAX_TOOL_ITERATIONS = "max_tool_iterations"
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_TOP_P = "top_p"
CONF_FREQUENCY_PENALTY = "frequency_penalty"
CONF_PRESENCE_PENALTY = "presence_penalty"
CONF_STOP_SEQUENCES = "stop_sequences"
CONF_MODEL = "model"
CONF_WEB_SEARCH = "web_search"
CONF_FILTER_MARKDOWN = "filter_markdown"

# Entity states
STATE_READY = "Ready"
STATE_PROCESSING = "Processing"
STATE_ERROR = "Error"

# API endpoints
API_URL_CHAT_COMPLETIONS = "/v1/chat/completions"
API_URL_ROOT = "/"
API_URL_MODELS = "/v1/models"
API_URL_HEALTH = "/health"
API_URL_DOCS = "/v1/docs"
API_URL_DOCUMENTATION = "/v1/documentation"
API_URL_TEST = "/v1/test"
API_URL_UI = "/v1/ui"
API_URL_WEB = "/v1/web"
API_URL_INTERFACE = "/v1/interface"
API_URL_STATUS = "/v1/status"

# Rate limiting
RATE_LIMIT_WINDOW = 60  # 1-minute window

# Platform definitions
PLATFORMS = [Platform.CONVERSATION, Platform.SENSOR]

# Error messages
ERROR_INVALID_AUTH = "Invalid API key or token"
ERROR_TOO_MANY_REQUESTS = "Too many requests, please try again later"
ERROR_SERVER_ERROR = "Server error, please try again later"
ERROR_TIMEOUT = "Request timed out, please try again later"
ERROR_UNKNOWN = "Unknown error"

# Documentation URLs
DOCS_URL = "https://github.com/zhouyoukang/MIGPT-easy/wiki"
OPENAI_API_DOCS_URL = "https://platform.openai.com/docs/api-reference"
HOMEASSISTANT_DOCS_URL = "https://www.home-assistant.io/integrations/conversation/"

# 日志级别选项
LOG_LEVELS = ["debug", "info", "warning", "error", "critical"] 