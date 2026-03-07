#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型Node-RED流程生成器 - 为现有配置添加智能扩展
"""

import json
import uuid
import requests
from datetime import datetime

class FlowEnhancer:
    """Node-RED流程增强器"""
    
    def __init__(self, base_flows_file="current_flows.json"):
        # 读取现有流程
        with open(base_flows_file, 'r', encoding='utf-8') as f:
            self.base_flows = json.load(f)
        
        # 获取现有的关键ID
        self.tab_id = "b2fcf780a080b1cf"  # 流程1的ID
        self.ha_server_id = "2c7035591d8a9576"  # Home Assistant服务器ID
        
        # 生成新的ID
        self.new_ids = {}
        
    def generate_id(self, name):
        """生成唯一ID"""
        if name not in self.new_ids:
            self.new_ids[name] = str(uuid.uuid4()).replace('-', '')[:16]
        return self.new_ids[name]
    
    def create_enhanced_flows(self):
        """创建增强的流程配置"""
        enhanced_flows = self.base_flows.copy()
        
        # 添加新的实体配置
        enhanced_flows.extend(self.create_new_entities())
        
        # 添加温湿度监控
        enhanced_flows.extend(self.create_temperature_monitoring())
        
        # 添加定时任务
        enhanced_flows.extend(self.create_scheduled_tasks())
        
        # 添加语音控制集成
        enhanced_flows.extend(self.create_voice_control())
        
        # 添加安全监控
        enhanced_flows.extend(self.create_security_monitoring())
        
        # 添加节能管理
        enhanced_flows.extend(self.create_energy_management())
        
        # 添加通知系统
        enhanced_flows.extend(self.create_notification_system())
        
        # 添加自动化场景
        enhanced_flows.extend(self.create_automation_scenes())
        
        return enhanced_flows
    
    def create_new_entities(self):
        """创建新的Home Assistant实体配置"""
        entities = []
        
        # 温湿度传感器实体
        entities.append({
            "id": self.generate_id("temp_sensor_config"),
            "type": "ha-entity-config",
            "server": self.ha_server_id,
            "deviceConfig": "",
            "name": "环境监控",
            "version": "6",
            "entityType": "sensor",
            "haConfig": [
                {"property": "name", "value": "室内温湿度"},
                {"property": "icon", "value": "mdi:thermometer"},
                {"property": "entity_category", "value": ""},
                {"property": "device_class", "value": "temperature"}
            ],
            "resend": False,
            "debugEnabled": False
        })
        
        # 场景控制实体
        entities.append({
            "id": self.generate_id("scene_config"),
            "type": "ha-entity-config",
            "server": self.ha_server_id,
            "deviceConfig": "",
            "name": "智能场景",
            "version": "6",
            "entityType": "switch",
            "haConfig": [
                {"property": "name", "value": "智能场景控制"},
                {"property": "icon", "value": "mdi:home-automation"},
                {"property": "entity_category", "value": ""},
                {"property": "device_class", "value": ""}
            ],
            "resend": False,
            "debugEnabled": False
        })
        
        # 安全监控实体
        entities.append({
            "id": self.generate_id("security_config"),
            "type": "ha-entity-config",
            "server": self.ha_server_id,
            "deviceConfig": "",
            "name": "安全监控",
            "version": "6",
            "entityType": "binary_sensor",
            "haConfig": [
                {"property": "name", "value": "家庭安全状态"},
                {"property": "icon", "value": "mdi:security"},
                {"property": "entity_category", "value": ""},
                {"property": "device_class", "value": "safety"}
            ],
            "resend": False,
            "debugEnabled": False
        })
        
        return entities
    
    def create_temperature_monitoring(self):
        """创建温湿度监控节点"""
        nodes = []
        
        # 温度传感器监控
        nodes.append({
            "id": self.generate_id("temp_monitor"),
            "type": "ha-sensor",
            "z": self.tab_id,
            "name": "温湿度监控",
            "server": self.ha_server_id,
            "version": 1,
            "exposeAsEntityConfig": "",
            "inputs": 0,
            "outputs": 1,
            "entityConfig": self.generate_id("temp_sensor_config"),
            "outputProperties": [
                {"property": "payload", "propertyType": "msg", "value": "", "valueType": "entityState"},
                {"property": "data", "propertyType": "msg", "value": "", "valueType": "entity"}
            ],
            "x": 150,
            "y": 900,
            "wires": [[self.generate_id("temp_check")]]
        })
        
        # 温度检查逻辑
        nodes.append({
            "id": self.generate_id("temp_check"),
            "type": "switch",
            "z": self.tab_id,
            "name": "温度检查",
            "property": "payload",
            "propertyType": "msg",
            "rules": [
                {"t": "gte", "v": "28", "vt": "num"},  # 高温
                {"t": "lte", "v": "18", "vt": "num"},  # 低温
                {"t": "else"}  # 正常
            ],
            "checkall": "false",
            "repair": False,
            "outputs": 3,
            "x": 350,
            "y": 900,
            "wires": [
                [self.generate_id("high_temp_action")],
                [self.generate_id("low_temp_action")],
                [self.generate_id("normal_temp_action")]
            ]
        })
        
        # 高温处理
        nodes.append({
            "id": self.generate_id("high_temp_action"),
            "type": "http request",
            "z": self.tab_id,
            "name": "高温警告",
            "method": "GET",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "http://192.168.31.228:8080/high_temperature",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 550,
            "y": 860,
            "wires": [[]]
        })
        
        # 低温处理
        nodes.append({
            "id": self.generate_id("low_temp_action"),
            "type": "http request",
            "z": self.tab_id,
            "name": "低温提醒",
            "method": "GET",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "http://192.168.31.228:8080/low_temperature",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 550,
            "y": 920,
            "wires": [[]]
        })
        
        # 正常温度
        nodes.append({
            "id": self.generate_id("normal_temp_action"),
            "type": "debug",
            "z": self.tab_id,
            "name": "温度正常",
            "active": True,
            "tosidebar": True,
            "console": False,
            "tostatus": False,
            "complete": "payload",
            "targetType": "msg",
            "statusVal": "",
            "statusType": "auto",
            "x": 550,
            "y": 980,
            "wires": []
        })
        
        return nodes
    
    def create_scheduled_tasks(self):
        """创建定时任务节点"""
        nodes = []
        
        # 早晨例程定时器
        nodes.append({
            "id": self.generate_id("morning_timer"),
            "type": "inject",
            "z": self.tab_id,
            "name": "早晨例程",
            "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
            "repeat": "",
            "crontab": "00 07 * * *",  # 每天7:00
            "once": False,
            "onceDelay": 0.1,
            "topic": "morning_routine",
            "payload": "start",
            "payloadType": "str",
            "x": 150,
            "y": 1100,
            "wires": [[self.generate_id("morning_sequence")]]
        })
        
        # 早晨例程序列
        nodes.append({
            "id": self.generate_id("morning_sequence"),
            "type": "function",
            "z": self.tab_id,
            "name": "早晨例程逻辑",
            "func": '''
// 早晨例程：开灯 -> 播放音乐 -> 启动AI助手
var sequence = [
    {url: "http://192.168.31.228:8080/morning_light", delay: 0},
    {url: "http://192.168.31.228:8080/morning_music", delay: 5000},
    {url: "http://192.168.31.228:8080/doubao", delay: 10000},
    {url: "http://localhost:12101/api/text-to-speech", method: "POST", data: "早上好，新的一天开始了", delay: 15000}
];

var index = context.get("morning_index") || 0;
if (index < sequence.length) {
    var action = sequence[index];
    msg.url = action.url;
    msg.method = action.method || "GET";
    if (action.data) msg.payload = action.data;
    
    context.set("morning_index", index + 1);
    
    // 设置下一个动作的延时
    if (index + 1 < sequence.length) {
        setTimeout(() => {
            node.send(msg);
        }, action.delay);
    }
    return msg;
} else {
    context.set("morning_index", 0);
    return null;
}
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 350,
            "y": 1100,
            "wires": [[self.generate_id("morning_http")]]
        })
        
        # 早晨HTTP请求
        nodes.append({
            "id": self.generate_id("morning_http"),
            "type": "http request",
            "z": self.tab_id,
            "name": "执行早晨动作",
            "method": "use",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 550,
            "y": 1100,
            "wires": [[]]
        })
        
        # 晚间例程定时器
        nodes.append({
            "id": self.generate_id("evening_timer"),
            "type": "inject",
            "z": self.tab_id,
            "name": "晚间例程",
            "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
            "repeat": "",
            "crontab": "00 22 * * *",  # 每天22:00
            "once": False,
            "onceDelay": 0.1,
            "topic": "evening_routine",
            "payload": "start",
            "payloadType": "str",
            "x": 150,
            "y": 1200,
            "wires": [[self.generate_id("evening_sequence")]]
        })
        
        # 晚间例程序列
        nodes.append({
            "id": self.generate_id("evening_sequence"),
            "type": "function",
            "z": self.tab_id,
            "name": "晚间例程逻辑",
            "func": '''
// 晚间例程：检查功率 -> 关闭设备 -> 调暗灯光 -> 晚安语音
var sequence = [
    {url: "http://192.168.31.228:8080/power_check", delay: 0},
    {url: "http://192.168.31.228:8080/evening_music_stop", delay: 3000},
    {url: "http://192.168.31.228:8080/dim_lights", delay: 6000},
    {url: "http://localhost:12101/api/text-to-speech", method: "POST", data: "晚安，祝您好梦", delay: 10000}
];

var index = context.get("evening_index") || 0;
if (index < sequence.length) {
    var action = sequence[index];
    msg.url = action.url;
    msg.method = action.method || "GET";
    if (action.data) msg.payload = action.data;
    
    context.set("evening_index", index + 1);
    
    // 设置下一个动作的延时
    if (index + 1 < sequence.length) {
        setTimeout(() => {
            node.send(msg);
        }, action.delay);
    }
    return msg;
} else {
    context.set("evening_index", 0);
    return null;
}
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 350,
            "y": 1200,
            "wires": [[self.generate_id("evening_http")]]
        })
        
        # 晚间HTTP请求
        nodes.append({
            "id": self.generate_id("evening_http"),
            "type": "http request",
            "z": self.tab_id,
            "name": "执行晚间动作",
            "method": "use",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 550,
            "y": 1200,
            "wires": [[]]
        })
        
        return nodes
    
    def create_voice_control(self):
        """创建语音控制集成"""
        nodes = []
        
        # Rhasspy语音输入
        nodes.append({
            "id": self.generate_id("voice_input"),
            "type": "http in",
            "z": self.tab_id,
            "name": "语音指令接收",
            "url": "/voice/command",
            "method": "post",
            "upload": False,
            "swaggerDoc": "",
            "x": 150,
            "y": 1350,
            "wires": [[self.generate_id("voice_parser")]]
        })
        
        # 语音解析
        nodes.append({
            "id": self.generate_id("voice_parser"),
            "type": "function",
            "z": self.tab_id,
            "name": "语音指令解析",
            "func": '''
// 解析语音指令
var command = msg.payload.text || msg.payload;
var intent = "";
var action = "";

// 指令映射
if (command.includes("开灯") || command.includes("打开灯")) {
    intent = "light_control";
    action = "on";
} else if (command.includes("关灯") || command.includes("关闭灯")) {
    intent = "light_control";
    action = "off";
} else if (command.includes("播放音乐") || command.includes("放音乐")) {
    intent = "music_control";
    action = "play";
} else if (command.includes("停止音乐") || command.includes("关闭音乐")) {
    intent = "music_control";
    action = "stop";
} else if (command.includes("启动") && command.includes("豆包")) {
    intent = "ai_control";
    action = "doubao_start";
} else if (command.includes("启动") && command.includes("kimi")) {
    intent = "ai_control";
    action = "kimi_start";
} else if (command.includes("晚安") || command.includes("睡眠模式")) {
    intent = "scene_control";
    action = "sleep";
} else if (command.includes("早安") || command.includes("起床模式")) {
    intent = "scene_control";
    action = "wakeup";
}

msg.intent = intent;
msg.action = action;
msg.original_command = command;

return msg;
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 350,
            "y": 1350,
            "wires": [[self.generate_id("voice_router")]]
        })
        
        # 语音路由
        nodes.append({
            "id": self.generate_id("voice_router"),
            "type": "switch",
            "z": self.tab_id,
            "name": "语音指令路由",
            "property": "intent",
            "propertyType": "msg",
            "rules": [
                {"t": "eq", "v": "light_control", "vt": "str"},
                {"t": "eq", "v": "music_control", "vt": "str"},
                {"t": "eq", "v": "ai_control", "vt": "str"},
                {"t": "eq", "v": "scene_control", "vt": "str"},
                {"t": "else"}
            ],
            "checkall": "false",
            "repair": False,
            "outputs": 5,
            "x": 550,
            "y": 1350,
            "wires": [
                [self.generate_id("voice_light")],
                [self.generate_id("voice_music")],
                [self.generate_id("voice_ai")],
                [self.generate_id("voice_scene")],
                [self.generate_id("voice_unknown")]
            ]
        })
        
        # 语音控制灯光
        nodes.append({
            "id": self.generate_id("voice_light"),
            "type": "function",
            "z": self.tab_id,
            "name": "语音控制灯光",
            "func": '''
if (msg.action === "on") {
    msg.url = "http://192.168.31.228:8080/voice_light_on";
} else if (msg.action === "off") {
    msg.url = "http://192.168.31.228:8080/voice_light_off";
}
return msg;
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 750,
            "y": 1300,
            "wires": [[self.generate_id("voice_execute")]]
        })
        
        # 语音执行HTTP
        nodes.append({
            "id": self.generate_id("voice_execute"),
            "type": "http request",
            "z": self.tab_id,
            "name": "执行语音命令",
            "method": "GET",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 950,
            "y": 1350,
            "wires": [[self.generate_id("voice_response")]]
        })
        
        # 语音响应
        nodes.append({
            "id": self.generate_id("voice_response"),
            "type": "http request",
            "z": self.tab_id,
            "name": "语音反馈",
            "method": "POST",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "http://localhost:12101/api/text-to-speech",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [{"keyType": "other", "keyValue": "Content-Type", "valueType": "other", "valueValue": "text/plain"}],
            "x": 1150,
            "y": 1350,
            "wires": [[]]
        })
        
        return nodes
    
    def create_security_monitoring(self):
        """创建安全监控节点"""
        nodes = []
        
        # 安全状态监控
        nodes.append({
            "id": self.generate_id("security_monitor"),
            "type": "inject",
            "z": self.tab_id,
            "name": "安全检查",
            "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
            "repeat": "3600",  # 每小时检查一次
            "crontab": "",
            "once": True,
            "onceDelay": 10,
            "topic": "security_check",
            "payload": "check",
            "payloadType": "str",
            "x": 150,
            "y": 1500,
            "wires": [[self.generate_id("security_check")]]
        })
        
        # 安全检查逻辑
        nodes.append({
            "id": self.generate_id("security_check"),
            "type": "function",
            "z": self.tab_id,
            "name": "安全检查逻辑",
            "func": '''
// 检查各种安全状态
var checks = [];

// 检查功率异常
var power = flow.get("total_power") || 0;
if (power > 800) {
    checks.push("功率使用异常: " + power + "W");
}

// 检查时间段（深夜活动检测）
var hour = new Date().getHours();
if ((hour >= 23 || hour <= 5) && power > 200) {
    checks.push("深夜高功率活动检测");
}

// 检查设备状态
var deviceStatus = flow.get("device_status") || {};
if (Object.keys(deviceStatus).length === 0) {
    checks.push("设备状态未知");
}

msg.security_issues = checks;
msg.severity = checks.length > 0 ? "warning" : "normal";

return msg;
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 350,
            "y": 1500,
            "wires": [[self.generate_id("security_alert")]]
        })
        
        # 安全警告
        nodes.append({
            "id": self.generate_id("security_alert"),
            "type": "switch",
            "z": self.tab_id,
            "name": "安全警告判断",
            "property": "severity",
            "propertyType": "msg",
            "rules": [
                {"t": "eq", "v": "warning", "vt": "str"},
                {"t": "eq", "v": "normal", "vt": "str"}
            ],
            "checkall": "false",
            "repair": False,
            "outputs": 2,
            "x": 550,
            "y": 1500,
            "wires": [
                [self.generate_id("security_notification")],
                [self.generate_id("security_log")]
            ]
        })
        
        # 安全通知
        nodes.append({
            "id": self.generate_id("security_notification"),
            "type": "http request",
            "z": self.tab_id,
            "name": "发送安全警告",
            "method": "GET",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "http://192.168.31.228:8080/security_alert",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 750,
            "y": 1480,
            "wires": [[]]
        })
        
        return nodes
    
    def create_energy_management(self):
        """创建节能管理节点"""
        nodes = []
        
        # 节能监控
        nodes.append({
            "id": self.generate_id("energy_monitor"),
            "type": "inject",
            "z": self.tab_id,
            "name": "节能检查",
            "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
            "repeat": "1800",  # 每30分钟检查一次
            "crontab": "",
            "once": True,
            "onceDelay": 5,
            "topic": "energy_check",
            "payload": "check",
            "payloadType": "str",
            "x": 150,
            "y": 1650,
            "wires": [[self.generate_id("energy_analysis")]]
        })
        
        # 节能分析
        nodes.append({
            "id": self.generate_id("energy_analysis"),
            "type": "function",
            "z": self.tab_id,
            "name": "节能分析",
            "func": '''
// 获取当前功率
var power = flow.get("total_power") || 0;
var hour = new Date().getHours();
var actions = [];

// 节能策略
if (power > 600) {
    actions.push("high_power_alert");
}

// 夜间节能
if (hour >= 23 || hour <= 6) {
    if (power > 100) {
        actions.push("night_energy_save");
    }
}

// 白天无人时节能
if (hour >= 9 && hour <= 17) {
    var motion = flow.get("motion_detected") || false;
    if (!motion && power > 200) {
        actions.push("daytime_energy_save");
    }
}

msg.energy_actions = actions;
msg.current_power = power;
msg.recommendation = actions.length > 0 ? "节能建议可用" : "能耗正常";

return msg;
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 350,
            "y": 1650,
            "wires": [[self.generate_id("energy_action")]]
        })
        
        # 节能行动
        nodes.append({
            "id": self.generate_id("energy_action"),
            "type": "function",
            "z": self.tab_id,
            "name": "执行节能措施",
            "func": '''
var actions = msg.energy_actions || [];
var urls = [];

actions.forEach(action => {
    switch(action) {
        case "high_power_alert":
            urls.push("http://192.168.31.228:8080/high_power_warning");
            break;
        case "night_energy_save":
            urls.push("http://192.168.31.228:8080/night_energy_mode");
            break;
        case "daytime_energy_save":
            urls.push("http://192.168.31.228:8080/daytime_energy_save");
            break;
    }
});

if (urls.length > 0) {
    msg.url = urls[0]; // 执行第一个动作
    return msg;
}
return null;
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 550,
            "y": 1650,
            "wires": [[self.generate_id("energy_http")]]
        })
        
        # 节能HTTP请求
        nodes.append({
            "id": self.generate_id("energy_http"),
            "type": "http request",
            "z": self.tab_id,
            "name": "执行节能动作",
            "method": "GET",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 750,
            "y": 1650,
            "wires": [[]]
        })
        
        return nodes
    
    def create_notification_system(self):
        """创建通知系统"""
        nodes = []
        
        # 通知中心
        nodes.append({
            "id": self.generate_id("notification_center"),
            "type": "function",
            "z": self.tab_id,
            "name": "通知中心",
            "func": '''
// 通知管理中心
var notifications = context.get("notifications") || [];
var newNotification = {
    timestamp: new Date().toISOString(),
    type: msg.type || "info",
    message: msg.message || msg.payload,
    priority: msg.priority || "normal"
};

notifications.push(newNotification);

// 保持最近50条通知
if (notifications.length > 50) {
    notifications = notifications.slice(-50);
}

context.set("notifications", notifications);

// 根据优先级决定是否立即处理
if (newNotification.priority === "urgent") {
    msg.immediate = true;
}

return msg;
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 350,
            "y": 1800,
            "wires": [[self.generate_id("notification_router")]]
        })
        
        return nodes
    
    def create_automation_scenes(self):
        """创建自动化场景"""
        nodes = []
        
        # 智能场景控制器
        nodes.append({
            "id": self.generate_id("scene_controller"),
            "type": "ha-switch",
            "z": self.tab_id,
            "name": "智能场景控制",
            "server": self.ha_server_id,
            "version": 0,
            "debugenabled": False,
            "inputs": 0,
            "outputs": 2,
            "entityConfig": self.generate_id("scene_config"),
            "enableInput": False,
            "outputOnStateChange": True,
            "outputProperties": [
                {"property": "outputType", "propertyType": "msg", "value": "state change", "valueType": "str"},
                {"property": "payload", "propertyType": "msg", "value": "", "valueType": "entityState"}
            ],
            "x": 150,
            "y": 1950,
            "wires": [
                [self.generate_id("scene_selector")],
                []
            ]
        })
        
        # 场景选择器
        nodes.append({
            "id": self.generate_id("scene_selector"),
            "type": "function",
            "z": self.tab_id,
            "name": "场景选择器",
            "func": '''
// 根据时间和状态选择合适的场景
var hour = new Date().getHours();
var scene = "";

if (hour >= 6 && hour < 9) {
    scene = "morning";
} else if (hour >= 9 && hour < 17) {
    scene = "daytime";
} else if (hour >= 17 && hour < 22) {
    scene = "evening";
} else {
    scene = "night";
}

msg.scene = scene;
msg.hour = hour;

return msg;
''',
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 350,
            "y": 1950,
            "wires": [[self.generate_id("scene_executor")]]
        })
        
        # 场景执行器
        nodes.append({
            "id": self.generate_id("scene_executor"),
            "type": "switch",
            "z": self.tab_id,
            "name": "场景执行器",
            "property": "scene",
            "propertyType": "msg",
            "rules": [
                {"t": "eq", "v": "morning", "vt": "str"},
                {"t": "eq", "v": "daytime", "vt": "str"},
                {"t": "eq", "v": "evening", "vt": "str"},
                {"t": "eq", "v": "night", "vt": "str"}
            ],
            "checkall": "false",
            "repair": False,
            "outputs": 4,
            "x": 550,
            "y": 1950,
            "wires": [
                [self.generate_id("morning_scene_http")],
                [self.generate_id("daytime_scene_http")],
                [self.generate_id("evening_scene_http")],
                [self.generate_id("night_scene_http")]
            ]
        })
        
        # 各种场景的HTTP请求节点
        scenes = ["morning", "daytime", "evening", "night"]
        y_positions = [1900, 1950, 2000, 2050]
        
        for i, scene in enumerate(scenes):
            nodes.append({
                "id": self.generate_id(f"{scene}_scene_http"),
                "type": "http request",
                "z": self.tab_id,
                "name": f"{scene.title()}场景",
                "method": "GET",
                "ret": "txt",
                "paytoqs": "ignore",
                "url": f"http://192.168.31.228:8080/scene_{scene}",
                "tls": "",
                "persist": False,
                "proxy": "",
                "insecureHTTPParser": False,
                "authType": "",
                "senderr": False,
                "headers": [],
                "x": 750,
                "y": y_positions[i],
                "wires": [[]]
            })
        
        return nodes

def deploy_enhanced_flows():
    """部署增强的流程"""
    print("🚀 开始生成增强的Node-RED流程...")
    
    enhancer = FlowEnhancer()
    enhanced_flows = enhancer.create_enhanced_flows()
    
    # 保存到文件
    with open("enhanced_flows.json", "w", encoding="utf-8") as f:
        json.dump(enhanced_flows, f, ensure_ascii=False, indent=2)
    
    print(f"📝 增强流程已保存到 enhanced_flows.json")
    print(f"📊 新增节点数量: {len(enhanced_flows) - len(enhancer.base_flows)}")
    
    # 尝试部署到Node-RED
    try:
        response = requests.post(
            "http://localhost:1880/flows",
            json=enhanced_flows,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ 增强流程已成功部署到Node-RED!")
            return True
        else:
            print(f"❌ 部署失败: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 部署失败: {e}")
        print("💡 你可以手动导入 enhanced_flows.json 文件到Node-RED")
        return False

if __name__ == "__main__":
    deploy_enhanced_flows()

