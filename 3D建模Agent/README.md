# ModelForge — 图片→参数化3D模型 全自动管线

> 消弭意图与实物之间的一切摩擦。
> 任何人凭一张图片，将脑中所见无损地落地为手中可触摸的实物。

## 核心理念

**Cascade = 大脑**（分析图片/解构功能/生成代码/对比修正/收敛决策）
**forge.py = 双手**（渲染/验证/制造分析/图像对比/迭代追踪）
**零外部API依赖** — 无需联网/无需GPU/无需付费服务。

## 架构（自主感知-修正循环）

```
用户发送图片
       ↓
  ┌─ 1.感知 ─── 解构外形/功能/物理/制造 ─┐
  │  2.规划 ─── 拆解子部件+建模顺序       │
  │  3.建模 ─── 逐件参数化OpenSCAD        │
  │  4.组装 ─── 装配+公差校验              │
  │  5.渲染 ─── STL+验证+制造分析+预览     │
  │  6.对比 ─── 参考图vs渲染图逐项评估     │  自主循环
  │  7.诊断 ─── 定位偏差根因               │  (≤8轮)
  │  8.修正 ─── 调整参数 → 回到3           │
  └─ 9.收敛 ─── 三项达标 → 输出终稿+报告 ─┘
```

## 七项必达标准

1. **意图忠实** — 几何/比例/功能与参考图一致，物理逻辑（重心/受力/装配）还原
2. **可制造性** — FDM/SLA直接可打印，无需人工修补（`forge.py manufacture`验证）
3. **感知闭环** — 渲染→对比→诊断→修正自主循环至收敛
4. **零手动干预** — 用户发图后全链路自动
5. **结构解构** — 复杂物体拆解为独立参数化子部件，非表面网格雕刻
6. **五感代入** — 视觉比例、触感厚度、功能逻辑、制造可行性
7. **可追溯决策链** — 每轮迭代输出对比报告（偏差+修正+收敛趋势）

## 使用方式

在Windsurf中对Cascade说：
> 帮我把这张图片建模成参数化3D模型

附上图片。Agent自主完成全部工作，最终输出：
- `assembly.scad` — 参数化源码（可编辑/可调参）
- `output/model.stl` — 可直接切片打印的STL
- `output/preview_*.png` — 4视角预览图
- `report.md` — 迭代对比报告

## 项目结构

每个建模任务创建独立项目：
```
projects/<name>/
├── reference/          # 参考图片
├── parts/              # 子部件 .scad 文件
│   ├── body.scad
│   ├── handle.scad
│   └── lid.scad
├── output/             # STL + 预览PNG
├── iterations/         # 每轮对比图
├── assembly.scad       # 主装配文件
├── iteration_log.json  # 迭代追踪
└── report.md           # 最终报告
```

## forge.py 工具命令（10个）

```bash
# 核心
python forge.py check                              # 环境检查
python forge.py render  <scad> [<stl>] [--fn N]    # 渲染STL (JSON)
python forge.py validate <stl>                     # 几何验证 (JSON)
python forge.py preview <scad> <output_dir>        # 4视角PNG
python forge.py info <stl>                         # 网格信息 (JSON)

# 自主循环
python forge.py init <project_name>                # 创建项目目录
python forge.py compare <ref> <ren> <out> [--iter] # 参考图vs渲染图对比
python forge.py manufacture <stl> [--tech fdm|sla] # 制造性分析 (JSON)
python forge.py log <project_dir> '<json>'         # 记录迭代数据
python forge.py report <project_dir>               # 生成Markdown报告
```

## 制造性分析

`forge.py manufacture` 提供完整的3D打印就绪检查：
- **壁厚分析** — ray-casting采样500点，报告min/max/mean/中位数
- **悬臂分析** — 面法线角度分析，报告悬臂面积占比
- **底面接触** — 检测平底面积和稳定性
- **可打印评分** — 0-100综合评分

## 环境要求

| 依赖 | 用途 | 状态 |
|------|------|------|
| OpenSCAD 2021.01 | CSG渲染引擎 | ✅ `D:\openscad\` |
| Python 3.11 | 运行时 | ✅ |
| trimesh 4.11 | 几何验证+制造分析 | ✅ |
| rtree 1.4 | 空间索引（壁厚ray-casting） | ✅ |
| Pillow 10.3 | 图像对比合成 | ✅ |
| numpy | 数值计算 | ✅ |

## 参数化设计

```openscad
/* [杯身 / Body] */
body_height = 100;    // [60:1:150] 杯身高度 (mm)
body_diameter = 80;   // [50:1:120] 杯身外径 (mm)
wall_thickness = 3;   // [1.5:0.5:8] 壁厚 (mm)
```

修改方式：
1. **命令行**: `openscad -o new.stl -D "body_height=120" model.scad`
2. **GUI**: OpenSCAD Customizer面板拖动滑块
3. **代码**: 直接编辑 `.scad` 文件顶部数值

## 限制

- OpenSCAD CSG建模无法表达自由曲面（有机形态如人脸）
- 预览渲染质量受OpenSCAD 2021.01限制（无PBR材质）
- 壁厚分析依赖ray-casting采样，薄壁检测有±0.1mm误差

## 详细Agent协议

→ `.windsurf/skills/3d-modeling/SKILL.md`

## 已验证案例

- `demo/coffee_mug.scad` — 2组件13参数，2.84s渲染，912面流形，制造分析74分
