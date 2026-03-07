"""工具库管理器传感器."""
import logging
from datetime import timedelta
import aiohttp
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """设置传感器平台."""
    api_url = hass.data[DOMAIN][entry.entry_id]["api_url"]
    
    # 创建数据协调器
    coordinator = HAToolsCoordinator(hass, api_url)
    await coordinator.async_config_entry_first_refresh()
    
    # 创建传感器
    sensors = [
        HAToolsSystemInfoSensor(coordinator),
        HAToolsBackupsSensor(coordinator),
    ]
    
    async_add_entities(sensors, True)


class HAToolsCoordinator(DataUpdateCoordinator):
    """数据更新协调器."""

    def __init__(self, hass: HomeAssistant, api_url: str) -> None:
        """初始化协调器."""
        super().__init__(
            hass,
            _LOGGER,
            name="HA Tools Manager",
            update_interval=SCAN_INTERVAL,
        )
        self.api_url = api_url
        self.data = {
            "system_info": {},
            "backups": [],
            "scripts": []
        }

    async def _async_update_data(self):
        """获取最新的数据."""
        try:
            async with async_timeout.timeout(10):
                data = await self.hass.async_add_executor_job(self._fetch_data)
                return data
        except Exception as err:
            _LOGGER.error("更新数据时出错: %s", err)
            raise

    def _fetch_data(self):
        """从API获取数据."""
        data = {
            "system_info": {},
            "backups": [],
            "scripts": []
        }
        
        try:
            # 获取系统信息
            system_info_url = f"{self.api_url}/system_info"
            system_info_response = requests.get(system_info_url, timeout=5)
            system_info_response.raise_for_status()
            data["system_info"] = system_info_response.json()
            
            # 获取备份列表
            backups_url = f"{self.api_url}/backups"
            backups_response = requests.get(backups_url, timeout=5)
            backups_response.raise_for_status()
            data["backups"] = backups_response.json()
            
            # 获取脚本列表
            scripts_url = f"{self.api_url}/scripts"
            scripts_response = requests.get(scripts_url, timeout=5)
            scripts_response.raise_for_status()
            data["scripts"] = scripts_response.json()
            
        except Exception as e:
            _LOGGER.error("获取API数据时出错: %s", e)
            # 保留已有数据
            return self.data
        
        return data


class HAToolsSystemInfoSensor(CoordinatorEntity, SensorEntity):
    """系统信息传感器."""

    def __init__(self, coordinator: HAToolsCoordinator) -> None:
        """初始化传感器."""
        super().__init__(coordinator)
        self._attr_name = "HA工具管理器系统信息"
        self._attr_unique_id = "ha_tools_manager_system_info"

    @property
    def state(self):
        """返回传感器状态."""
        if "system_info" in self.coordinator.data:
            info = self.coordinator.data["system_info"]
            if "error_count" in info:
                return info["error_count"]
        return 0
    
    @property
    def extra_state_attributes(self):
        """返回实体的状态属性."""
        if "system_info" in self.coordinator.data:
            return self.coordinator.data["system_info"]
        return {}


class HAToolsBackupsSensor(CoordinatorEntity, SensorEntity):
    """备份信息传感器."""

    def __init__(self, coordinator: HAToolsCoordinator) -> None:
        """初始化传感器."""
        super().__init__(coordinator)
        self._attr_name = "HA工具管理器备份信息"
        self._attr_unique_id = "ha_tools_manager_backups"

    @property
    def state(self):
        """返回传感器状态."""
        if "backups" in self.coordinator.data:
            return len(self.coordinator.data["backups"])
        return 0
    
    @property
    def extra_state_attributes(self):
        """返回实体的状态属性."""
        if "backups" in self.coordinator.data:
            # 只返回最新的10个备份信息
            backups = self.coordinator.data["backups"][:10]
            return {
                "backups": backups,
                "total_count": len(self.coordinator.data["backups"])
            }
        return {} 