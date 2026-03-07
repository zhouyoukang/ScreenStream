"""工具库管理服务组件."""
import logging
import json
import voluptuous as vol
import requests
from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)

from .const import (
    DOMAIN,
    ATTR_SCRIPT_PATH,
    ATTR_PARAMS,
    ATTR_TASK_ID,
    SERVICE_RUN_SCRIPT,
    SERVICE_RESTART_HA,
)

_LOGGER = logging.getLogger(__name__)

# 服务调用架构
SERVICE_RUN_SCRIPT_SCHEMA = vol.Schema({
    vol.Required(ATTR_SCRIPT_PATH): cv.string,
    vol.Optional(ATTR_PARAMS): vol.Any(dict, None),
})

SERVICE_RESTART_HA_SCHEMA = vol.Schema({})


async def async_setup_services(hass):
    """设置服务组件."""
    
    if hass.services.has_service(DOMAIN, SERVICE_RUN_SCRIPT):
        return
    
    async def handle_run_script(call: ServiceCall):
        """处理运行脚本服务调用."""
        script_path = call.data.get(ATTR_SCRIPT_PATH)
        params = call.data.get(ATTR_PARAMS, {})
        
        api_url = None
        
        # 尝试找到配置的API端点
        for entry_id, entry_data in hass.data[DOMAIN].items():
            if isinstance(entry_data, dict) and "api_url" in entry_data:
                api_url = entry_data["api_url"]
                break
        
        if not api_url:
            _LOGGER.error("没有找到配置的API端点")
            return
        
        try:
            response = await hass.async_add_executor_job(
                lambda: requests.post(
                    f"{api_url}/run_script",
                    json={"script_path": script_path, "params": params},
                    timeout=10
                )
            )
            response.raise_for_status()
            data = response.json()
            
            _LOGGER.info("脚本执行任务已创建: %s", data.get("task_id"))
            return data.get("task_id")
        
        except Exception as ex:
            _LOGGER.error("运行脚本失败: %s", ex)
            raise
    
    async def handle_restart_ha(call: ServiceCall):
        """处理重启Home Assistant服务调用."""
        api_url = None
        
        # 尝试找到配置的API端点
        for entry_id, entry_data in hass.data[DOMAIN].items():
            if isinstance(entry_data, dict) and "api_url" in entry_data:
                api_url = entry_data["api_url"]
                break
        
        if not api_url:
            _LOGGER.error("没有找到配置的API端点")
            return
        
        try:
            response = await hass.async_add_executor_job(
                lambda: requests.post(
                    f"{api_url}/restart_ha",
                    timeout=5
                )
            )
            response.raise_for_status()
            data = response.json()
            
            _LOGGER.info("重启命令已发送: %s", data.get("task_id"))
            return data.get("task_id")
        
        except Exception as ex:
            _LOGGER.error("重启Home Assistant失败: %s", ex)
            raise
    
    hass.services.async_register(
        DOMAIN, SERVICE_RUN_SCRIPT, handle_run_script, schema=SERVICE_RUN_SCRIPT_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_RESTART_HA, handle_restart_ha, schema=SERVICE_RESTART_HA_SCHEMA
    )
    
    return True


async def async_unload_services(hass):
    """卸载服务组件."""
    if hass.services.has_service(DOMAIN, SERVICE_RUN_SCRIPT):
        hass.services.async_remove(DOMAIN, SERVICE_RUN_SCRIPT)
    
    if hass.services.has_service(DOMAIN, SERVICE_RESTART_HA):
        hass.services.async_remove(DOMAIN, SERVICE_RESTART_HA) 