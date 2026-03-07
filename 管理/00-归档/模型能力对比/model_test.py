"""
Windsurf 全模型后端测试 v2.0
=============================
不依赖IDE页面，直接后端调用测试所有模型。

测试策略（三路并行）：
  路径A: 通过CFW代理 → Codeium gRPC API（Windsurf原生模型）
  路径B: 直接调用模型提供商API（BYOK模型）
  路径C: 本地语言服务器gRPC探测

伏羲八卦映射：
  ☰乾(编码) ☱兑(多模态) ☲离(速度) ☳震(成本)
  ☴巽(工具) ☵坎(推理) ☶艮(安全) ☷坤(上下文)

用法:
  python model_test.py                 # 完整测试
  python model_test.py --quick         # 快速探测
  python model_test.py --report        # 仅生成报告
"""

import os
import sys
import json
import time
import ssl
import struct
import socket
import http.client
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
import uuid
from collections import OrderedDict

# ==================== 配置 ====================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RESULTS_FILE = SCRIPT_DIR / "test_results.json"
REPORT_FILE = SCRIPT_DIR / "TEST_REPORT.md"

# Windsurf 进程信息
WINDSURF_JS = Path(r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js")
CODEIUM_DIR = Path(os.path.expanduser("~")) / ".codeium" / "windsurf"

# CFW 代理
CFW_HOST = "127.0.0.1"
CFW_PORT = 443

# Codeium API 端点
CODEIUM_API_SERVER = "server.self-serve.windsurf.com"
CODEIUM_INFERENCE = "inference.codeium.com"

# 测试提示词
TEST_PROMPT = "Write a Python function that calculates fibonacci(n) recursively with memoization. Return only the code."
TEST_PROMPT_CN = "写一个Python斐波那契函数，带记忆化递归。只返回代码。"


def load_secrets_env():
    """自动加载secrets.env中所有键值对到环境变量"""
    secrets_file = PROJECT_ROOT / "secrets.env"
    loaded = 0
    if secrets_file.exists():
        for line in secrets_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if val and key not in os.environ:
                    os.environ[key] = val
                    loaded += 1
    return loaded


# 代理（用于国外API）
HTTP_PROXY = "http://127.0.0.1:7890"

# ==================== 模型枚举（从JS逆向提取） ====================

# 用户可见的聊天模型（排除内部/embedding/tab模型）
CHAT_MODELS = OrderedDict([
    # Anthropic/Claude
    ("MODEL_CLAUDE_4_6_OPUS", {"provider": "Anthropic", "name": "Claude 4.6 Opus", "tier": "premium", "credits": "10x"}),
    ("MODEL_CLAUDE_4_6_SONNET", {"provider": "Anthropic", "name": "Claude 4.6 Sonnet", "tier": "premium", "credits": "2x"}),
    ("MODEL_CLAUDE_4_5_OPUS", {"provider": "Anthropic", "name": "Claude 4.5 Opus", "tier": "premium", "credits": "10x"}),
    ("MODEL_CLAUDE_4_5_OPUS_THINKING", {"provider": "Anthropic", "name": "Claude 4.5 Opus (Thinking)", "tier": "premium", "credits": "10x"}),
    ("MODEL_CLAUDE_4_5_SONNET", {"provider": "Anthropic", "name": "Claude 4.5 Sonnet", "tier": "premium", "credits": "2x"}),
    ("MODEL_CLAUDE_4_5_SONNET_THINKING", {"provider": "Anthropic", "name": "Claude 4.5 Sonnet (Thinking)", "tier": "premium", "credits": "2x"}),
    ("MODEL_CLAUDE_4_5_SONNET_1M", {"provider": "Anthropic", "name": "Claude 4.5 Sonnet 1M", "tier": "premium", "credits": "4x"}),
    ("MODEL_CLAUDE_4_1_OPUS", {"provider": "Anthropic", "name": "Claude 4.1 Opus", "tier": "premium", "credits": "10x"}),
    ("MODEL_CLAUDE_4_OPUS", {"provider": "Anthropic", "name": "Claude 4 Opus", "tier": "premium", "credits": "10x"}),
    ("MODEL_CLAUDE_4_SONNET", {"provider": "Anthropic", "name": "Claude 4 Sonnet", "tier": "premium", "credits": "2x"}),
    ("MODEL_CLAUDE_4_SONNET_THINKING", {"provider": "Anthropic", "name": "Claude 4 Sonnet (Thinking)", "tier": "premium", "credits": "2x"}),
    ("MODEL_CLAUDE_3_7_SONNET_20250219", {"provider": "Anthropic", "name": "Claude 3.7 Sonnet", "tier": "standard", "credits": "1x"}),
    ("MODEL_CLAUDE_3_5_SONNET_20241022", {"provider": "Anthropic", "name": "Claude 3.5 Sonnet", "tier": "standard", "credits": "1x"}),
    ("MODEL_CLAUDE_3_5_HAIKU_20241022", {"provider": "Anthropic", "name": "Claude 3.5 Haiku", "tier": "lite", "credits": "0.5x"}),

    # OpenAI/GPT
    ("MODEL_CHAT_GPT_5_4", {"provider": "OpenAI", "name": "GPT-5.4", "tier": "premium", "credits": "1x"}),
    ("MODEL_CHAT_GPT_5_3_CODEX_SPARK", {"provider": "OpenAI", "name": "GPT-5.3 Codex Spark", "tier": "standard", "credits": "1x"}),
    ("MODEL_CHAT_GPT_5_3_CODEX", {"provider": "OpenAI", "name": "GPT-5.3 Codex", "tier": "standard", "credits": "1x"}),
    ("MODEL_CHAT_GPT_5_2", {"provider": "OpenAI", "name": "GPT-5.2", "tier": "premium", "credits": "2x"}),
    ("MODEL_CHAT_GPT_5", {"provider": "OpenAI", "name": "GPT-5", "tier": "premium", "credits": "2x"}),
    ("MODEL_CHAT_GPT_5_HIGH", {"provider": "OpenAI", "name": "GPT-5 High", "tier": "premium", "credits": "4x"}),
    ("MODEL_CHAT_GPT_5_LOW", {"provider": "OpenAI", "name": "GPT-5 Low", "tier": "standard", "credits": "1x"}),
    ("MODEL_CHAT_GPT_5_CODEX", {"provider": "OpenAI", "name": "GPT-5 Codex", "tier": "premium", "credits": "2x"}),
    ("MODEL_CHAT_GPT_4_5", {"provider": "OpenAI", "name": "GPT-4.5", "tier": "premium", "credits": "4x"}),
    ("MODEL_CHAT_GPT_4_1_2025_04_14", {"provider": "OpenAI", "name": "GPT-4.1", "tier": "standard", "credits": "1x"}),
    ("MODEL_CHAT_GPT_4_1_MINI_2025_04_14", {"provider": "OpenAI", "name": "GPT-4.1 Mini", "tier": "lite", "credits": "0.5x"}),
    ("MODEL_CHAT_GPT_4O_2024_08_06", {"provider": "OpenAI", "name": "GPT-4o", "tier": "standard", "credits": "1x"}),
    ("MODEL_CHAT_GPT_4O_MINI_2024_07_18", {"provider": "OpenAI", "name": "GPT-4o Mini", "tier": "lite", "credits": "0.25x"}),
    ("MODEL_CHAT_O3", {"provider": "OpenAI", "name": "O3", "tier": "premium", "credits": "4x"}),
    ("MODEL_CHAT_O3_MINI", {"provider": "OpenAI", "name": "O3 Mini", "tier": "standard", "credits": "1x"}),
    ("MODEL_CHAT_O4_MINI", {"provider": "OpenAI", "name": "O4 Mini", "tier": "standard", "credits": "1x"}),
    ("MODEL_O3_PRO_2025_06_10", {"provider": "OpenAI", "name": "O3 Pro", "tier": "premium", "credits": "20x"}),
    ("MODEL_CODEX_MINI_LATEST", {"provider": "OpenAI", "name": "Codex Mini", "tier": "standard", "credits": "1x"}),

    # Google/Gemini
    ("MODEL_GOOGLE_GEMINI_3_1_PRO_HIGH", {"provider": "Google", "name": "Gemini 3.1 Pro", "tier": "premium", "credits": "1x"}),
    ("MODEL_GOOGLE_GEMINI_3_0_PRO_HIGH", {"provider": "Google", "name": "Gemini 3.0 Pro", "tier": "premium", "credits": "2x"}),
    ("MODEL_GOOGLE_GEMINI_3_0_FLASH_HIGH", {"provider": "Google", "name": "Gemini 3.0 Flash", "tier": "standard", "credits": "1x"}),
    ("MODEL_GOOGLE_GEMINI_2_5_PRO", {"provider": "Google", "name": "Gemini 2.5 Pro", "tier": "premium", "credits": "2x"}),
    ("MODEL_GOOGLE_GEMINI_2_5_FLASH", {"provider": "Google", "name": "Gemini 2.5 Flash", "tier": "lite", "credits": "0.5x"}),
    ("MODEL_GOOGLE_GEMINI_2_0_FLASH", {"provider": "Google", "name": "Gemini 2.0 Flash", "tier": "lite", "credits": "0.25x"}),

    # DeepSeek
    ("MODEL_DEEPSEEK_V3_2", {"provider": "DeepSeek", "name": "DeepSeek V3.2", "tier": "standard", "credits": "1x"}),
    ("MODEL_DEEPSEEK_R1", {"provider": "DeepSeek", "name": "DeepSeek R1", "tier": "standard", "credits": "1x"}),

    # xAI/Grok
    ("MODEL_XAI_GROK_3", {"provider": "xAI", "name": "Grok 3", "tier": "premium", "credits": "2x"}),
    ("MODEL_XAI_GROK_3_MINI_REASONING", {"provider": "xAI", "name": "Grok 3 Mini", "tier": "standard", "credits": "1x"}),
    ("MODEL_XAI_GROK_CODE_FAST", {"provider": "xAI", "name": "Grok Code Fast", "tier": "lite", "credits": "0.5x"}),

    # Qwen/阿里
    ("MODEL_QWEN_3_CODER_480B_INSTRUCT", {"provider": "Qwen", "name": "Qwen 3 Coder 480B", "tier": "standard", "credits": "1x"}),
    ("MODEL_QWEN_3_235B_INSTRUCT", {"provider": "Qwen", "name": "Qwen 3 235B", "tier": "standard", "credits": "1x"}),

    # Kimi/Moonshot
    ("MODEL_KIMI_K2_5", {"provider": "Moonshot", "name": "Kimi K2.5", "tier": "standard", "credits": "1x"}),
    ("MODEL_KIMI_K2", {"provider": "Moonshot", "name": "Kimi K2", "tier": "standard", "credits": "1x"}),
    ("MODEL_KIMI_K2_THINKING", {"provider": "Moonshot", "name": "Kimi K2 (Thinking)", "tier": "standard", "credits": "1x"}),

    # GLM/智谱
    ("MODEL_GLM_5", {"provider": "Zhipu", "name": "GLM-5", "tier": "premium", "credits": "1x"}),
    ("MODEL_GLM_4_7", {"provider": "Zhipu", "name": "GLM 4.7", "tier": "standard", "credits": "1x"}),
    ("MODEL_GLM_4_6", {"provider": "Zhipu", "name": "GLM 4.6", "tier": "standard", "credits": "1x"}),
    ("MODEL_GLM_4_5", {"provider": "Zhipu", "name": "GLM 4.5", "tier": "standard", "credits": "1x"}),

    # MiniMax
    ("MODEL_MINIMAX_M2_5", {"provider": "MiniMax", "name": "Minimax M2.5", "tier": "standard", "credits": "1x"}),
    ("MODEL_MINIMAX_M2_1", {"provider": "MiniMax", "name": "MiniMax M2.1", "tier": "standard", "credits": "1x"}),

    # Meta/Llama
    ("MODEL_LLAMA_3_3_70B_INSTRUCT", {"provider": "Meta", "name": "Llama 3.3 70B", "tier": "lite", "credits": "0.25x"}),

    # Windsurf自研
    ("MODEL_SWE_1_5", {"provider": "Windsurf", "name": "SWE-1.5", "tier": "free", "credits": "0x"}),
    ("MODEL_SWE_1_5_FAST", {"provider": "Windsurf", "name": "SWE-1.5 Fast", "tier": "free", "credits": "0.5x"}),
    ("MODEL_SWE_1_6", {"provider": "Windsurf", "name": "SWE-1.6", "tier": "free", "credits": "0x"}),
    ("MODEL_SWE_1_6_FAST", {"provider": "Windsurf", "name": "SWE-1.6 Fast", "tier": "free", "credits": "0x"}),
])

# Protobuf枚举值（从workbench.desktop.main.js逆向提取）
MODEL_ENUM_VALUES = {
    "MODEL_UNSPECIFIED": 0,
    "MODEL_CHAT_GPT_4": 30, "MODEL_CHAT_GPT_4O_2024_05_13": 71,
    "MODEL_CHAT_GPT_4O_2024_08_06": 109, "MODEL_CHAT_GPT_4O_MINI_2024_07_18": 113,
    "MODEL_CHAT_GPT_4_5": 228, "MODEL_CHAT_GPT_4_1_2025_04_14": 259,
    "MODEL_CHAT_GPT_4_1_MINI_2025_04_14": 260, "MODEL_CHAT_GPT_4_1_NANO_2025_04_14": 261,
    "MODEL_CHAT_GPT_5": 340, "MODEL_CHAT_GPT_5_LOW": 339, "MODEL_CHAT_GPT_5_HIGH": 341,
    "MODEL_CHAT_GPT_5_CODEX": 346,
    "MODEL_CHAT_O3_MINI": 207, "MODEL_CHAT_O3": 262, "MODEL_CHAT_O4_MINI": 264,
    "MODEL_O3_PRO_2025_06_10": 294,
    "MODEL_CODEX_MINI_LATEST": 287,
    "MODEL_GPT_5_2_LOW": 400, "MODEL_GPT_5_2_MEDIUM": 401, "MODEL_GPT_5_2_HIGH": 402,
    "MODEL_GPT_5_2_CODEX_LOW": 422, "MODEL_GPT_5_2_CODEX_HIGH": 424,
    "MODEL_CLAUDE_3_5_SONNET_20241022": 166, "MODEL_CLAUDE_3_5_HAIKU_20241022": 171,
    "MODEL_CLAUDE_3_7_SONNET_20250219": 226, "MODEL_CLAUDE_3_7_SONNET_20250219_THINKING": 227,
    "MODEL_CLAUDE_4_SONNET": 281, "MODEL_CLAUDE_4_SONNET_THINKING": 282,
    "MODEL_CLAUDE_4_OPUS": 290, "MODEL_CLAUDE_4_OPUS_THINKING": 291,
    "MODEL_CLAUDE_4_1_OPUS": 328, "MODEL_CLAUDE_4_1_OPUS_THINKING": 329,
    "MODEL_CLAUDE_4_5_SONNET": 353, "MODEL_CLAUDE_4_5_SONNET_THINKING": 354,
    "MODEL_CLAUDE_4_5_SONNET_1M": 370,
    "MODEL_CLAUDE_4_5_OPUS": 391, "MODEL_CLAUDE_4_5_OPUS_THINKING": 392,
    "MODEL_GOOGLE_GEMINI_2_0_FLASH": 184, "MODEL_GOOGLE_GEMINI_2_5_PRO": 246,
    "MODEL_GOOGLE_GEMINI_2_5_FLASH": 312,
    "MODEL_GOOGLE_GEMINI_3_0_PRO_HIGH": 379, "MODEL_GOOGLE_GEMINI_3_0_FLASH_HIGH": 416,
    "MODEL_DEEPSEEK_V3": 205, "MODEL_DEEPSEEK_R1": 206, "MODEL_DEEPSEEK_V3_2": 409,
    "MODEL_XAI_GROK_3": 217, "MODEL_XAI_GROK_3_MINI_REASONING": 234,
    "MODEL_XAI_GROK_CODE_FAST": 345,
    "MODEL_QWEN_3_235B_INSTRUCT": 324, "MODEL_QWEN_3_CODER_480B_INSTRUCT": 325,
    "MODEL_KIMI_K2": 323, "MODEL_KIMI_K2_THINKING": 394,
    "MODEL_GLM_4_5": 342, "MODEL_GLM_4_6": 356, "MODEL_GLM_4_7": 417,
    "MODEL_MINIMAX_M2_1": 419,
    "MODEL_LLAMA_3_3_70B_INSTRUCT": 208,
    "MODEL_SWE_1_5": 359, "MODEL_SWE_1_5_THINKING": 369,
    "MODEL_SWE_1_6": 420, "MODEL_SWE_1_6_FAST": 421,
}

# 八卦 × 能力维度
BAGUA_DIMENSIONS = {
    "☰乾_编码": "coding",
    "☱兑_多模态": "multimodal",
    "☲离_速度": "speed",
    "☳震_成本": "cost",
    "☴巽_工具": "tools",
    "☵坎_推理": "reasoning",
    "☶艮_安全": "safety",
    "☷坤_上下文": "context",
}


# ==================== 工具函数 ====================

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"INFO": "ℹ", "OK": "✅", "WARN": "⚠", "ERR": "❌", "TEST": "🧪"}.get(level, "·")
    print(f"[{ts}] {icon} {msg}")


def tcp_probe(host, port, timeout=3):
    """TCP端口探测"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        s.close()
        return False


def https_request(host, port, path, body=None, headers=None, timeout=10):
    """HTTPS请求（跳过证书验证）"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
    hdrs = headers or {}
    method = "POST" if body is not None else "GET"
    try:
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        return resp.status, resp.reason, dict(resp.getheaders()), resp.read()
    except Exception as e:
        return 0, str(e), {}, b""
    finally:
        conn.close()


def grpc_web_call(host, port, service, method, payload=b"", timeout=10):
    """gRPC-Web调用（通过HTTP/1.1）"""
    path = f"/{service}/{method}"
    # gRPC消息格式: [1B compressed=0][4B length][protobuf payload]
    grpc_msg = b"\x00" + struct.pack(">I", len(payload)) + payload
    headers = {
        "Content-Type": "application/grpc-web+proto",
        "x-grpc-web": "1",
        "te": "trailers",
    }
    status, reason, resp_headers, body = https_request(host, port, path, grpc_msg, headers, timeout)
    return {
        "status": status,
        "reason": reason,
        "headers": resp_headers,
        "body": body,
        "content_type": resp_headers.get("content-type", ""),
        "grpc_status": resp_headers.get("grpc-status", ""),
    }


# ==================== Protobuf编码器（手动实现，无外部依赖） ====================

def pb_varint(value):
    """编码varint"""
    if value == 0:
        return b"\x00"
    result = b""
    while value > 0x7f:
        result += bytes([0x80 | (value & 0x7f)])
        value >>= 7
    result += bytes([value & 0x7f])
    return result


def pb_string(field_number, value):
    """编码string字段 (wire type 2)"""
    data = value.encode("utf-8")
    return pb_varint((field_number << 3) | 2) + pb_varint(len(data)) + data


def pb_message(field_number, data):
    """编码嵌套message字段 (wire type 2)"""
    return pb_varint((field_number << 3) | 2) + pb_varint(len(data)) + data


def pb_enum(field_number, value):
    """编码enum字段 (wire type 0 = varint)"""
    return pb_varint((field_number << 3) | 0) + pb_varint(value)


def pb_uint64(field_number, value):
    """编码uint64字段 (wire type 0)"""
    return pb_varint((field_number << 3) | 0) + pb_varint(value)


def pb_bool(field_number, value):
    """编码bool字段 (wire type 0)"""
    return pb_varint((field_number << 3) | 0) + pb_varint(1 if value else 0)


def pb_decode_varint(data, offset):
    """解码varint，返回(value, new_offset)"""
    value = 0
    shift = 0
    while offset < len(data):
        b = data[offset]
        value |= (b & 0x7f) << shift
        offset += 1
        if not (b & 0x80):
            break
        shift += 7
    return value, offset


def pb_decode_fields(data):
    """解码protobuf消息，返回[(field_number, wire_type, value)]"""
    fields = []
    i = 0
    while i < len(data):
        try:
            tag, i = pb_decode_varint(data, i)
            field_number = tag >> 3
            wire_type = tag & 7
            if wire_type == 0:  # varint
                value, i = pb_decode_varint(data, i)
            elif wire_type == 2:  # length-delimited
                length, i = pb_decode_varint(data, i)
                value = data[i:i + length]
                i += length
            elif wire_type == 1:  # 64-bit
                value = data[i:i + 8]
                i += 8
            elif wire_type == 5:  # 32-bit
                value = data[i:i + 4]
                i += 4
            else:
                break
            fields.append((field_number, wire_type, value))
        except (IndexError, ValueError):
            break
    return fields


def pb_extract_text(data, max_depth=5):
    """递归提取protobuf消息中的所有文本字符串"""
    if max_depth <= 0 or not data:
        return []
    texts = []
    fields = pb_decode_fields(data)
    for fn, wt, val in fields:
        if wt == 2 and isinstance(val, (bytes, bytearray)):
            # 尝试解码为UTF-8文本
            try:
                text = val.decode("utf-8")
                if text and all(c.isprintable() or c in '\n\r\t' for c in text):
                    texts.append(text)
            except (UnicodeDecodeError, ValueError):
                pass
            # 也尝试解析为嵌套message
            nested = pb_extract_text(val, max_depth - 1)
            texts.extend(nested)
    return texts


# ==================== gRPC-web模型调用器 ====================

def build_metadata():
    """构建请求元数据 (Metadata protobuf)"""
    meta = b""
    meta += pb_string(1, "windsurf")           # ide_name
    meta += pb_string(2, "2.0.0")              # extension_version
    # field 3 (api_key) - 留空，CFW自动注入
    meta += pb_string(4, "en")                 # locale
    meta += pb_string(5, "windows_x64")        # os
    meta += pb_string(7, "1.100.0")            # ide_version
    meta += pb_uint64(9, int(time.time() * 1000000))  # request_id
    meta += pb_string(10, str(uuid.uuid4()))    # session_id
    return meta


def build_chat_message(role, content):
    """构建ChatMessage protobuf (role=1:USER, 2:SYSTEM)"""
    msg = b""
    msg += pb_enum(1, role)       # role enum
    msg += pb_string(3, content)  # content
    return msg


def build_chat_request(model_name, prompt, model_enum_value=0):
    """构建GetChatMessageRequest protobuf"""
    request = b""
    # field 1: metadata
    request += pb_message(1, build_metadata())
    # field 2: chat_messages (repeated - user message)
    request += pb_message(2, build_chat_message(1, prompt))  # role=1=USER
    # field 4: chat_model (enum varint) - if known
    if model_enum_value > 0:
        request += pb_enum(4, model_enum_value)
    # field 5: chat_model_name (string)
    request += pb_string(5, model_name)
    return request


def parse_grpc_web_response(body):
    """解析gRPC-web流式响应，提取所有文本内容"""
    if not body:
        return {"texts": [], "frames": 0, "error": None, "raw_fields": []}

    texts = []
    raw_fields = []
    frames = 0
    i = 0

    while i + 5 <= len(body):
        # gRPC frame: [1B flag][4B length BE]
        flag = body[i]
        frame_len = struct.unpack(">I", body[i + 1:i + 5])[0]
        i += 5

        if i + frame_len > len(body):
            break

        frame_data = body[i:i + frame_len]
        i += frame_len
        frames += 1

        if flag == 0x80:
            # Trailer frame - contains status info
            try:
                trailer_text = frame_data.decode("utf-8", errors="replace")
                if "grpc-status" in trailer_text:
                    raw_fields.append(("trailer", trailer_text))
            except Exception:
                pass
            continue

        # Data frame - parse protobuf
        extracted = pb_extract_text(frame_data, max_depth=4)
        for t in extracted:
            if len(t) > 2 and t not in texts:
                texts.append(t)

        # Also store raw decoded fields for debugging
        fields = pb_decode_fields(frame_data)
        for fn, wt, val in fields:
            raw_fields.append((fn, wt, val[:100] if isinstance(val, bytes) else val))

    return {"texts": texts, "frames": frames, "error": None, "raw_fields": raw_fields}


def test_cfw_model(model_name, prompt=None, timeout=30):
    """通过CFW代理测试单个模型的gRPC-web调用"""
    if prompt is None:
        prompt = "Write a Python function that returns 'hello world'. Reply with ONLY the code, no explanation."

    model_enum_value = MODEL_ENUM_VALUES.get(model_name, 0)
    payload = build_chat_request(model_name, prompt, model_enum_value)

    start_time = time.time()
    try:
        result = grpc_web_call(CFW_HOST, CFW_PORT,
                               "exa.chat_pb.ChatService", "GetChatMessage",
                               payload, timeout=timeout)
        elapsed = time.time() - start_time

        parsed = parse_grpc_web_response(result["body"])

        # 判断成功条件
        grpc_status = result.get("grpc_status", "")
        has_content = len(parsed["texts"]) > 0
        content_preview = ""
        if parsed["texts"]:
            content_preview = parsed["texts"][0][:200]

        # 检查trailer中的grpc-status
        trailer_status = None
        for kind, data in parsed.get("raw_fields", []):
            if kind == "trailer" and "grpc-status:" in str(data):
                import re as _re
                st = _re.search(r'grpc-status:\s*(\d+)', str(data))
                if st:
                    trailer_status = int(st.group(1))

        status = "success" if (result["status"] == 200 and
                               (has_content or trailer_status == 0)) else "fail"

        return {
            "model": model_name,
            "enum_value": model_enum_value,
            "status": status,
            "http_status": result["status"],
            "grpc_status": grpc_status or str(trailer_status),
            "frames": parsed["frames"],
            "texts_count": len(parsed["texts"]),
            "content_preview": content_preview,
            "elapsed_ms": int(elapsed * 1000),
            "body_size": len(result["body"]),
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "model": model_name,
            "enum_value": model_enum_value,
            "status": "error",
            "http_status": 0,
            "grpc_status": "",
            "frames": 0,
            "texts_count": 0,
            "content_preview": "",
            "elapsed_ms": int(elapsed * 1000),
            "body_size": 0,
            "error": str(e),
        }


def test_all_cfw_models():
    """通过CFW代理测试所有已知模型"""
    log("=" * 60)
    log("路径A+: CFW反代 → 全模型gRPC-web调用测试", "TEST")

    # 先做TCP探测
    if not tcp_probe(CFW_HOST, CFW_PORT, timeout=3):
        log("CFW代理端口443不可达，跳过全模型测试", "ERR")
        return []

    results = []
    # 选择代表性模型进行测试（避免超时，按tier分组）
    test_models = [
        # Free tier (最可能成功)
        "MODEL_SWE_1_5", "MODEL_SWE_1_6",
        # Lite tier
        "MODEL_CLAUDE_3_5_HAIKU_20241022", "MODEL_GOOGLE_GEMINI_2_0_FLASH",
        "MODEL_CHAT_GPT_4O_MINI_2024_07_18",
        # Standard tier
        "MODEL_DEEPSEEK_V3_2", "MODEL_KIMI_K2",
        "MODEL_QWEN_3_235B_INSTRUCT", "MODEL_GLM_4_7",
        # Premium tier
        "MODEL_CLAUDE_4_5_SONNET", "MODEL_CHAT_GPT_5",
        "MODEL_GOOGLE_GEMINI_3_0_PRO_HIGH", "MODEL_XAI_GROK_3",
        # Thinking models
        "MODEL_CLAUDE_4_5_SONNET_THINKING", "MODEL_CLAUDE_4_5_OPUS_THINKING",
        # Codex/Reasoning
        "MODEL_CHAT_GPT_5_CODEX", "MODEL_CODEX_MINI_LATEST",
    ]

    prompt = "def fib(n): # fibonacci with memoization, complete this function"

    for i, model in enumerate(test_models):
        log(f"  [{i + 1}/{len(test_models)}] {model}...", "INFO")
        r = test_cfw_model(model, prompt, timeout=15)

        status_icon = "✅" if r["status"] == "success" else "❌" if r["status"] == "fail" else "⚠️"
        detail = f"http={r['http_status']} grpc={r['grpc_status']} body={r['body_size']}B frames={r['frames']} {r['elapsed_ms']}ms"
        if r["content_preview"]:
            detail += f" → {r['content_preview'][:80]}"
        if r["error"]:
            detail += f" err={r['error'][:60]}"
        log(f"    {status_icon} {detail}", "INFO")
        results.append(r)

    # 统计
    success = sum(1 for r in results if r["status"] == "success")
    fail = sum(1 for r in results if r["status"] == "fail")
    error = sum(1 for r in results if r["status"] == "error")
    log(f"  CFW模型测试完成: {success}成功 {fail}失败 {error}错误 / {len(results)}总计", "OK")

    return results


def get_language_server_info():
    """从进程命令行提取语言服务器信息"""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'language_server' } | "
             "Select-Object ProcessId, CommandLine | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if not isinstance(data, list):
                data = [data]
            servers = []
            for proc in data:
                cmd = proc.get("CommandLine", "")
                info = {
                    "pid": proc.get("ProcessId"),
                    "api_server": _extract_arg(cmd, "--api_server_url"),
                    "inference_api": _extract_arg(cmd, "--inference_api_server_url"),
                    "ext_port": _extract_arg(cmd, "--extension_server_port"),
                    "csrf_token": _extract_arg(cmd, "--csrf_token"),
                    "workspace_id": _extract_arg(cmd, "--workspace_id"),
                    "version": _extract_arg(cmd, "--windsurf_version"),
                }
                servers.append(info)
            return servers
    except Exception as e:
        log(f"获取语言服务器信息失败: {e}", "WARN")
    return []


def _extract_arg(cmd, flag):
    """从命令行提取参数值"""
    parts = cmd.split()
    for i, p in enumerate(parts):
        if p == flag and i + 1 < len(parts):
            return parts[i + 1]
    return None


def get_listening_ports():
    """获取语言服务器监听的端口"""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'language_server' } | "
             "ForEach-Object { $_.ProcessId } | ForEach-Object { "
             "Get-NetTCPConnection -OwningProcess $_ -State Listen -ErrorAction SilentlyContinue "
             "} | Select-Object LocalPort | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if not isinstance(data, list):
                data = [data]
            return [d["LocalPort"] for d in data if d.get("LocalPort")]
    except Exception:
        pass
    return []


# ==================== 测试路径A: CFW代理 → Codeium API ====================

def test_cfw_proxy():
    """测试CFW代理连通性"""
    log("路径A: 探测CFW代理 (127.0.0.1:443)...", "TEST")
    results = {"available": False, "tests": []}

    # 1. TCP探测
    if not tcp_probe(CFW_HOST, CFW_PORT, timeout=3):
        log("CFW代理端口443不可达", "ERR")
        results["tests"].append({"name": "tcp_probe", "status": "fail", "detail": "port closed"})
        return results

    results["tests"].append({"name": "tcp_probe", "status": "pass"})
    log("TCP连接成功", "OK")

    # 2. HTTPS探测
    status, reason, _, body = https_request(CFW_HOST, CFW_PORT, "/")
    results["tests"].append({"name": "https_get", "status": "pass" if status == 200 else "fail",
                             "detail": f"{status} {reason}"})
    log(f"HTTPS GET /: {status} {reason}", "OK" if status == 200 else "WARN")

    # 3. gRPC-Web Heartbeat
    grpc_result = grpc_web_call(CFW_HOST, CFW_PORT,
                                "exa.language_server_pb.LanguageServerService", "Heartbeat")
    hb_ok = grpc_result["status"] == 200
    results["tests"].append({"name": "grpc_heartbeat", "status": "pass" if hb_ok else "fail",
                             "detail": f'{grpc_result["status"]} ct={grpc_result["content_type"]}'})
    log(f"gRPC Heartbeat: {grpc_result['status']} {grpc_result['content_type']}", "OK" if hb_ok else "WARN")

    # 4. 探测各种gRPC服务方法
    grpc_methods = [
        ("exa.seat_management_pb.SeatManagementService", "GetUser"),
        ("exa.api_server_pb.ApiServerService", "GetApiKeySummary"),
        ("exa.chat_pb.ChatService", "GetChatMessage"),
        ("exa.language_server_pb.LanguageServerService", "GetProcesses"),
    ]
    for svc, method in grpc_methods:
        try:
            r = grpc_web_call(CFW_HOST, CFW_PORT, svc, method, timeout=5)
            status_str = "pass" if r["status"] == 200 else f"fail({r['status']})"
            body_len = len(r["body"])
            grpc_st = r.get("grpc_status", "?")
            results["tests"].append({
                "name": f"grpc_{method}",
                "status": status_str,
                "detail": f"status={r['status']} body={body_len}B grpc_status={grpc_st}"
            })
            log(f"  {svc}/{method}: {r['status']} body={body_len}B", "INFO")
        except Exception as e:
            results["tests"].append({"name": f"grpc_{method}", "status": "error", "detail": str(e)})

    results["available"] = any(t["status"] == "pass" for t in results["tests"])
    return results


# ==================== 测试路径B: 直接模型提供商API ====================

def test_provider_api(provider, api_url, api_key, model_id, prompt, proxy=None):
    """测试单个模型提供商API"""
    start_time = time.time()
    result = {
        "provider": provider,
        "model": model_id,
        "status": "unknown",
        "latency_ms": 0,
        "response_preview": "",
        "tokens": 0,
        "error": None,
    }

    try:
        import urllib.request
        import urllib.error

        data = json.dumps({
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0,
        }).encode()

        req = urllib.request.Request(api_url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")

        # SSL context: skip verification when using proxy (fixes SSL EOF errors)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        https_handler = urllib.request.HTTPSHandler(context=ssl_ctx)

        if proxy:
            handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
            opener = urllib.request.build_opener(handler, https_handler)
        else:
            opener = urllib.request.build_opener(https_handler)

        with opener.open(req, timeout=30) as resp:
            body = json.loads(resp.read())
            elapsed = (time.time() - start_time) * 1000

            content = ""
            if "choices" in body and body["choices"]:
                msg = body["choices"][0].get("message", {})
                content = msg.get("content", "")
            elif "message" in body:
                content = body["message"].get("content", "")

            result["status"] = "success"
            result["latency_ms"] = round(elapsed)
            result["response_preview"] = content[:200]
            result["tokens"] = body.get("usage", {}).get("total_tokens", 0)

    except urllib.error.HTTPError as e:
        result["status"] = "http_error"
        result["error"] = f"{e.code} {e.reason}"
        try:
            result["error"] += f" - {e.read().decode()[:200]}"
        except Exception:
            pass
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"

    result["latency_ms"] = round((time.time() - start_time) * 1000)
    return result


def test_anthropic_api(api_key, model_id, prompt, proxy=None):
    """Anthropic专用API测试（不同于OpenAI格式）"""
    import urllib.request
    import urllib.error
    start_time = time.time()
    result = {"provider": "Anthropic", "model": model_id, "status": "unknown",
              "latency_ms": 0, "response_preview": "", "tokens": 0, "error": None}
    try:
        data = json.dumps({
            "model": model_id,
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-api-key", api_key)
        req.add_header("anthropic-version", "2023-06-01")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        https_handler = urllib.request.HTTPSHandler(context=ssl_ctx)
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"https": proxy, "http": proxy}), https_handler)
        else:
            opener = urllib.request.build_opener(https_handler)
        with opener.open(req, timeout=30) as resp:
            body = json.loads(resp.read())
            content = ""
            for block in body.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            result["status"] = "success"
            result["latency_ms"] = round((time.time() - start_time) * 1000)
            result["response_preview"] = content[:200]
            result["tokens"] = body.get("usage", {}).get("input_tokens", 0) + body.get("usage", {}).get("output_tokens", 0)
    except urllib.error.HTTPError as e:
        result["status"] = "http_error"
        result["error"] = f"{e.code} {e.reason}"
        try:
            result["error"] += f" - {e.read().decode()[:200]}"
        except Exception:
            pass
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    result["latency_ms"] = round((time.time() - start_time) * 1000)
    return result


def test_all_providers():
    """测试所有可用的模型提供商API"""
    log("路径B: 直接模型提供商API测试...", "TEST")
    results = []

    # 检测代理可用性（降级逻辑：代理不可用→直连）
    proxy = HTTP_PROXY
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 7890))
        s.close()
        log("  Clash代理可用，国外API走代理", "OK")
    except Exception:
        proxy = None
        log("  Clash代理不可用，所有API走直连（国外API可能失败）", "WARN")

    # DeepSeek (免费额度)
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        for model in ["deepseek-chat", "deepseek-reasoner"]:
            log(f"  测试 DeepSeek {model}...")
            r = test_provider_api("DeepSeek", "https://api.deepseek.com/chat/completions",
                                  deepseek_key, model, TEST_PROMPT, proxy=proxy)
            results.append(r)
            log(f"    {r['status']} {r['latency_ms']}ms", "OK" if r["status"] == "success" else "ERR")
    else:
        log("  DeepSeek: 无API Key (DEEPSEEK_API_KEY)", "WARN")

    # OpenAI (如果有key)
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        for model in ["gpt-4o-mini", "gpt-4o"]:
            log(f"  测试 OpenAI {model}...")
            r = test_provider_api("OpenAI", "https://api.openai.com/v1/chat/completions",
                                  openai_key, model, TEST_PROMPT, proxy=proxy)
            results.append(r)
            log(f"    {r['status']} {r['latency_ms']}ms", "OK" if r["status"] == "success" else "ERR")
    else:
        log("  OpenAI: 无API Key (OPENAI_API_KEY)", "WARN")

    # Anthropic (如果有key) — 特殊格式: x-api-key + anthropic-version
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        for model in ["claude-3-5-haiku-20241022"]:
            log(f"  测试 Anthropic {model}...")
            r = test_anthropic_api(anthropic_key, model, TEST_PROMPT, proxy=proxy)
            results.append(r)
    else:
        log("  Anthropic: 无API Key (ANTHROPIC_API_KEY)", "WARN")

    # HuggingFace (有token)
    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        # 尝试从secrets.env读取
        secrets_file = PROJECT_ROOT / "secrets.env"
        if secrets_file.exists():
            for line in secrets_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("HF_TOKEN="):
                    hf_token = line.split("=", 1)[1].strip()
                    break

    if hf_token:
        # HF镜像(hf-mirror.com)仅下载用，推理API必须走官方endpoint+代理
        log(f"  测试 HuggingFace Inference API (需代理)...")
        r = test_provider_api(
            "HuggingFace",
            "https://router.huggingface.co/novita/v3/openai/chat/completions",
            hf_token, "meta-llama/llama-3.1-8b-instruct", TEST_PROMPT, proxy=proxy
        )
        results.append(r)
        log(f"    {r['status']} {r['latency_ms']}ms", "OK" if r["status"] == "success" else "ERR")
    else:
        log("  HuggingFace: 无Token", "WARN")

    # 阿里云 DashScope (Qwen直调)
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if dashscope_key:
        log(f"  测试 DashScope (Qwen)...")
        r = test_provider_api(
            "DashScope", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            dashscope_key, "qwen-plus", TEST_PROMPT_CN
        )
        results.append(r)
    else:
        log("  DashScope: 无API Key (DASHSCOPE_API_KEY)", "WARN")

    # 智谱AI (GLM直调)
    zhipu_key = os.environ.get("ZHIPU_API_KEY", "")
    if zhipu_key:
        log(f"  测试 智谱AI (GLM)...")
        r = test_provider_api(
            "Zhipu", "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            zhipu_key, "glm-4-flash", TEST_PROMPT_CN
        )
        results.append(r)
    else:
        log("  智谱AI: 无API Key (ZHIPU_API_KEY)", "WARN")

    # SiliconFlow (免费额度, 国内直连)
    sf_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if sf_key:
        for model in ["Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"]:
            log(f"  测试 SiliconFlow {model}...")
            r = test_provider_api(
                "SiliconFlow", "https://api.siliconflow.cn/v1/chat/completions",
                sf_key, model, TEST_PROMPT_CN
            )
            results.append(r)
            log(f"    {r['status']} {r['latency_ms']}ms", "OK" if r["status"] == "success" else "ERR")
    else:
        log("  SiliconFlow: 无API Key (SILICONFLOW_API_KEY)", "WARN")

    # Google Gemini (免费API, generativelanguage endpoint)
    google_key = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
    if google_key:
        log(f"  测试 Google Gemini (免费API)...")
        r = test_gemini_api(google_key, "gemini-2.0-flash", TEST_PROMPT, proxy=proxy)
        results.append(r)
        log(f"    {r['status']} {r['latency_ms']}ms", "OK" if r["status"] == "success" else "ERR")
    else:
        log("  Google Gemini: 无API Key (GOOGLE_API_KEY/GEMINI_API_KEY)", "WARN")

    return results


def test_gemini_api(api_key, model_id, prompt, proxy=None):
    """Google Gemini专用API测试（generateContent endpoint）"""
    import urllib.request
    import urllib.error
    start_time = time.time()
    result = {"provider": "Google", "model": model_id, "status": "unknown",
              "latency_ms": 0, "response_preview": "", "tokens": 0, "error": None}
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        data = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 200, "temperature": 0},
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        https_handler = urllib.request.HTTPSHandler(context=ssl_ctx)
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"https": proxy, "http": proxy}), https_handler)
        else:
            opener = urllib.request.build_opener(https_handler)
        with opener.open(req, timeout=30) as resp:
            body = json.loads(resp.read())
            content = ""
            for cand in body.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    content += part.get("text", "")
            result["status"] = "success"
            result["latency_ms"] = round((time.time() - start_time) * 1000)
            result["response_preview"] = content[:200]
            usage = body.get("usageMetadata", {})
            result["tokens"] = usage.get("totalTokenCount", 0)
    except urllib.error.HTTPError as e:
        result["status"] = "http_error"
        result["error"] = f"{e.code} {e.reason}"
        try:
            result["error"] += f" - {e.read().decode()[:200]}"
        except Exception:
            pass
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    result["latency_ms"] = round((time.time() - start_time) * 1000)
    return result


# ==================== 测试路径C: 本地语言服务器 ====================

def test_language_server():
    """探测本地语言服务器"""
    log("路径C: 本地语言服务器探测...", "TEST")
    results = {"servers": [], "ports": [], "grpc_tests": []}

    # 1. 获取语言服务器进程信息
    servers = get_language_server_info()
    results["servers"] = servers
    for s in servers:
        log(f"  PID={s['pid']} ext_port={s['ext_port']} api={s['api_server']} ver={s['version']}")

    # 2. 获取监听端口
    ports = get_listening_ports()
    results["ports"] = ports
    log(f"  监听端口: {ports}")

    # 3. 探测每个端口 (gRPC over HTTP/2 需要h2库)
    for port in ports[:5]:  # 最多测5个
        # 尝试HTTP/1.1 Connect协议
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            conn.request("POST",
                         "/exa.language_server_pb.LanguageServerService/Heartbeat",
                         body=b"\x00\x00\x00\x00\x00",
                         headers={"Content-Type": "application/json",
                                  "connect-protocol-version": "1"})
            r = conn.getresponse()
            results["grpc_tests"].append({
                "port": port, "protocol": "connect",
                "status": r.status, "body_len": len(r.read())
            })
            log(f"  Port {port} Connect: {r.status}", "OK" if r.status == 200 else "WARN")
            conn.close()
        except Exception as e:
            results["grpc_tests"].append({
                "port": port, "protocol": "connect",
                "status": 0, "error": str(e)[:100]
            })
            log(f"  Port {port}: {type(e).__name__}", "WARN")

    return results


# ==================== 综合环境探测 ====================

def detect_environment():
    """探测完整运行环境"""
    log("=" * 60)
    log("Windsurf 全模型后端测试 v2.0")
    log("=" * 60)

    env = {
        "timestamp": datetime.now().isoformat(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "windsurf_js_exists": WINDSURF_JS.exists(),
        "codeium_dir_exists": CODEIUM_DIR.exists(),
        "cfw_running": False,
        "language_servers": [],
        "proxy_available": False,
        "api_keys": {},
    }

    # 检查CFW
    env["cfw_running"] = tcp_probe(CFW_HOST, CFW_PORT)
    log(f"CFW代理 (443): {'✅ 运行中' if env['cfw_running'] else '❌ 未运行'}")

    # 检查Clash代理
    env["proxy_available"] = tcp_probe("127.0.0.1", 7890)
    log(f"Clash代理 (7890): {'✅ 可用' if env['proxy_available'] else '❌ 不可用'}")

    # 检查API Keys
    secrets_file = PROJECT_ROOT / "secrets.env"
    if secrets_file.exists():
        for line in secrets_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if any(k in key for k in ["API_KEY", "TOKEN", "SECRET"]) and val:
                    env["api_keys"][key] = f"{val[:4]}...{val[-4:]}" if len(val) > 8 else "***"

    # 环境变量中的API keys
    for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
              "GOOGLE_API_KEY", "DASHSCOPE_API_KEY", "ZHIPU_API_KEY"]:
        v = os.environ.get(k, "")
        if v:
            env["api_keys"][k] = f"{v[:4]}...{v[-4:]}"

    log(f"可用API Keys: {list(env['api_keys'].keys()) or '无'}")

    # 语言服务器
    env["language_servers"] = get_language_server_info()
    log(f"语言服务器: {len(env['language_servers'])}个进程")

    # 模型总数
    log(f"已知模型枚举: {len(CHAT_MODELS)}个")
    providers = {}
    for m in CHAT_MODELS.values():
        p = m["provider"]
        providers[p] = providers.get(p, 0) + 1
    log(f"提供商分布: {dict(providers)}")

    return env


# ==================== 八卦辩证分析 ====================

def bagua_analysis(cfw_results, provider_results, ls_results, env):
    """伏羲八卦框架分析所有测试结果"""
    analysis = {
        "dimensions": {},
        "problems": [],
        "solutions": [],
        "insights": [],
    }

    # ☰乾 — 编码能力
    analysis["dimensions"]["☰乾_编码"] = {
        "score": 0, "max": 10,
        "finding": "无法直接测试编码能力（需要IDE交互）",
        "models_available": len(CHAT_MODELS),
    }

    # ☱兑 — 感知力（API可达性）
    provider_success = sum(1 for r in provider_results if r["status"] == "success")
    provider_total = len(provider_results) if provider_results else 1
    analysis["dimensions"]["☱兑_感知"] = {
        "score": round(provider_success / provider_total * 10, 1) if provider_results else 0,
        "max": 10,
        "finding": f"提供商API {provider_success}/{len(provider_results)} 成功",
    }

    # ☲离 — 速度
    latencies = [r["latency_ms"] for r in provider_results if r.get("latency_ms")]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0
    analysis["dimensions"]["☲离_速度"] = {
        "score": max(0, 10 - avg_latency // 1000) if avg_latency else 0,
        "max": 10,
        "finding": f"平均延迟: {avg_latency}ms" if avg_latency else "无延迟数据",
    }

    # ☳震 — 成本效率
    free_models = sum(1 for m in CHAT_MODELS.values() if m["credits"] == "0x")
    analysis["dimensions"]["☳震_成本"] = {
        "score": 8 if free_models > 0 else 5,
        "max": 10,
        "finding": f"{free_models}个免费模型 (SWE系列), BYOK降本路径可用",
    }

    # ☴巽 — 工具调用（gRPC API可达性）
    cfw_pass = sum(1 for t in cfw_results.get("tests", []) if t["status"] == "pass")
    analysis["dimensions"]["☴巽_工具"] = {
        "score": min(10, cfw_pass * 2),
        "max": 10,
        "finding": f"CFW gRPC {cfw_pass}个端点可达",
    }

    # ☵坎 — 推理深度（通过API实际调用验证）
    analysis["dimensions"]["☵坎_推理"] = {
        "score": 7 if provider_success > 0 else 0,
        "max": 10,
        "finding": f"{'已验证模型推理输出' if provider_success > 0 else '无法验证（缺少API Key）'}",
    }

    # ☶艮 — 稳定性
    errors = sum(1 for r in provider_results if r["status"] != "success")
    analysis["dimensions"]["☶艮_安全"] = {
        "score": max(0, 10 - errors * 2),
        "max": 10,
        "finding": f"{errors}个错误 / {len(provider_results)}个测试",
    }

    # ☷坤 — 容量（模型覆盖度）
    analysis["dimensions"]["☷坤_上下文"] = {
        "score": 8,
        "max": 10,
        "finding": f"覆盖{len(CHAT_MODELS)}个模型, 8个提供商",
    }

    # 问题发现
    if not env.get("cfw_running"):
        analysis["problems"].append("P1: CFW代理未运行，无法通过Windsurf通道测试")
    if not env.get("api_keys"):
        analysis["problems"].append("P2: 无模型提供商API Key，BYOK路径不可用")
    if not env.get("proxy_available"):
        analysis["problems"].append("P3: Clash代理不可用，国外API不可达")

    ls_ports = ls_results.get("ports", [])
    ls_grpc_ok = any(t.get("status") == 200 for t in ls_results.get("grpc_tests", []))
    if ls_ports and not ls_grpc_ok:
        analysis["problems"].append(f"P4: 语言服务器{len(ls_ports)}个端口监听但gRPC连接失败")

    if not provider_results or all(r["status"] != "success" for r in provider_results):
        analysis["problems"].append("P5: 所有提供商API测试失败")

    # 解决方案
    analysis["solutions"] = [
        "S1: 添加BYOK API Keys到环境变量 → 直接测试各提供商模型",
        "S2: 通过CFW gRPC-web代理测试Windsurf原生模型",
        "S3: 使用HuggingFace免费推理API测试开源模型",
        "S4: 逆向语言服务器gRPC协议 → 直接调用本地服务",
        "S5: 编写IDE扩展注入测试 → 通过Windsurf内部API测试",
    ]

    # 洞见
    analysis["insights"] = [
        "I1: Windsurf通过gRPC-web代理转发到Codeium后端, CFW在中间注入auth_token",
        "I2: 语言服务器端口监听但不接受外部HTTP连接 — 可能仅接受pipe连接",
        f"I3: {len(CHAT_MODELS)}个用户可见模型, 240+总枚举(含内部/embedding/tab)",
        "I4: 免费模型(SWE-1.5/1.6)在Arena排名超越付费模型 — 成本效率最优",
        "I5: BYOK支持OpenRouter/vLLM/Databricks等自定义端点",
    ]

    return analysis


# ==================== 报告生成 ====================

def generate_report(env, cfw_results, provider_results, ls_results, analysis):
    """生成Markdown测试报告"""
    lines = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append(f"# Windsurf 全模型后端测试报告")
    lines.append(f"")
    lines.append(f"> 生成时间: {ts}")
    lines.append(f"> 测试方法: 不依赖IDE页面, 直接后端API调用")
    lines.append(f"> Python: {env['python']} | 平台: {env['platform']}")
    lines.append(f"")

    # 环境概览
    lines.append(f"## 一、环境概览")
    lines.append(f"")
    lines.append(f"| 组件 | 状态 | 详情 |")
    lines.append(f"|------|------|------|")
    lines.append(f"| CFW代理 | {'✅' if env['cfw_running'] else '❌'} | 127.0.0.1:443 |")
    lines.append(f"| Clash代理 | {'✅' if env['proxy_available'] else '❌'} | 127.0.0.1:7890 |")
    lines.append(f"| 语言服务器 | {'✅' if env['language_servers'] else '❌'} | {len(env['language_servers'])}个进程 |")
    lines.append(f"| Windsurf JS | {'✅' if env['windsurf_js_exists'] else '❌'} | {WINDSURF_JS} |")
    lines.append(f"| API Keys | {len(env.get('api_keys', {}))}个 | {', '.join(env.get('api_keys', {}).keys()) or '无'} |")
    lines.append(f"")

    # 语言服务器详情
    if env["language_servers"]:
        lines.append(f"### 语言服务器进程")
        lines.append(f"")
        lines.append(f"| PID | API Server | Ext Port | Version |")
        lines.append(f"|-----|-----------|----------|---------|")
        for s in env["language_servers"]:
            lines.append(f"| {s['pid']} | {s['api_server'] or '?'} | {s['ext_port'] or '?'} | {s['version'] or '?'} |")
        lines.append(f"")

    # 路径A: CFW
    lines.append(f"## 二、路径A — CFW代理测试")
    lines.append(f"")
    if cfw_results.get("tests"):
        lines.append(f"| 测试项 | 状态 | 详情 |")
        lines.append(f"|--------|------|------|")
        for t in cfw_results["tests"]:
            icon = "✅" if t["status"] == "pass" else "❌"
            lines.append(f"| {t['name']} | {icon} {t['status']} | {t.get('detail', '')} |")
        lines.append(f"")

    # 路径B: 提供商API
    lines.append(f"## 三、路径B — 模型提供商API测试")
    lines.append(f"")
    if provider_results:
        lines.append(f"| 提供商 | 模型 | 状态 | 延迟 | 响应预览 |")
        lines.append(f"|--------|------|------|------|----------|")
        for r in provider_results:
            icon = "✅" if r["status"] == "success" else "❌"
            preview = r.get("response_preview", "")[:60].replace("\n", " ").replace("|", "\\|")
            lines.append(f"| {r['provider']} | {r['model']} | {icon} {r['status']} | {r['latency_ms']}ms | {preview} |")
        lines.append(f"")
    else:
        lines.append(f"> 无可用API Key, 未执行提供商直接测试。")
        lines.append(f"")

    # 路径C: 语言服务器
    lines.append(f"## 四、路径C — 本地语言服务器探测")
    lines.append(f"")
    if ls_results.get("ports"):
        lines.append(f"- 监听端口: {ls_results['ports']}")
    if ls_results.get("grpc_tests"):
        lines.append(f"")
        lines.append(f"| 端口 | 协议 | 状态 | 详情 |")
        lines.append(f"|------|------|------|------|")
        for t in ls_results["grpc_tests"]:
            icon = "✅" if t.get("status") == 200 else "❌"
            detail = t.get("error", f"body={t.get('body_len', '?')}B")
            lines.append(f"| {t['port']} | {t['protocol']} | {icon} {t.get('status', '?')} | {detail} |")
        lines.append(f"")

    # 模型枚举
    lines.append(f"## 五、模型枚举全景（{len(CHAT_MODELS)}个用户可见模型）")
    lines.append(f"")
    lines.append(f"| # | 枚举ID | 提供商 | 名称 | 级别 | 积分 |")
    lines.append(f"|---|--------|--------|------|------|------|")
    for i, (mid, info) in enumerate(CHAT_MODELS.items(), 1):
        lines.append(f"| {i} | `{mid}` | {info['provider']} | {info['name']} | {info['tier']} | {info['credits']} |")
    lines.append(f"")

    # 八卦分析
    lines.append(f"## 六、伏羲八卦辩证分析")
    lines.append(f"")
    lines.append(f"### 6.1 八维能力雷达")
    lines.append(f"")
    lines.append(f"| 卦象 | 维度 | 得分 | 发现 |")
    lines.append(f"|------|------|------|------|")
    total_score = 0
    for dim_name, dim_data in analysis["dimensions"].items():
        score = dim_data["score"]
        total_score += score
        bar = "█" * int(score) + "░" * (10 - int(score))
        lines.append(f"| {dim_name} | {bar} | {score}/10 | {dim_data['finding']} |")
    lines.append(f"| **总分** | | **{total_score}/80** | |")
    lines.append(f"")

    # 问题
    if analysis["problems"]:
        lines.append(f"### 6.2 发现的问题")
        lines.append(f"")
        for p in analysis["problems"]:
            lines.append(f"- **{p}**")
        lines.append(f"")

    # 洞见
    if analysis["insights"]:
        lines.append(f"### 6.3 关键洞见")
        lines.append(f"")
        for ins in analysis["insights"]:
            lines.append(f"- {ins}")
        lines.append(f"")

    # 解决方案
    if analysis["solutions"]:
        lines.append(f"### 6.4 解决方案")
        lines.append(f"")
        for s in analysis["solutions"]:
            lines.append(f"- {s}")
        lines.append(f"")

    # 结论
    lines.append(f"## 七、结论")
    lines.append(f"")
    lines.append(f"### 后端直调可行性")
    lines.append(f"")
    lines.append(f"| 路径 | 可行性 | 说明 |")
    lines.append(f"|------|--------|------|")
    lines.append(f"| A. CFW gRPC代理 | ⚠️ 部分 | gRPC端点可达但缺少auth_token |")
    lines.append(f"| B. 提供商直调 | {'✅ 可行' if any(r['status']=='success' for r in provider_results) else '❌ 需API Key'} | BYOK路径, 需各提供商API Key |")
    lines.append(f"| C. 语言服务器 | ❌ 受限 | 端口监听但gRPC连接超时/拒绝 |")
    lines.append(f"")
    lines.append(f"### 推荐行动")
    lines.append(f"")
    lines.append(f"1. **立即可做**: 添加DeepSeek/DashScope/智谱AI免费API Key到环境变量")
    lines.append(f"2. **中期**: 开发Windsurf扩展注入,从IDE内部获取auth_token")
    lines.append(f"3. **长期**: 完整逆向Codeium gRPC协议,实现独立调用")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*由 model_test.py v1.0 自动生成 | 伏羲八卦 × 全模型测试*")

    return "\n".join(lines)


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="Windsurf 全模型后端测试")
    parser.add_argument("--quick", action="store_true", help="快速探测模式")
    parser.add_argument("--report", action="store_true", help="仅生成报告（使用缓存结果）")
    parser.add_argument("--provider", help="只测试指定提供商")
    args = parser.parse_args()

    # 0. 加载secrets.env
    loaded = load_secrets_env()
    if loaded:
        log(f"从secrets.env加载了{loaded}个环境变量")

    # 1. 环境探测
    env = detect_environment()

    if args.report and RESULTS_FILE.exists():
        log("使用缓存结果生成报告...")
        cached = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        cfw_results = cached.get("cfw", {})
        cfw_model_results = cached.get("cfw_models", [])
        provider_results = cached.get("providers", [])
        ls_results = cached.get("language_server", {})
    else:
        # 2. 路径A: CFW代理测试
        cfw_results = test_cfw_proxy()

        # 2.5 路径A+: CFW全模型gRPC-web调用测试
        cfw_model_results = test_all_cfw_models()

        # 3. 路径B: 提供商API测试
        provider_results = test_all_providers()

        # 4. 路径C: 语言服务器探测
        ls_results = test_language_server()

        # 保存原始结果
        raw_results = {
            "timestamp": env["timestamp"],
            "env": env,
            "cfw": cfw_results,
            "cfw_models": cfw_model_results,
            "providers": provider_results,
            "language_server": ls_results,
        }
        RESULTS_FILE.write_text(json.dumps(raw_results, indent=2, ensure_ascii=False, default=str),
                                encoding="utf-8")
        log(f"原始结果已保存: {RESULTS_FILE}")

    # 5. 八卦分析
    log("=" * 60)
    log("伏羲八卦辩证分析...", "TEST")
    analysis = bagua_analysis(cfw_results, provider_results, ls_results, env)

    # 6. 生成报告
    report = generate_report(env, cfw_results, provider_results, ls_results, analysis,
                             cfw_model_results=cfw_model_results)
    REPORT_FILE.write_text(report, encoding="utf-8")
    log(f"测试报告已生成: {REPORT_FILE}", "OK")

    # 打印摘要
    cfw_m_success = sum(1 for r in cfw_model_results if r.get('status') == 'success')
    log("=" * 60)
    log("测试摘要:")
    total = sum(d["score"] for d in analysis["dimensions"].values())
    log(f"  八卦总分: {total}/80")
    log(f"  问题数: {len(analysis['problems'])}")
    log(f"  CFW可达: {cfw_results.get('available', False)}")
    log(f"  CFW模型测试: {cfw_m_success}/{len(cfw_model_results)}成功")
    log(f"  API成功: {sum(1 for r in provider_results if r['status']=='success')}/{len(provider_results)}")
    log(f"  模型枚举: {len(CHAT_MODELS)}个 | Protobuf枚举: {len(MODEL_ENUM_VALUES)}个")
    log("=" * 60)

    return 0 if not analysis["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
