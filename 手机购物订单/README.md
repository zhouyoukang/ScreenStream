# 手机购物订单

从手机购物APP（淘宝/京东/拼多多/美团/饿了么/闲鱼/当当）采集的订单数据。

## 目录结构

```
手机购物订单/
├── 采集脚本/          ← 6个Python脚本（纯ADB + phone_lib两种模式）
├── 原始数据/          ← UI自动化采集的原始文本
└── 解析结果/          ← 语义解析后的结构化报告
```

## 采集脚本

| 脚本 | 方式 | 功能 |
|------|------|------|
| shopping_records.py | ADB直连 | 7个APP通用采集，Intent直跳订单页 |
| taobao_deep_collect.py | ADB直连 | 淘宝全量订单滚动采集 |
| taobao_deep.py | ADB直连 | 淘宝订单详情页钻取 |
| taobao_parse.py | 离线解析 | 语义分类引擎，从原始数据重建订单结构 |
| parse_orders.py | 离线解析 | 通用订单解析 |
| scan_book_orders.py | phone_lib | 跨平台书籍订单扫描 |

## 数据来源

- 设备: OnePlus NE2210 (Android 11)
- 采集日期: 2026-02-23
- 方法: uiautomator dump → 文本提取 → 语义解析
- 覆盖APP: 淘宝、京东、拼多多、美团、饿了么、闲鱼、当当

## 运行

```bash
# 采集（需ADB连接手机）
python 采集脚本/shopping_records.py

# 解析（离线，无需手机）
python 采集脚本/taobao_parse.py
python 采集脚本/parse_orders.py
```
