"""
VM Client SDK — Agent直接import使用的极简接口
=============================================
零配置、零依赖(除vm_controller)、开箱即用。

核心: vm()无参数时自动选择开发测试VM，永远不默认到初始模拟器VM[0]。

用法:
  from vm_client import vm, vm_for, fleet

  # ★ 智能选择 (自动选开发测试VM, 非初始模拟器)
  vm().snapshot()               # 自动选运行中的开发测试VM
  vm().click("设置")            # 无需记忆index
  vm().health()                 # 健康检查

  # ★ 项目感知路由 (根据项目名自动选VM)
  vm_for("ScreenStream").snapshot()     # → VM[3]
  vm_for("手机购物订单").shell("ls")     # → VM[5]
  vm_for("二手书手机端").read()          # → VM[4]

  # 指定VM (需要精确控制时)
  vm(3).snapshot()              # UI快照
  vm(3).click("设置")           # 点击
  vm(3).type_text("hello")     # 输入
  vm(3).shell("ls /sdcard")    # shell
  vm(3).screenshot()           # 截屏
  vm(3).launch_app("com.android.chrome")  # 启动APP
  vm(3).read()                 # 读取屏幕
  vm(3).health()               # 健康检查
  vm(3).senses()               # 五感采集
  vm(3).wait_for("登录成功")    # 等待文字

  # 舰队操作
  fleet.list_all()             # 列出所有VM
  fleet.status()               # 全景状态
  fleet.running()              # 运行中的VM
  fleet.forward_all()          # 设置所有端口映射
  fleet.dev_vm()               # 获取默认开发测试VM
  fleet.vm_for("ScreenStream") # 项目感知选择

  # 批量操作
  for v in [vm(3), vm(4), vm(5)]:
      print(v.health())

  # 链式操作
  v = vm()  # 自动选开发测试VM
  v.home()
  v.launch_app("com.android.chrome")
  v.wait_for("搜索或输入网址", timeout=5)
  v.click("搜索或输入网址")
  v.type_text("github.com")
  v.key("ENTER")

浏览器MCP对照:
  browser_snapshot      →  vm(3).snapshot()
  browser_click         →  vm(3).click("text")
  browser_type          →  vm(3).type_text("text")
  browser_navigate      →  vm(3).launch_app("pkg") / vm(3).open_url("url")
  browser_evaluate      →  vm(3).shell("cmd")
  browser_press_key     →  vm(3).key("ENTER")
  browser_wait_for      →  vm(3).wait_for("text")
  take_screenshot       →  vm(3).screenshot()
  list_pages            →  fleet.list_all()
  select_page           →  vm(3)  # 直接选择
  browser_navigate_back →  vm(3).back()
  console_messages      →  vm(3).logcat()
"""

import sys, os

# 确保vm_controller可导入
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from vm_controller import VMFleet, VMPhone, DEV_VM_INDICES, DEFAULT_VM_INDEX, PROJECT_VM_MAP

# 全局舰队实例 (单例, 多Agent安全: VMPhone各自独立)
fleet = VMFleet()

def vm(index: int = None) -> VMPhone:
    """获取VM操控接口。无参数时自动选择开发测试VM(非初始模拟器)。
    
    Args:
        index: VM索引 (0, 3, 4, 5 等)。
               None时自动选择运行中的开发测试VM。
    
    Returns:
        VMPhone实例
    
    Example:
        v = vm()       # 自动选择开发测试VM
        v = vm(3)      # 指定VM[3]
        v.snapshot()   # UI快照
        v.click("OK")  # 点击
    """
    if index is None:
        return fleet.dev_vm()
    return fleet[index]


def vm_for(project: str) -> VMPhone:
    """根据项目名自动选择对应VM。
    
    Args:
        project: 项目名 (如 "ScreenStream", "手机操控库")
    
    Returns:
        VMPhone实例
    
    Example:
        v = vm_for("ScreenStream")  # 自动选择VM[3]
        v = vm_for("手机购物订单")    # 自动选择VM[5]
    """
    return fleet.vm_for(project)


# 便捷别名
list_vms = fleet.list_all
running_vms = fleet.running
all_status = fleet.status
forward_all = fleet.forward_all
dev_vm = fleet.dev_vm


def quick_test(index: int):
    """快速测试VM是否可操控"""
    v = vm(index)
    h = v.health()
    print(f"VM[{index}] {v.name}")
    print(f"  ADB:  {'✅' if h['checks'].get('adb') else '❌'}")
    print(f"  SS:   {'✅' if h['checks'].get('screenstream') else '❌'}")
    if h['checks'].get('screenstream'):
        r = v.read()
        print(f"  屏幕: {r.get('count', 0)} texts, pkg={r.get('package', '')}")
    return h


def batch_health():
    """批量健康检查所有运行中的VM"""
    results = {}
    for v in fleet.running():
        idx = v["index"]
        h = vm(idx).health()
        status = "✅" if h["healthy"] else "❌"
        print(f"  {status} VM[{idx}] {v['name']}")
        results[idx] = h
    return results
