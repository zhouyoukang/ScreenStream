# Immersive-Home VR智能家居参考

> 源项目: `e:\github\AIOT\Immersive-Home\` | 原作者: Nitwel
> 混合现实 + 智能家居控制

## 定位

将Smart Home和Mixed Reality技术结合，在VR/MR中直观控制智能家居设备。

## 核心特性

- 快速直观的IoT设备控制
- 智能家居实时概览
- 内置语音助手
- 房屋微缩模型管理
- 手势自然交互
- 基于房间位置的高级自动化

## 技术栈

- **引擎**: Godot (GDScript)
- **平台**: Meta Quest 2 / Pro / 3
- **智能家居**: Home Assistant集成
- **分发**: Meta App Lab / SideQuest / itch.io

## 与用户生态的关系

用户已有Meta Quest设备（从VR_Hub/quest_recordings等目录推断），Immersive-Home可作为VR端的智能家居控制入口：

```
VR头显 → Immersive-Home → Home Assistant API → 设备控制
手机   → ScreenStream    → HA/MIGPT          → 设备控制
语音   → 小爱/ha-chat    → HA/MIGPT          → 设备控制
PC     → n8n/Node-RED    → HA API            → 设备控制
```

## 参考价值

- VR中控制智能家居的UX模式
- 空间位置驱动的自动化理念
- Home Assistant自定义组件开发
- Godot + WebSocket + HA API集成

## 当前状态

- 项目已clone，含论文PDF(thesis.pdf)
- 未进行二次开发
- 作为长期探索方向保留

## 文档

- 用户文档: https://docs.immersive-home.org/
- 开发文档: https://docs.immersive-home.org/development/
