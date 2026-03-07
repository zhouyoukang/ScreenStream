"""Home Assistant工具管理器常量."""

DOMAIN = "ha_tools_manager"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000
TOOLS_API_URL = "{host}:{port}/api"

ATTR_SCRIPT_PATH = "script_path"
ATTR_PARAMS = "params"
ATTR_TASK_ID = "task_id"

SERVICE_RUN_SCRIPT = "run_script"
SERVICE_RESTART_HA = "restart_ha" 