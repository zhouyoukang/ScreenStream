# Windsurf 计费逆向 & 积分优化

> 2026-03-20 | Windsurf v1.108.2 | 源码级逆向 + 客户端Patch + 工具链

## 文档

| 文件 | 说明 |
|------|------|
| `DEEP_CREDIT_MECHANISM_v8.md` | **主文档** — 六层计费架构+新旧体系完整逆向(700行) |

## 工具

| 文件 | 用途 | 命令 |
|------|------|------|
| `patch_continue_bypass.py` | P1-P4: maxGen=9999 + AutoContinue | `python patch_continue_bypass.py` |
| `patch_rate_limit_bypass.py` | P6-P8: Fail-Open + UI解锁 | `python patch_rate_limit_bypass.py` |
| `telemetry_reset.py` | 设备指纹重置→新Trial | `python telemetry_reset.py` |
| `credit_toolkit.py` | 积分监控/委派/Dashboard | `python credit_toolkit.py monitor` |
| `_model_matrix.py` | 提取最新模型积分矩阵 | `python _model_matrix.py` |
| `_decode_models.py` | 模型protobuf解码器 | — |

## 数据

| 文件 | 内容 |
|------|------|
| `_complete_model_matrix.json` | 102模型完整矩阵(含cost/ctx/tier) |
| `_decoded_models.json` | 8命令模型解码数据 |
| `_windsurf_backups/` | Patch原始备份 |
| `_archive/` | 历史归档 |

## 核心结论

- **3/18定价改革**: Credits → Quota/ACU (日+周双重刷新)
- **计费根源**: `PlanInfo.billing_strategy` (CREDITS=1/QUOTA=2/ACU=3)
- **服务端控制一切**: 客户端patch仅影响UI/门禁，不减少实际扣费
- **0成本模型永久有效**: SWE-1.5/1.6/Gemini Flash/Kimi/DeepSeek = 0 ACU
- **BYOK唯一真正绕过**: 自付API费 = 0 Windsurf成本

## 最优策略

```
P0: BYOK自带Key → 0 Windsurf成本
P1: SWE-1.5(0x)执行 → 无限免费
P2: 减少Context/Rules → 新体系按token计费
P3: 并行tool calls → 减少invocations
P4: 选高性价比模型 → GPT-4.1(1x) > Sonnet(2-4x) > Opus(4-12x)
```
