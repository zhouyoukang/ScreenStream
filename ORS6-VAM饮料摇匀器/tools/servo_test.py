"""舵机逐轴测试工具 — 安全验证每个轴的运动范围"""

import sys
import time
import argparse
import logging

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from tcode import TCodeSerial, AXES_SR6

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def test_single_axis(dev: TCodeSerial, axis_code: str, axis_name: str,
                     speed_ms: int = 1000):
    """测试单轴全行程"""
    logger.info(f"\n{'='*40}")
    logger.info(f"测试轴: {axis_code} ({axis_name})")
    logger.info(f"{'='*40}")

    # 归中位
    logger.info("  → 归中位 (5000)")
    dev.move(axis_code, 5000, speed_ms)
    time.sleep(speed_ms / 1000.0 + 0.5)

    # 最小位置
    logger.info("  → 最小位置 (0)")
    dev.move(axis_code, 0, speed_ms)
    time.sleep(speed_ms / 1000.0 + 0.5)

    # 最大位置
    logger.info("  → 最大位置 (9999)")
    dev.move(axis_code, 9999, speed_ms)
    time.sleep(speed_ms / 1000.0 + 0.5)

    # 归中位
    logger.info("  → 归中位 (5000)")
    dev.move(axis_code, 5000, speed_ms)
    time.sleep(speed_ms / 1000.0 + 0.5)

    logger.info(f"  ✓ {axis_code} 测试完成")


def test_all_axes(dev: TCodeSerial, speed_ms: int = 1000):
    """逐轴测试所有6个轴"""
    logger.info("\n" + "="*50)
    logger.info("SR6 全轴测试")
    logger.info("="*50)

    for name, axis_def in AXES_SR6.items():
        test_single_axis(dev, axis_def.code, f"{name} ({axis_def.description})",
                         speed_ms)
        time.sleep(0.5)

    logger.info("\n✅ 所有轴测试完成!")


def interactive_test(dev: TCodeSerial):
    """交互式测试模式"""
    logger.info("\n交互式测试模式")
    logger.info("命令格式: <轴><位置>[I<时间ms>]")
    logger.info("示例: L09999I500  R05000I1000")
    logger.info("特殊命令: home=归位, stop=停止, quit=退出, list=列出端口")
    logger.info("-" * 40)

    while True:
        try:
            cmd = input("TCode> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue
        if cmd.lower() == "quit":
            break
        if cmd.lower() == "home":
            dev.home_all()
            logger.info("已归位")
            continue
        if cmd.lower() == "stop":
            dev.stop()
            logger.info("已停止")
            continue
        if cmd.lower() == "list":
            for p in TCodeSerial.list_ports():
                logger.info(f"  {p['port']}: {p['description']}")
            continue
        if cmd.lower() == "info":
            info = dev.device_info()
            logger.info(f"设备: {info}")
            continue

        response = dev.send(cmd)
        if response:
            logger.info(f"响应: {response}")


def main():
    parser = argparse.ArgumentParser(description="OSR6 舵机测试工具")
    parser.add_argument("-p", "--port", help="串口 (如COM5, 默认自动检测)")
    parser.add_argument("-b", "--baud", type=int, default=115200, help="波特率")
    parser.add_argument("-s", "--speed", type=int, default=1000,
                        help="运动速度(ms)")
    parser.add_argument("-a", "--axis", help="测试特定轴 (如L0)")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="交互模式")
    parser.add_argument("--list-ports", action="store_true", help="列出串口")

    args = parser.parse_args()

    if args.list_ports:
        ports = TCodeSerial.list_ports()
        if not ports:
            logger.info("未检测到串口设备")
        for p in ports:
            logger.info(f"  {p['port']}: {p['description']} (VID={p['vid']})")
        return

    with TCodeSerial(port=args.port, baudrate=args.baud) as dev:
        if not dev.is_connected:
            logger.error("连接失败!")
            return

        if args.interactive:
            interactive_test(dev)
        elif args.axis:
            axis_name = next(
                (n for n, a in AXES_SR6.items() if a.code == args.axis.upper()),
                args.axis
            )
            test_single_axis(dev, args.axis.upper(), axis_name, args.speed)
        else:
            test_all_axes(dev, args.speed)


if __name__ == "__main__":
    main()
