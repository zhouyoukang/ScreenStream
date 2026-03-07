---
description: 图片→参数化3D模型的全自动建模。当用户发送图片要求建模、需要参数化CAD模型、或需要3D打印就绪的STL时自动触发。
---

# 3D Modeling Agent — 自主建模协议

> **核心原则**: Cascade = 大脑（分析/决策/生成/修正），forge.py = 双手（渲染/验证/对比/制造分析）。
> 所有智能由Agent提供，零外部API依赖。

## 工具链

| 工具 | 路径 | 用途 |
|------|------|------|
| forge.py | `3D建模Agent/forge.py` | 10命令工具箱 |
| OpenSCAD | `D:\openscad\openscad.com` | CSG渲染引擎 |
| trimesh | Python包 | 几何验证+制造分析 |
| Pillow | Python包 | 图像对比合成 |

## 自主循环（9步，不可跳过任何环节）

```
┌─────────────────────────────────────────────────────┐
│  用户发送图片/描述                                    │
└──────────────┬──────────────────────────────────────┘
               ↓
    ┌──── 1. 感知 ────┐
    │  read_file看图片  │
    │  解构需求:        │
    │  · 外形+功能      │
    │  · 物理逻辑       │
    │  · 制造约束       │
    └────────┬─────────┘
             ↓
    ┌──── 2. 规划 ────┐
    │  拆解子部件清单   │
    │  确定建模顺序     │
    │  确定装配策略     │
    │  估算关键尺寸     │
    └────────┬─────────┘
             ↓
    ┌──── 3. 建模 ────┐
    │  逐件写OpenSCAD  │
    │  每件独立module   │
    │  参数化Customizer │
    └────────┬─────────┘
             ↓
    ┌──── 4. 组装 ────┐
    │  assembly.scad   │
    │  装配+公差校验    │
    │  explode参数      │
    └────────┬─────────┘
             ↓
    ┌──── 5. 渲染 ────┐
    │  forge.py render │
    │  forge.py preview│
    │  4视角PNG        │
    └────────┬─────────┘
             ↓
    ┌──── 6. 对比 ────┐
    │  read_file看渲染  │
    │  vs参考图逐项比对 │
    │  轮廓/比例/细节   │
    └────────┬─────────┘
             ↓
    ┌──── 7. 诊断 ────┐
    │  定位偏差根因     │
    │  哪个子部件       │
    │  哪个参数         │
    └────────┬─────────┘
             ↓
    ┌──── 8. 修正 ────┐
    │  调整参数/代码    │
    │  → 回到步骤3     │
    └────────┬─────────┘
             ↓
    ┌──── 9. 收敛判定 ──┐
    │  三项均达标？      │
    │  · 几何轮廓 ✓     │
    │  · 比例关系 ✓     │
    │  · 功能完整 ✓     │
    │  → 终止+输出      │
    └───────────────────┘
```

## 步骤详解

### 1. 感知（Perceive）

```
输入: 用户发送的图片（read_file直接查看）+ 可选文字描述
输出: 结构化需求分析
```

**必须解构的四个维度：**
- **外形**: 整体轮廓、曲面特征、边缘处理（圆角/倒角/锐边）
- **功能**: 物体的用途决定了内部结构（容器需要腔体、铰链需要轴孔、卡扣需要弹性臂）
- **物理逻辑**: 重心位置、受力方向、运动副（旋转/滑动/固定）、装配关系
- **制造约束**: 打印方向、悬臂角度、最小壁厚、支撑需求

**尺寸估算策略：**
- 图中有已知物体（硬币、手指、尺子）→ 用作比例参考
- 图中无参考 → 根据功能推断合理尺寸（杯子80mm直径、手柄12mm宽）
- 用户给出尺寸 → 直接采用

### 2. 规划（Plan）

```
输入: 需求分析
输出: 子部件清单 + 建模顺序 + 装配策略
```

**子部件拆解原则：**
- 每个功能独立的结构是一个子部件
- 每个子部件有独立的参数化约束
- 子部件之间通过明确的装配接口连接
- 建模顺序：主体 → 附件 → 细节 → 装配

**执行命令：**
```bash
python forge.py init <project_name>
```
→ 创建 `projects/<name>/` 目录结构（reference/ parts/ output/ iterations/）

将参考图片复制到 `reference/` 目录。

### 3. 建模（Model）

**OpenSCAD代码规范（必须遵守）：**

```openscad
// 参数顶部声明，Customizer兼容
/* [主体 / Body] */
body_height = 100;    // [60:1:150] 主体高度 (mm)
body_diameter = 80;   // [50:1:120] 主体外径 (mm)
wall_thickness = 3;   // [1.5:0.5:8] 壁厚 (mm)

/* [渲染 / Render] */
quality = 64;         // [16:8:128] 渲染精度
explode = 0;          // [0:5:100] 爆炸视图间距

// 每组件一个module
module body() { ... }
module handle() { ... }

// 底部装配区
body();
translate([explode, 0, 0]) handle();
```

**关键约束：**
- 壁厚 ≥ 1.5mm（FDM）或 ≥ 0.5mm（SLA）
- 优先 `hull()` 而非 `minkowski()`（快10倍）
- 优先 `cube` + `hull` 而非 `sphere` + `hull`（避免47s→超时）
- `$fn=quality` 用于所有曲面
- 每个子部件写入 `parts/` 目录，assembly.scad 用 `use <parts/xxx.scad>`

**每个子部件的文件结构：**
```
parts/
├── body.scad       # 主体
├── handle.scad     # 把手
├── lid.scad        # 盖子
└── hinge.scad      # 铰链
```

### 4. 组装（Assemble）

编辑 `assembly.scad`：
- `use` 引入所有子部件
- 按装配关系 `translate`/`rotate` 定位
- `explode` 参数控制爆炸视图间距
- 检查配合公差（间隙0.2-0.3mm用于FDM活动配合）

### 5. 渲染（Render）

```bash
# 渲染STL
python forge.py render assembly.scad output/model.stl

# 几何验证
python forge.py validate output/model.stl

# 制造性分析
python forge.py manufacture output/model.stl --tech fdm

# 4视角预览
python forge.py preview assembly.scad output/
```

**渲染失败处理：**
- OpenSCAD错误 → 读错误信息，修复语法
- 超时(>300s) → 降低 `$fn`，简化 `hull` 链
- 零体积 → 检查 `difference()` 是否完全减空

### 6. 对比（Compare）

```bash
# 生成对比图
python forge.py compare reference/photo.jpg output/preview_iso.png iterations/compare_N.png --iter N
```

然后 `read_file` 查看对比图，逐项评估：

| 维度 | 检查方法 | 收敛标准 |
|------|---------|---------|
| 几何轮廓 | 叠加对比，检查错位 | 无可见错位 |
| 比例关系 | 关键尺寸比值 | 比值偏差<5% |
| 功能结构 | 铰链/卡扣/孔位是否齐全 | 全部建模 |
| 细节 | 圆角/倒角/纹理 | 主要特征还原 |

**五感代入验证（每轮必做）：**
- 👁 视觉：比例舒不舒服？看起来对不对？
- 🖐 触觉：拿在手里的感觉对不对？厚度/重量合理吗？
- 🧠 功能：这个东西能用吗？逻辑通不通？
- ⚙️ 制造：打印出来能不能成型？需要支撑吗？
- 📐 精度：尺寸关系正不正确？

### 7. 诊断（Diagnose）

定位偏差根因：
- **哪个子部件**偏差最大？
- **哪个参数**需要调整？
- **调整方向和幅度**是什么？

### 8. 修正（Fix）

使用 `edit` 或 `multi_edit` 修改对应的 `.scad` 文件参数。
每次只改一个变量维度（避免过度调整导致振荡）。

**记录迭代：**
```bash
python forge.py log projects/<name> '<iteration_json>'
```

其中 iteration_json 包含：
```json
{
  "deviations": ["把手太小", "主体锥度不对"],
  "fixes": ["handle_depth 28→35", "body_taper 0.9→0.85"],
  "metrics": {
    "geometry_match": "70%",
    "proportion_match": "80%",
    "function_complete": "90%",
    "printability_score": 74
  },
  "verdict": "继续迭代 / 已收敛",
  "converged": false
}
```

### 9. 收敛判定（Converge）

**三项指标全部达标 → 终止循环：**
1. **几何轮廓偏差**: 多角度渲染与参考图对比，无可见错位
2. **比例偏差**: 关键尺寸比值与参考图一致（<5%偏差）
3. **功能完整度**: 所有可推断的功能结构已建模

**附加条件：**
- `forge.py manufacture` 报告 `print_ready: true`
- `forge.py validate` 报告 `valid: true`

**最终输出：**
```bash
# 生成迭代报告
python forge.py report projects/<name>
```

输出物清单：
- `assembly.scad` — 参数化源码（可编辑、可调参）
- `output/model.stl` — 可直接切片打印的STL
- `output/preview_*.png` — 4视角预览图
- `report.md` — 迭代对比报告（每轮偏差+修正+收敛趋势）
- `parts/*.scad` — 各子部件源码

## 循环控制

- **最大迭代次数**: 8次（超过则输出当前最优结果 + 未收敛说明）
- **每次只改一个维度**: 避免多变量同时调整导致振荡
- **修复优先于重建**: 参数调整 > 重写module > 重新设计
- **渲染失败不计入迭代**: 语法错误修复不消耗迭代配额

## 已知OpenSCAD陷阱

| 陷阱 | 后果 | 解法 |
|------|------|------|
| `sphere()` + `hull()` | 47s→超时 | 用 `cube()` + `hull()`（2.8s） |
| `minkowski()` | 极慢 | 手动倒角或 `offset()` |
| 空 `font=""` | 渲染失败 | `font="Liberation Sans:style=Bold"` |
| 复杂布尔运算嵌套 | 指数爆炸 | 拆分为多步 `difference()`/`union()` |
| `$fn > 128` | 渐进慢 | `$fn=64` 足够，预览用32 |

## forge.py 命令速查

```bash
# 核心
python forge.py check                              # 环境检查
python forge.py render  <scad> [<stl>] [--fn N]    # 渲染STL
python forge.py validate <stl>                     # 几何验证
python forge.py preview <scad> <output_dir>        # 4视角PNG
python forge.py info <stl>                         # 网格信息

# 自主循环
python forge.py init <project_name>                # 创建项目
python forge.py compare <ref> <rendered> <out> [--iter N]  # 对比图
python forge.py manufacture <stl> [--tech fdm|sla] # 制造分析
python forge.py log <project_dir> '<json>'         # 记录迭代
python forge.py report <project_dir>               # 生成报告
```

## 禁止项

- **禁止** 产出非参数化的纯网格模型
- **禁止** 跳过对比验证直接输出终稿
- **禁止** 在循环中要求用户手动输入
- **禁止** 脱离IDE另建独立GUI
- **禁止** 只复制外壳忽略内部结构
- **禁止** 使用非OpenSCAD的建模工具（保持工具链统一）
