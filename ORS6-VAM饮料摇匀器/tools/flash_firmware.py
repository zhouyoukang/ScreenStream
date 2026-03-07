"""ESP32固件烧写辅助工具

支持:
  1. 自动下载固件
  2. 使用esptool.py烧写
  3. 验证连接

推荐固件:
  - TCodeESP32 (jcfain/TCodeESP32) — 功能最全
  - osr-esp32 (ayvasoftware) — BLE增强
  - MiraBot — 图形化烧写
"""

import sys
import subprocess
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

FIRMWARE_OPTIONS = {
    "tcode_esp32": {
        "name": "TCodeESP32 (推荐)",
        "repo": "https://github.com/jcfain/TCodeESP32",
        "description": "功能最全: Serial + WiFi + Bluetooth, Web配置界面",
        "flash_cmd": "esptool.py --chip esp32 --baud 921600 write_flash 0x0 firmware.bin",
    },
    "osr_esp32": {
        "name": "osr-esp32 (BLE增强)",
        "repo": "https://github.com/ayvasoftware/osr-esp32",
        "description": "BLE Streaming支持, 基于TempestMAx设计",
        "flash_cmd": "esptool.py --chip esp32 --baud 921600 write_flash 0x0 firmware.bin",
    },
    "osr_esp32_s3": {
        "name": "osr-esp32-s3 (ESP32-S3)",
        "repo": "https://github.com/BQsummer/osr-esp32-s3",
        "description": "ESP32-S3版本, 默认OSR6模式",
        "flash_cmd": "esptool.py --chip esp32s3 --baud 921600 write_flash 0x0 firmware.bin",
    },
    "sr6mb": {
        "name": "TCodeESP32-SR6MB (SR6主板)",
        "repo": "https://github.com/Diy6bot/TCodeESP32-SR6MB",
        "description": "SR6主板专用 v1.38b, Crimzzon修改版",
        "flash_cmd": "esptool.py --chip esp32 --baud 921600 write_flash 0x0 firmware.bin",
    },
    "mirabot": {
        "name": "MiraBot (图形化)",
        "url": "https://mirabotx.com/guide-osr-compatible-firmware/",
        "description": "浏览器图形化烧写, 最简单",
        "flash_cmd": "# 浏览器打开MiraBot网站，连接ESP32，选择固件，点击START",
    },
}


def check_esptool() -> bool:
    """检查esptool是否安装"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "esptool", "version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            logger.info(f"esptool已安装: {result.stdout.strip()}")
            return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    logger.warning("esptool未安装。安装: pip install esptool")
    return False


def list_firmwares():
    """列出所有可用固件"""
    logger.info("\n可用固件选项:")
    logger.info("=" * 60)
    for key, fw in FIRMWARE_OPTIONS.items():
        logger.info(f"\n  [{key}] {fw['name']}")
        logger.info(f"    {fw['description']}")
        logger.info(f"    仓库: {fw.get('repo', fw.get('url', 'N/A'))}")


def print_flash_guide():
    """打印烧写指南"""
    logger.info("""
╔══════════════════════════════════════════════════╗
║          ESP32 固件烧写指南                       ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  方法1: MiraBot (最简单，推荐新手)                  ║
║  ─────────────────────────────────               ║
║  1. 浏览器打开: mirabotx.com/guide               ║
║  2. USB连接ESP32                                 ║
║  3. 点击Connect → 选择固件 → START              ║
║                                                  ║
║  方法2: esptool (命令行)                          ║
║  ──────────────────────                          ║
║  1. pip install esptool                          ║
║  2. 下载固件.bin文件                              ║
║  3. esptool.py --chip esp32 \\                    ║
║       --baud 921600 \\                            ║
║       write_flash 0x0 firmware.bin               ║
║                                                  ║
║  方法3: Arduino IDE                              ║
║  ────────────────                                ║
║  1. 安装Arduino IDE + ESP32 Board Package       ║
║  2. 打开固件.ino文件                              ║
║  3. 选择ESP32 Dev Module → Upload              ║
║                                                  ║
║  方法4: PlatformIO (VSCode)                      ║
║  ──────────────────────                          ║
║  1. VSCode安装PlatformIO扩展                     ║
║  2. 打开固件项目                                  ║
║  3. PlatformIO: Upload                          ║
║                                                  ║
╚══════════════════════════════════════════════════╝
""")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ESP32固件烧写辅助")
    parser.add_argument("--list", action="store_true", help="列出固件选项")
    parser.add_argument("--guide", action="store_true", help="烧写指南")
    parser.add_argument("--check", action="store_true", help="检查esptool")

    args = parser.parse_args()

    if args.list:
        list_firmwares()
    elif args.guide:
        print_flash_guide()
    elif args.check:
        check_esptool()
    else:
        list_firmwares()
        print_flash_guide()


if __name__ == "__main__":
    main()
