# 智能家居控制中心 · 独立于ScreenStream的网关服务

## 身份
独立项目。Python FastAPI网关，统一编排小米/易微联/HA/涂鸦/微信。无需触碰Android代码。

## 边界
- ✅ `网关服务/`下所有文件(自由创建)
- 🚫 `反向控制/输入路由/InputRoutes.kt`(SS路由，需协调)
- 🚫 `投屏链路/MJPEG投屏/assets/index.html`(SS前端)
- 🚫 `.windsurf/rules/` `.windsurf/skills/`

## 入口
- 启动: `cd 网关服务 && python gateway.py` (:8900)
- 验证: `python verify_platforms.py`
- 测试: `python test_wechat.py`

## 铁律
1. **跨项目修改协议**: 改InputRoutes.kt需通知SS Agent
2. gateway.py只做路由编排，每个平台一个`*_backend.py`
3. 凭据三级链: L1 config直填→L2 自缓存→L3 HA回退

## 关联
| 方向 | 项目 | 说明 |
|---|---|---|
| 代理 | ScreenStream | SS前端通过`/smarthome/*`代理到:8900 |
| 运维 | ADB reverse | `adb reverse tcp:8900 tcp:8900` |

## 陷阱
- 音箱核心洞察: 一台在线音箱 > 十个平台API(语音代理路径最强)
