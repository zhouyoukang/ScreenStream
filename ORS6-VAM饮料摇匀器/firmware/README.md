# ESP32固件选择指南

## 推荐固件

### 1. TCodeESP32 ⭐ (功能最全)

- **仓库**: [jcfain/TCodeESP32](https://github.com/jcfain/TCodeESP32)
- **特点**: Serial + WiFi + Bluetooth, Web配置界面
- **芯片**: ESP32 DevKit V1
- **烧写**: Arduino IDE / PlatformIO

### 2. osr-esp32 (BLE增强)

- **仓库**: [ayvasoftware/osr-esp32](https://github.com/ayvasoftware/osr-esp32)
- **特点**: BLE Streaming TCode支持
- **芯片**: ESP32

### 3. osr-esp32-s3 (新芯片)

- **仓库**: [BQsummer/osr-esp32-s3](https://github.com/BQsummer/osr-esp32-s3)
- **特点**: ESP32-S3适配, 默认OSR6模式
- **芯片**: ESP32-S3

### 4. TCodeESP32-SR6MB (SR6主板)

- **仓库**: [Diy6bot/TCodeESP32-SR6MB](https://github.com/Diy6bot/TCodeESP32-SR6MB)
- **特点**: SR6专用主板, Crimzzon修改版 v1.38b

### 5. MiraBot (图形化烧写)

- **网站**: [mirabotx.com](https://mirabotx.com/guide-osr-compatible-firmware/)
- **特点**: 浏览器一键烧写, 无需IDE

## 烧写方法

详见 `../tools/flash_firmware.py --guide`

## 固件配置 (TCodeESP32)

烧写后ESP32启动WiFi AP:

1. 手机连接 `TCode_xxxxx` WiFi
2. 打开 `192.168.4.1`
3. 配置: WiFi网络、UDP端口、轴范围、舵机引脚

## 引脚定义 (默认)

| 轴 | GPIO | 舵机 |
|----|------|------|
| L0 | 13 | Stroke |
| L1 | 14 | Surge |
| L2 | 15 | Sway |
| R0 | 16 | Twist |
| R1 | 17 | Roll |
| R2 | 18 | Pitch |

> 具体引脚定义取决于固件版本，请查阅对应仓库README
