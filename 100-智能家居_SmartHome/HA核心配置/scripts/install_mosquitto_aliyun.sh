#!/bin/bash
# 阿里云服务器 Mosquitto MQTT Broker 安装脚本
# 服务器: 8.138.177.6

echo "=== 安装 Mosquitto MQTT Broker ==="

# 更新包管理器
apt-get update

# 安装 Mosquitto
apt-get install -y mosquitto mosquitto-clients

# 创建密码文件
echo "=== 配置 MQTT 用户 ==="
touch /etc/mosquitto/passwd
mosquitto_passwd -b /etc/mosquitto/passwd ha_mqtt ha_mqtt_password

# 创建配置文件
cat > /etc/mosquitto/conf.d/ha_mqtt.conf << 'EOF'
# Home Assistant MQTT 配置
# 监听端口
listener 1883 0.0.0.0

# 认证
allow_anonymous false
password_file /etc/mosquitto/passwd

# 日志
log_dest file /var/log/mosquitto/mosquitto.log
log_type all
EOF

# 重启 Mosquitto
echo "=== 重启 Mosquitto 服务 ==="
systemctl restart mosquitto
systemctl enable mosquitto

# 检查状态
echo "=== 检查服务状态 ==="
systemctl status mosquitto

# 测试连接
echo "=== 测试 MQTT 连接 ==="
echo "运行以下命令测试 (在另一个终端):"
echo "mosquitto_sub -h localhost -p 1883 -u ha_mqtt -P ha_mqtt_password -t 'ha/watch/command'"
echo ""
echo "发布测试消息:"
echo "mosquitto_pub -h localhost -p 1883 -u ha_mqtt -P ha_mqtt_password -t 'ha/watch/command' -m 'test'"

echo ""
echo "=== 安装完成 ==="
echo "MQTT Broker 地址: 8.138.177.6:1883"
echo "用户名: ha_mqtt"
echo "密码: ha_mqtt_password"
echo ""
echo "请确保阿里云安全组已开放 1883 端口!"
