# API Issues (Phone Agent → Developer Cascade)

## 2026-02-21 sendIntent 缺少 flags 参数 ✅ FIXED

- **发现方式**：尝试用 Intent 打开设置主页，但 Activity 恢复到上次子页面
- **预期行为**：`POST /intent {"action":"android.settings.SETTINGS"}` 应该能指定 `FLAG_ACTIVITY_CLEAR_TASK` 强制打开主页
- **实际行为**：`sendIntent()` 硬编码 `FLAG_ACTIVITY_NEW_TASK`，不暴露 flags 参数
- **API 端点**：`POST /intent`
- **代码位置**：`InputService.kt:2168` — `intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)`
- **建议修改**：在 params JSON 中增加可选的 `"flags"` 字段（整数），或增加 `"clearTask": true` 布尔值
- **设备**：OnePlus NE2210, Android 15
- **影响**：所有需要"干净启动"APP的场景（设置、部分 OEM APP 恢复上次位置）
- **临时绕行**：先 `POST /back` 多次退到主页，或用 `POST /command {"command":"打开设置"}` 通过自然语言命令

## 2026-02-21 端口探测应内置到 /status

- **发现方式**：默认端口8081不可用，实际端口是8086
- **问题**：Agent 每次连接都需要扫描 8080-8099 范围
- **建议**：ScreenStream 启动时通过 adb 写入实际端口到设备文件（如 `/sdcard/.screenstream_port`），或通过广播通知
