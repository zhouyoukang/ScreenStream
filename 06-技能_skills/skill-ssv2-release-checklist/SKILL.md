---
name: skill-ssv2-release-checklist
description: ScreenStream_v2 构建/发布/验收 checklist（减少漏项与返工）
metadata: {"aiot":{"risk":"high","needs_user_confirm":false}}
---

## 触发条件（triggers）

- 需要打包/发版/交付 APK 或进行对外演示。

## 目标（goal）

- 固化一份“可执行”的发版清单（构建→安装→网络→流→输入→回归）。

## 输入（inputs）

- 目标渠道：Debug/Release
- 目标输出链路：MJPEG / WebRTC / RTSP
- 目标设备：手机/平板/Quest

## refs（权威入口）

- docs 权威入口：`ScreenStream_v2/docs/README.md`
- 状态面板：`ScreenStream_v2/docs/STATUS.md`

## 护栏（guardrails）

- 禁止隐式改动 keystore/签名/版本策略。
- 如果涉及新增依赖/联网安装：必须显式确认（高风险）。

## 步骤（steps）

1. 构建：确认构建类型与产物路径
2. 安装：卸载旧版本（如有）→安装新包
3. 网络：确认同网段/FRP 参数/端口不冲突
4. 视频链路：打开 Web UI/播放器确认画面
5. 输入链路：点击/滑动/按键/文本输入回归
6. 回归：基础设置项与性能（帧率/延迟）
7. 归档：记录本次版本信息与已知问题

## 输出与验收（outputs）

- 产出：
  - 版本与验收记录（可追加到 `docs/STATUS.md` 的“本轮验收”段落）
- 验收标准：
  - 在目标设备上完成：看画面 + 远程输入 + 无明显端口冲突/闪退
