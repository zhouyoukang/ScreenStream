#!/usr/bin/env python3
"""伏羲八卦全景验证 — Agent自动选择开发测试VM"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vm_client import vm, vm_for, fleet, dev_vm

results = []

def check(name, condition, detail=""):
    icon = "✅" if condition else "❌"
    results.append((name, condition))
    print(f"  {icon} {name}: {detail}")

print("=" * 60)
print("  伏羲八卦全景验证 · Agent自动选择开发测试VM")
print("=" * 60)

# ☰乾: vm()自动选择 — 必须返回开发VM(非VM[0])
print("\n☰乾 · vm()自动选择:")
v = vm()
check("vm()返回开发VM", v.index in [3, 4, 5], f"index={v.index} serial={v.serial}")
check("vm()不返回VM[0]", v.index != 0, f"index={v.index}")

# ☷坤: dev_vm()直接调用
print("\n☷坤 · dev_vm():")
dv = dev_vm()
check("dev_vm()返回开发VM", dv.index in [3, 4, 5], f"index={dv.index}")

# ☲离: 项目感知路由 — 12个项目全部正确路由
print("\n☲离 · 项目感知路由 (12项目):")
expected = {
    "ScreenStream": 3, "手机操控库": 3, "公网投屏": 3, "亲情远程": 3, "手机软路由": 3,
    "二手书手机端": 4, "电脑公网投屏手机": 4, "智能家居": 4, "微信公众号": 4,
    "手机购物订单": 5, "ORS6-VAM抖音同步": 5, "agent-phone-control": 5,
}
for proj, exp_idx in expected.items():
    actual = vm_for(proj).index
    check(f"{proj}", actual == exp_idx, f"→ VM[{actual}] (期望VM[{exp_idx}])")

# ☳震: 未知项目fallback — 必须fallback到开发VM
print("\n☳震 · 未知项目fallback:")
unknown = vm_for("不存在的项目")
check("未知项目→开发VM", unknown.index in [3, 4, 5], f"→ VM[{unknown.index}]")
check("未知项目≠VM[0]", unknown.index != 0, f"→ VM[{unknown.index}]")

# ☴巽: fleet.list_all() — VM列表
print("\n☴巽 · fleet.list_all():")
vms = fleet.list_all()
check("VM列表非空", len(vms) > 0, f"{len(vms)} VMs")
dev_names = [v["name"] for v in vms if v["index"] in [3, 4, 5]]
check("开发测试VM存在", len(dev_names) > 0, f"names={dev_names}")

# ☵坎: vm(0)警告机制
print("\n☵坎 · VM[0]访告机制:")
# 创建新fleet实例测试警告
from vm_controller import VMFleet
test_fleet = VMFleet()
import io
old_stderr = sys.stderr
sys.stderr = captured = io.StringIO()
test_fleet[0]
sys.stderr = old_stderr
warning = captured.getvalue()
check("vm(0)触发警告", "初始模拟器" in warning or "VM[0]" in warning, 
      f"警告内容: {warning.strip()[:60]}")

# ☶艮: 五感集成 — vm()返回的对象有五感方法
print("\n☶艮 · 五感集成:")
v = vm()
check("snapshot方法", hasattr(v, 'snapshot'), "browser_snapshot对等")
check("click方法", hasattr(v, 'click'), "browser_click对等")
check("senses方法", hasattr(v, 'senses'), "五感采集")
check("health方法", hasattr(v, 'health'), "健康检查")
check("read方法", hasattr(v, 'read'), "屏幕文字读取")

# ☱兑: 多Agent安全 — 不同fleet实例互不干扰
print("\n☱兑 · 多Agent安全:")
f1 = VMFleet()
f2 = VMFleet()
v1 = f1.dev_vm(prefer_running=False)
v2 = f2.dev_vm(prefer_running=False)
check("独立实例", v1 is not v2, "不同fleet的VMPhone独立")
check("同index", v1.index == v2.index, f"都选VM[{v1.index}]")

# 汇总
print("\n" + "=" * 60)
passed = sum(1 for _, ok in results if ok)
total = len(results)
status = "✅ 涅槃 · 全通过" if passed == total else f"⚠️ {total - passed}项未通过"
print(f"  八卦验证: {passed}/{total} {status}")
print("=" * 60)
