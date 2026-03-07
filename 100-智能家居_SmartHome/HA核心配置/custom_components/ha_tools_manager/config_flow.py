"""Config flow for 工具库管理器."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

class HAToolsManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """处理配置流程."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """处理用户配置."""
        errors = {}

        if user_input is not None:
            host = user_input.get(CONF_HOST, DEFAULT_HOST)
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            
            # 检查是否已经配置
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            
            # 尝试连接到API服务器
            try:
                # TODO: 添加实际连接测试
                return self.async_create_entry(
                    title=f"工具库管理器 {host}:{port}",
                    data=user_input,
                )
            except Exception as ex:
                _LOGGER.error("无法连接到工具API: %s", ex)
                errors["base"] = "cannot_connect"

        # 显示表单
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                }
            ),
            errors=errors,
        ) 