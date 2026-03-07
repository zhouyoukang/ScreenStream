"""
OPPO Reno4 SE (PEAM00/MT6853) Root激活脚本 v2
BL已解锁 + Magisk已安装 → 只需提取boot.img → patch → flash

用法:
  python auto_root.py extract   # 提取boot.img (多种方法自动尝试)
  python auto_root.py patch     # 推送到手机让Magisk patch
  python auto_root.py flash     # fastboot写入patched boot
  python auto_root.py verify    # 验证root
  python auto_root.py all       # 全自动流程
  python auto_root.py status    # 查看设备状态

提取boot.img的方法 (按优先级):
  A. dd直读 — adb shell dd if=/dev/block/by-name/boot (需root或宽松权限)
  B. payload-dumper — 从stock固件ZIP提取 (需下载固件)
  C. fastboot boot TWRP — 临时启动TWRP提取 (需TWRP镜像)
  D. mtkclient BROM — MTK漏洞提取 (OPPO安全锁阻止,已证实失败)

已验证失败的方法:
  ✗ adb root — production build拒绝
  ✗ mtkclient --crash preloader exploit — OPPO安全preloader握手失败
  ✗ adb reboot recovery → ADB — OPPO ColorOS recovery无ADB
"""
import subprocess, sys, os, time, shutil, glob

ADB = r"D:\platform-tools\adb.exe"
FASTBOOT = r"D:\platform-tools\fastboot.exe"
SERIAL = "WK555X5DF65PPR4L"
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
BOOT_IMG = os.path.join(WORK_DIR, "boot.img")
PATCHED_BOOT = os.path.join(WORK_DIR, "magisk_patched_boot.img")
DUMPER = os.path.join(WORK_DIR, "payload-dumper-go.exe")

def run(cmd, timeout=60, check=True):
    """Run command and return output"""
    print(f"  > {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        print(f"  ! Exit {r.returncode}: {r.stderr.strip()}")
    return r

def adb(args, timeout=30):
    return run(f'"{ADB}" -s {SERIAL} {args}', timeout=timeout, check=False)

def fastboot(args, timeout=30):
    return run(f'"{FASTBOOT}" -s {SERIAL} {args}', timeout=timeout, check=False)

def wait_for_brom(timeout=120):
    """Wait for device to enter BROM mode (MTK preloader)"""
    print("\n" + "="*60)
    print("请将手机进入BROM模式:")
    print("  1. 完全关机")
    print("  2. 按住 音量+ 键")  
    print("  3. 保持按住，同时插入USB线")
    print("  4. 屏幕保持黑色 = 成功")
    print(f"  等待设备连接... (最长{timeout}秒)")
    print("="*60)
    
    start = time.time()
    while time.time() - start < timeout:
        # Check for MTK preloader device
        try:
            import libusb_package
            import usb.core
            import usb.backend.libusb1
            backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
            mtk_devs = list(usb.core.find(find_all=True, idVendor=0x0E8D, backend=backend))
            if mtk_devs:
                for d in mtk_devs:
                    print(f"\n✅ MTK设备检测到! VID={hex(d.idVendor)} PID={hex(d.idProduct)}")
                return True
        except Exception:
            pass
        time.sleep(2)
        elapsed = int(time.time() - start)
        if elapsed % 10 == 0:
            print(f"  ... 已等待 {elapsed}秒")
    
    print("❌ 超时，未检测到BROM设备")
    return False

def wait_for_adb(timeout=120):
    """Wait for device to come back to ADB mode"""
    print(f"\n等待手机重启并连接ADB... (最长{timeout}秒)")
    start = time.time()
    while time.time() - start < timeout:
        r = adb("shell echo ok", timeout=5)
        if r.returncode == 0 and "ok" in r.stdout:
            print("✅ ADB已连接")
            return True
        time.sleep(3)
    print("❌ ADB超时")
    return False

def step_extract():
    """Step 1: Extract boot.img — 多方法自动尝试"""
    print("\n" + "="*60)
    print("步骤1: 提取boot.img")
    print("="*60)
    
    if os.path.exists(BOOT_IMG) and os.path.getsize(BOOT_IMG) > 1024*1024:
        size_mb = os.path.getsize(BOOT_IMG) / (1024*1024)
        print(f"✅ boot.img 已存在 ({size_mb:.1f} MB)，跳过提取")
        return True
    
    # 方法A: dd直读 (最简单,但通常需root)
    print("\n[方法A] 尝试dd直读boot分区...")
    if try_dd_extract():
        return True
    
    # 方法B: payload-dumper从固件ZIP提取
    print("\n[方法B] 尝试从固件ZIP提取...")
    if try_payload_extract():
        return True
    
    # 方法C: mtkclient BROM (已知对OPPO失败,但仍尝试)
    print("\n[方法C] mtkclient BROM (OPPO可能阻止)...")
    if try_mtkclient_extract():
        return True
    
    print("\n❌ 所有自动提取方法失败")
    print("手动方案: 下载PEAM00固件ZIP → 放到本目录 → 重新运行")
    print("固件搜索: 百度搜 'OPPO Reno4 SE PEAM00 固件下载'")
    return False

def try_dd_extract():
    """方法A: adb shell dd直读boot分区"""
    # 先找boot分区设备路径
    r = adb('shell "ls -la /dev/block/by-name/boot 2>/dev/null || '
            'ls -la /dev/block/bootdevice/by-name/boot 2>/dev/null || '
            'ls -la /dev/block/platform/*/by-name/boot 2>/dev/null"')
    if r.returncode != 0 or not r.stdout.strip():
        # 尝试从fstab或proc/partinfo找
        r = adb('shell "cat /proc/partinfo 2>/dev/null | grep boot || '
                'cat /proc/dumchar_info 2>/dev/null | grep boot"')
        print(f"  分区信息: {r.stdout.strip() if r.stdout else '无法读取'}")
        print("  dd方法: 无法定位boot分区")
        return False
    
    boot_dev = r.stdout.strip().split()[-1] if ' -> ' in r.stdout else r.stdout.strip().split()[0]
    print(f"  boot分区: {boot_dev}")
    
    # 尝试dd读取
    r = adb(f'shell "dd if={boot_dev} of=/sdcard/Download/boot_extract.img bs=4096 2>&1"', timeout=60)
    if 'Permission denied' in (r.stderr + r.stdout):
        print("  dd方法: Permission denied (需root)")
        return False
    
    # 检查生成的文件
    r2 = adb('shell "ls -la /sdcard/Download/boot_extract.img 2>/dev/null"')
    if r2.returncode == 0 and r2.stdout.strip():
        # 拉取到PC
        adb(f'pull /sdcard/Download/boot_extract.img "{BOOT_IMG}"', timeout=60)
        adb('shell "rm /sdcard/Download/boot_extract.img"')
        if os.path.exists(BOOT_IMG) and os.path.getsize(BOOT_IMG) > 1024*1024:
            print(f"  ✅ dd提取成功! ({os.path.getsize(BOOT_IMG)/1024/1024:.1f} MB)")
            return True
    
    print("  dd方法: 提取失败")
    return False

def try_payload_extract():
    """方法B: 从固件ZIP中用payload-dumper提取boot.img"""
    # 检查payload-dumper-go
    if not os.path.exists(DUMPER):
        print(f"  payload-dumper-go 未找到: {DUMPER}")
        return False
    
    # 搜索固件ZIP
    firmware_patterns = [
        os.path.join(WORK_DIR, "*.zip"),
        os.path.join(WORK_DIR, "*.ofp"),
        os.path.join(WORK_DIR, "PEAM*"),
    ]
    firmware_file = None
    for pattern in firmware_patterns:
        matches = glob.glob(pattern)
        for m in matches:
            if os.path.getsize(m) > 100*1024*1024:  # >100MB = likely firmware
                firmware_file = m
                break
        if firmware_file:
            break
    
    if not firmware_file:
        print("  未找到固件文件 (需>100MB的ZIP/OFP)")
        return False
    
    print(f"  固件: {os.path.basename(firmware_file)}")
    r = run(f'"{DUMPER}" -partitions boot -o "{WORK_DIR}" "{firmware_file}"', timeout=300)
    
    # payload-dumper可能输出到子目录
    for candidate in [BOOT_IMG, os.path.join(WORK_DIR, "output", "boot.img")]:
        if os.path.exists(candidate) and os.path.getsize(candidate) > 1024*1024:
            if candidate != BOOT_IMG:
                shutil.move(candidate, BOOT_IMG)
            print(f"  ✅ payload提取成功! ({os.path.getsize(BOOT_IMG)/1024/1024:.1f} MB)")
            return True
    
    print("  payload提取失败")
    return False

def try_mtkclient_extract():
    """方法C: mtkclient BROM提取 (OPPO大概率失败)"""
    if not wait_for_brom(timeout=30):  # 短超时,不久等
        return False
    r = run(f'python -m mtkclient r boot "{BOOT_IMG}"', timeout=120, check=False)
    if os.path.exists(BOOT_IMG) and os.path.getsize(BOOT_IMG) > 1024*1024:
        print(f"  ✅ mtkclient提取成功!")
        return True
    print("  mtkclient提取失败 (OPPO安全preloader阻止)")
    return False

def step_patch():
    """Step 2: Push boot.img to phone and let Magisk patch it"""
    print("\n" + "="*60)
    print("步骤2: 推送boot.img到手机，Magisk patch")
    print("="*60)
    
    if not os.path.exists(BOOT_IMG):
        print(f"❌ {BOOT_IMG} 不存在，请先执行 extract")
        return False
    
    # Wait for ADB
    if not wait_for_adb():
        return False
    
    # Unlock screen
    print("\n解锁屏幕...")
    adb('shell "input keyevent KEYCODE_WAKEUP; sleep 1; input swipe 540 1800 540 800"')
    time.sleep(2)
    
    # Push boot.img to phone
    print("\n推送boot.img到手机...")
    r = adb(f'push "{BOOT_IMG}" /sdcard/Download/boot.img', timeout=60)
    if r.returncode != 0:
        print("❌ 推送失败")
        return False
    print("✅ boot.img 已推送到 /sdcard/Download/boot.img")
    
    # Open Magisk and instruct user
    print("\n启动Magisk App...")
    adb('shell "am start -n com.topjohnwu.magisk/.ui.MainActivity"')
    time.sleep(3)
    
    print("\n" + "="*60)
    print("📱 请在手机上操作:")
    print("  1. Magisk App → 点击'安装'按钮")
    print("  2. 方法 → 选择'选择并修补一个文件'")
    print("  3. 选择 /sdcard/Download/boot.img")
    print("  4. 点击'开始'")
    print("  5. 等待patch完成 (约10-30秒)")
    print("="*60)
    
    # Wait for patched file to appear
    print("\n等待patched boot.img生成...")
    for i in range(120):
        r = adb('shell "ls -la /sdcard/Download/magisk_patched-*.img 2>/dev/null"')
        if r.returncode == 0 and "magisk_patched" in r.stdout:
            patched_name = r.stdout.strip().split()[-1]
            print(f"\n✅ Magisk patch完成: {patched_name}")
            
            # Pull patched boot
            print("拉取patched boot...")
            adb(f'pull "{patched_name}" "{PATCHED_BOOT}"', timeout=60)
            
            if os.path.exists(PATCHED_BOOT) and os.path.getsize(PATCHED_BOOT) > 1024*1024:
                size_mb = os.path.getsize(PATCHED_BOOT) / (1024*1024)
                print(f"✅ patched boot.img 已保存 ({size_mb:.1f} MB)")
                
                # Cleanup phone
                adb(f'shell "rm {patched_name}"')
                return True
            else:
                print("❌ 拉取失败")
                return False
        
        if i % 10 == 0 and i > 0:
            print(f"  ... 已等待 {i}秒")
        time.sleep(1)
    
    print("❌ 超时，Magisk未生成patched文件")
    return False

def step_flash():
    """Step 3: Flash patched boot via fastboot (首选) 或 mtkclient"""
    print("\n" + "="*60)
    print("步骤3: 写入patched boot")
    print("="*60)
    
    if not os.path.exists(PATCHED_BOOT):
        print(f"❌ {PATCHED_BOOT} 不存在，请先执行 patch")
        return False
    
    size_mb = os.path.getsize(PATCHED_BOOT) / (1024*1024)
    print(f"patched boot: {size_mb:.1f} MB")
    
    # 首选: fastboot flash (BL已解锁)
    print("\n[fastboot] 重启到bootloader模式...")
    adb('reboot bootloader')
    
    # 等待fastboot设备出现
    print("等待fastboot设备...")
    for i in range(30):
        time.sleep(2)
        r = fastboot('devices')
        if SERIAL in (r.stdout or ''):
            print(f"✅ fastboot设备已连接")
            break
        # 有些设备序列号在fastboot中不同
        if r.stdout and r.stdout.strip():
            print(f"  fastboot设备: {r.stdout.strip()}")
            break
    else:
        print("❌ fastboot超时，尝试mtkclient...")
        return try_mtkclient_flash()
    
    # Flash!
    print("\n正在flash patched boot...")
    r = fastboot(f'flash boot "{PATCHED_BOOT}"', timeout=120)
    if r.returncode == 0 or 'Finished' in (r.stdout or '') + (r.stderr or ''):
        print("✅ flash成功!")
        print("重启手机...")
        fastboot('reboot')
        return True
    else:
        print(f"❌ fastboot flash失败: {r.stderr}")
        print("尝试mtkclient备选...")
        return try_mtkclient_flash()

def try_mtkclient_flash():
    """备选: mtkclient BROM写入"""
    if not wait_for_brom(timeout=30):
        return False
    r = run(f'python -m mtkclient w boot "{PATCHED_BOOT}"', timeout=300, check=False)
    if r.returncode == 0:
        print("✅ mtkclient写入成功!")
        return True
    print("❌ mtkclient写入也失败")
    return False

def step_verify():
    """Step 4: Verify root access"""
    print("\n" + "="*60)
    print("步骤4: 验证Root")
    print("="*60)
    
    if not wait_for_adb():
        return False
    
    # Unlock screen
    adb('shell "input keyevent KEYCODE_WAKEUP; sleep 1; input swipe 540 1800 540 800"')
    time.sleep(2)
    
    # Open Magisk to grant su
    print("\n启动Magisk App (授予su权限)...")
    adb('shell "am start -n com.topjohnwu.magisk/.ui.MainActivity"')
    time.sleep(3)
    
    # Test su
    print("\n测试su...")
    r = adb('shell "su -c id"', timeout=15)
    if r.returncode == 0 and "uid=0(root)" in r.stdout:
        print(f"\n{'='*60}")
        print(f"🎉 ROOT成功! {r.stdout.strip()}")
        print(f"{'='*60}")
        
        # Additional checks
        adb('shell "su -c \'cat /proc/version | head -1\'"')
        adb('shell "su -c \'getenforce\'"')
        return True
    else:
        print(f"\n⚠️  su测试: {r.stdout.strip()} {r.stderr.strip()}")
        print("提示: 首次su可能需要在Magisk App中授权")
        print("请打开Magisk → 超级用户 → 授予shell权限")
        return False

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n快速状态检查:")
        step_status()
        sys.exit(0)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "extract":
        step_extract()
    elif cmd == "patch":
        step_patch()
    elif cmd == "flash":
        step_flash()
    elif cmd == "verify":
        step_verify()
    elif cmd == "status":
        step_status()
    elif cmd == "all":
        print("🔄 全自动Root流程 (extract → patch → flash → verify)")
        if not step_extract():
            print("\n❌ 提取失败，终止"); return
        if not wait_for_adb():
            print("\n❌ 等待ADB超时"); return
        if not step_patch():
            print("\n❌ Patch失败，终止"); return
        if not step_flash():
            print("\n❌ 写入失败，终止"); return
        print("\n⏳ 等待手机重启...")
        time.sleep(15)
        if not wait_for_adb():
            print("\n❌ 重启后ADB超时"); return
        step_verify()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)

def step_status():
    """查看设备当前状态"""
    print("\n" + "="*60)
    print("设备状态")
    print("="*60)
    r = adb('shell "getprop ro.product.model"')
    print(f"型号: {r.stdout.strip() if r.returncode == 0 else 'N/A'}")
    r = adb('shell "getprop ro.boot.verifiedbootstate"')
    print(f"Verified Boot: {r.stdout.strip() if r.returncode == 0 else 'N/A'}")
    r = adb('shell "getprop ro.boot.flash.locked"')
    print(f"BL Lock: {r.stdout.strip() if r.returncode == 0 else 'N/A'}")
    r = adb('shell "su -c id 2>/dev/null"', timeout=10)
    has_root = r.returncode == 0 and 'uid=0' in (r.stdout or '')
    print(f"Root: {'✅ YES' if has_root else '❌ NO'}")
    r = adb('shell "pm list packages | grep magisk"')
    print(f"Magisk: {'✅ installed' if 'magisk' in (r.stdout or '') else '❌ not found'}")
    print(f"boot.img: {'✅ ' + str(os.path.getsize(BOOT_IMG)//1024//1024) + 'MB' if os.path.exists(BOOT_IMG) and os.path.getsize(BOOT_IMG) > 1024*1024 else '❌ not found'}")
    print(f"patched: {'✅ ' + str(os.path.getsize(PATCHED_BOOT)//1024//1024) + 'MB' if os.path.exists(PATCHED_BOOT) and os.path.getsize(PATCHED_BOOT) > 1024*1024 else '❌ not found'}")

if __name__ == "__main__":
    main()
