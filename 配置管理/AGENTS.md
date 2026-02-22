# 配置管理

> **P1 ScreenStream 子模块** — 各模块的配置接口定义。

## 项目边界

| 维度 | 值 |
|------|-----|
| **目录** | `配置管理/` |
| **语言** | Kotlin |
| **所属** | P1 ScreenStream Android |

## 可修改文件

```
配置管理/
├── 010-全局配置_GlobalSettings/
│   ├── AppSettings.kt          ← 全局配置接口
│   └── AppSettingsImpl.kt      ← 全局配置实现
└── 040-反向控制配置_InputSettings/
    ├── InputSettings.kt        ← 反向控制配置接口
    └── InputSettingsImpl.kt    ← 反向控制配置实现
```

## 禁止修改

- `智能家居/` `手机操控库/` `远程桌面/` 及所有外部项目

## 注意

- 修改配置接口会影响所有引用该配置的模块
- 新增配置项需同步更新 `用户界面/` 中的设置UI
