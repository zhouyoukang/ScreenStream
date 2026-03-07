"""OSR6轴校准工具 — 确保舵机行程正确"""

import sys
import time
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tcode import TCodeSerial, AXES_SR6

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

CALIBRATION_FILE = Path(__file__).parent.parent / "calibration.json"

DEFAULT_CALIBRATION = {
    axis_def.code: {
        "min": 0,
        "max": 9999,
        "center": 5000,
        "inverted": False,
        "name": name,
    }
    for name, axis_def in AXES_SR6.items()
}


def load_calibration() -> dict:
    """加载校准数据"""
    if CALIBRATION_FILE.exists():
        with open(CALIBRATION_FILE, "r") as f:
            return json.load(f)
    return dict(DEFAULT_CALIBRATION)


def save_calibration(cal: dict):
    """保存校准数据"""
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(cal, f, indent=2, ensure_ascii=False)
    logger.info(f"校准数据已保存: {CALIBRATION_FILE}")


def calibrate_axis(dev: TCodeSerial, axis_code: str, cal: dict):
    """校准单轴"""
    info = cal.get(axis_code, DEFAULT_CALIBRATION.get(axis_code, {}))
    name = info.get("name", axis_code)

    logger.info(f"\n校准轴: {axis_code} ({name})")
    logger.info("-" * 30)

    # 步骤1: 归中位
    logger.info("步骤1: 移到中位...")
    dev.move(axis_code, 5000, 1000)
    time.sleep(1.5)
    input("  按Enter确认中位正确 (或输入新中位值): ") or "5000"

    # 步骤2: 最小位置
    logger.info("步骤2: 移到最小位置...")
    dev.move(axis_code, 0, 2000)
    time.sleep(2.5)
    min_input = input("  按Enter确认最小位置 (或输入调整值): ").strip()
    min_val = int(min_input) if min_input else 0

    # 步骤3: 最大位置
    logger.info("步骤3: 移到最大位置...")
    dev.move(axis_code, 9999, 2000)
    time.sleep(2.5)
    max_input = input("  按Enter确认最大位置 (或输入调整值): ").strip()
    max_val = int(max_input) if max_input else 9999

    # 步骤4: 反转检查
    dev.move(axis_code, 5000, 1000)
    time.sleep(1.5)
    invert = input("  轴方向是否需要反转? (y/N): ").strip().lower() == "y"

    cal[axis_code] = {
        "min": min_val,
        "max": max_val,
        "center": 5000,
        "inverted": invert,
        "name": name,
    }
    logger.info(f"  ✓ {axis_code}: min={min_val}, max={max_val}, invert={invert}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OSR6轴校准")
    parser.add_argument("-p", "--port", help="串口")
    parser.add_argument("-a", "--axis", help="校准特定轴")
    parser.add_argument("--show", action="store_true", help="显示当前校准")
    parser.add_argument("--reset", action="store_true", help="重置校准")

    args = parser.parse_args()

    if args.show:
        cal = load_calibration()
        logger.info("当前校准数据:")
        for code, data in cal.items():
            logger.info(f"  {code}: {json.dumps(data)}")
        return

    if args.reset:
        save_calibration(DEFAULT_CALIBRATION)
        logger.info("校准已重置为默认值")
        return

    cal = load_calibration()

    with TCodeSerial(port=args.port) as dev:
        if not dev.is_connected:
            logger.error("连接失败!")
            return

        if args.axis:
            calibrate_axis(dev, args.axis.upper(), cal)
        else:
            for axis_def in AXES_SR6.values():
                calibrate_axis(dev, axis_def.code, cal)

        save_calibration(cal)
        dev.home_all()
        logger.info("\n✅ 校准完成!")


if __name__ == "__main__":
    main()
