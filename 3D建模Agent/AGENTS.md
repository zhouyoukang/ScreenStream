# 3D建模Agent — 目录级指令

## 本目录职责
图片→参数化3D模型的全自动管线。**Cascade = 大脑**（分析/决策/生成/修正），**forge.py = 双手**（渲染/验证/对比/制造分析）。

## 架构（自主感知-修正循环）
```
感知(图片) → 规划(子部件) → 建模(OpenSCAD) → 组装 → 渲染
    ↑                                                    ↓
    └──── 修正 ← 诊断 ← 对比(参考vs渲染) ← 制造验证 ←──┘
                         ↓ (三项收敛)
                    输出终稿 + 报告
```
**零外部API依赖** — 所有智能由IDE内Agent提供。

## 七项必达标准
1. **意图忠实** — 几何/比例/功能与参考图一致
2. **可制造性** — FDM/SLA直接可打印（`forge.py manufacture`验证）
3. **感知闭环** — 渲染→对比→诊断→修正自主循环至收敛
4. **零手动干预** — 全链路无需用户再输入
5. **结构解构** — 拆解为独立参数化子部件，非表面雕刻
6. **五感代入** — 视觉比例、触感厚度、功能逻辑、制造可行性
7. **可追溯** — 每轮迭代输出对比报告

## 项目结构
```
projects/<name>/
├── reference/          # 参考图片
├── parts/              # 子部件 .scad 文件
├── output/             # STL + 预览PNG
├── iterations/         # 每轮对比图
├── assembly.scad       # 主装配文件
├── iteration_log.json  # 迭代追踪
└── report.md           # 最终报告
```

## 自主循环（9步）
1. **感知**: `read_file`看图 → 解构外形/功能/物理/制造四维度
2. **规划**: 拆解子部件清单 → `python forge.py init <name>`
3. **建模**: 逐件写OpenSCAD（参数化/Customizer兼容/每件独立module）
4. **组装**: assembly.scad装配+公差校验+explode参数
5. **渲染**: `forge.py render` → `validate` → `manufacture` → `preview`
6. **对比**: `forge.py compare` + `read_file`查看对比图 → 逐项评估
7. **诊断**: 定位偏差根因（哪个部件/哪个参数）
8. **修正**: 调整参数（每次只改一个维度）→ 回到步骤3
9. **收敛**: 几何+比例+功能三项达标 → `forge.py report` → 输出终稿

## forge.py 命令（10个）
```bash
# 核心
python forge.py check                              # 环境检查
python forge.py render  <scad> [<stl>] [--fn N]    # 渲染STL
python forge.py validate <stl>                     # 几何验证
python forge.py preview <scad> <output_dir>        # 4视角PNG
python forge.py info <stl>                         # 网格信息

# 自主循环
python forge.py init <project_name>                # 创建项目
python forge.py compare <ref> <ren> <out> [--iter] # 对比图
python forge.py manufacture <stl> [--tech fdm|sla] # 制造分析
python forge.py log <project_dir> '<json>'         # 记录迭代
python forge.py report <project_dir>               # 生成报告
```

## OpenSCAD代码规范
- 参数顶部声明：`body_height = 100; // [60:1:150] 杯身高度 (mm)`
- 分组注释：`/* [杯身 / Body] */`
- 每组件一个module，每件存 `parts/` 目录
- 底部装配区：`body(); translate([explode,0,0]) handle();`
- `$fn=quality` 用于所有曲面
- 壁厚 ≥ 1.5mm（FDM）/ ≥ 0.5mm（SLA）
- 优先 `hull()` > `minkowski()`，优先 `cube` > `sphere`

## 工具链
- OpenSCAD 2021.01: `D:\openscad\openscad.com`
- trimesh 4.11 + rtree: 几何验证+制造分析（壁厚/悬臂/底面）
- Pillow 10.3: 图像对比合成
- 无需API Key / 无需联网 / 无需GPU

## 详细协议
→ `.windsurf/skills/3d-modeling/SKILL.md`

## 已验证
- `demo/coffee_mug.scad` — 2组件13参数，2.84s渲染，912面流形
- `manufacture` — 壁厚ray-casting(500采样)/悬臂分析/底面接触/可打印评分
