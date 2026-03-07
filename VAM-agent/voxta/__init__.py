"""
Voxta Agent 控制包 — AI对话引擎管理

Voxta是独立的AI对话引擎，通过SignalR与VaM通信。
本包管理Voxta的所有方面：数据库/模块/角色/SignalR通信/服务进程/聊天/诊断。

模块:
  config        — Voxta路径/常量/服务配置
  db            — 数据库操作(角色/模块/记忆书/预设/对话)
  signalr       — SignalR实时WebSocket通信
  logs          — Voxta日志监控
  process       — Voxta服务生命周期管理
  chat          — 聊天引擎(独立/Voxta双模式, LLM/TTS直调, 角色加载, Prompt构建)
  hub           — 中枢控制(DB高级操作, 角色CRUD, TavernCard导入, 诊断, 自动修复)
  agent         — 统一Agent(五感集成)
  twitch_relay  — Twitch聊天→Voxta对话桥接 (from dion-labs/voxta-twitch-relay)
  remote_proxy  — 远程Voxta代理(WebSocket桥接+音频下载) (from Voxta.VamProxy)
"""

__version__ = "2.1.0"

from .config import VOXTA_CONFIG
from .agent import VoxtaAgent
from . import signalr
