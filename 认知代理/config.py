"""
认知代理 — 全局配置
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 数据目录（存放SQLite、快照等）
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# SQLite数据库
DB_PATH = DATA_DIR / "events.db"

# HTTP服务端口
SERVER_PORT = int(os.environ.get("COGNITIVE_AGENT_PORT", "9070"))

# 感知配置
SCREEN_SNAPSHOT_INTERVAL = 0.5   # 语义快照间隔（秒），≤2fps
SCREEN_MAX_DEPTH = 8             # UIA树最大深度
SCREEN_MIN_RECT_SIZE = 5         # 忽略小于5px的控件

INPUT_BUFFER_SIZE = 10000        # 输入事件缓冲区大小
WINDOW_POLL_INTERVAL = 0.2       # 窗口焦点轮询间隔

# 存储限制
MAX_SESSION_SIZE_MB = 100        # 单次采集会话上限
MAX_EVENTS_PER_SESSION = 500000  # 单次会话最大事件数
EVENT_RETENTION_HOURS = 72       # 事件保留时间

# 隐私
SENSITIVE_WINDOW_KEYWORDS = [
    "密码", "password", "银行", "bank", "支付", "pay",
    "credential", "secret", "token", "private",
]
SENSITIVE_PROCESS_NAMES = [
    "keepass", "1password", "bitwarden", "lastpass",
]
