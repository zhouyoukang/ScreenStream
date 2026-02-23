# SRT论文：艾比湖荒漠土壤ARGs对干旱梯度的响应

> **核心叙事**："总量守恒、组成重构" — ARG总量在干旱梯度上稳定，但22.8%的类别发生显著重组
> **论文阶段**：可提交初稿（框架+核心章节+Word+10张图+统计表全部就绪）

---

## 项目身份证

| 维度 | 内容 |
|------|------|
| **英文标题** | ARG responses to drought gradient in Ebinur Lake desert soils: overall stability with compositional restructuring |
| **作者** | 周有康 · 新疆大学 生态与环境学院 |
| **研究区** | 艾比湖湿地国家自然保护区（EWNR） |
| **数据规模** | 319,005 ORFs × 43样本 × 79 ARG类别 × 344抗性机制 |

---

## 目录结构

```
args论文/
├── README.md                ← 本文件（唯一入口）
├── config.py                ← 路径配置（所有脚本共享）
├── srt_run_all.py           ← 一键运行全管线
├── srt_full_analysis.py     ← 主分析 → Fig1-6
├── srt_deep_stats.py        ← 逐类别KW检验 → per_class_stats.csv
├── srt_sig_figs.py          ← 显著性图 → Fig7-9
├── srt_permanova.py         ← PERMANOVA → PERMANOVA_results.csv
├── srt_final_figs.py        ← Fig9修正 + Fig10 + Table2
├── srt_make_docx.py         ← Word文档生成
├── requirements.txt         ← Python依赖
├── .gitignore               ← 排除大数据文件
├── 论文/
│   ├── SRT_论文完整框架.md  ← 论文markdown全文
│   ├── SRT_论文完整版.docx  ← 最终Word文档
│   └── SRT_核心文献清单.md  ← 10篇参考文献+获取方式
├── 数据/
│   ├── 1_gene_catalog_ardb_annotation.xls  ← 主数据(57MB, 319K条)
│   ├── ph_swc_ec.xlsx                      ← 环境因子(44样本)
│   └── 筛选数据2_小子集_仅参考.xlsx        ← ⚠️仅345条,不可用于定量
├── figures/                  ← 图表产出(可重新生成)
│   ├── Fig1-10              ← 10张出版级PNG
│   ├── per_class_stats.csv  ← 79个ARG的KW检验
│   ├── Table2_SigARGs_summary.csv  ← 18个显著ARG汇总
│   ├── PERMANOVA_results.csv       ← 三因子PERMANOVA
│   ├── results_draft_v2.txt        ← 结果定量段落
│   └── quantitative_results_full.txt ← 完整定量结果
└── 参考素材/
    ├── WoS_ARGs搜索结果.png
    ├── WoS_ARGs搜索结果_完整.png
    ├── srt项目5.14-5.18研究进展.docx
    └── srt项目进展2025.5.4.pptx
```

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 一键运行全管线（~2.5min）
python srt_run_all.py

# 或逐步运行
python srt_full_analysis.py      # ~30s, Fig1-6
python srt_deep_stats.py          # ~20s, 统计表
python srt_sig_figs.py            # ~10s, Fig7-9
python srt_permanova.py           # ~60s, PERMANOVA(999置换)
python srt_final_figs.py          # ~20s, Fig9修正+Fig10+Table2
python srt_make_docx.py           # ~5s, Word文档
```

---

## 核心发现

### 1. ARG总量稳定
- KW H=5.48, **P=0.064**（边际不显著）
- Mild=7998±2982, Moderate=6219±1893, Severe=7776±1543

### 2. 22.8%的ARG类别显著重组（18/79, FDR后8/79）
- **6类↑**：tetracenomycin_c(FC=1.87×), puromycin(FC=2.63×), qa_compound, lincomycin, streptomycin, NR
- **5类↓**：AF, CA, TSKCN, erythromycin, polymyxin
- **7类非线性**：tunicamycin, tigecycline, methicillin等

### 3. 环境因子与总量无关但与特定ARG强相关
- tetracenomycin_c vs SWC: rho=**-0.800** (P<0.001)

### 4. 干旱驱动力 > 植物种效应（在显著ARG上）

### 5. 根际vs非根际无显著差异

---

## 已修复的问题

| # | 问题 | 修复 |
|---|------|------|
| P1 | 自动生成的中文段落声称"ARG显著递减" | 替换为数据支持的正确结论(P=0.064 ns) |
| P2 | 同样错误结论写入结果文件 | 同步修正 |
| P3 | srt_analysis.py使用错误小数据集(345条) | 废弃，用srt_full_analysis.py替代 |
| P4 | PERMANOVA脚本有死代码 | 删除重复计算块 |
| P5 | Word文档生成器缺失Fig4和Fig6 | 添加到图表列表 |
| P6 | 所有脚本硬编码Desktop/OneDrive路径 | **统一到config.py相对路径** |
| P7 | 数据文件散落在3个位置 | **整合到数据/目录** |

---

## 提交前待办

### 必做（阻塞提交）
- [ ] 导师审阅并确认论文方向和叙事
- [ ] 确认样本命名映射（D/L/P = 红砂/白刺/骆驼刺）
- [ ] 确认根际/非根际划分（1-3/4-6）
- [ ] 运行 `python srt_make_docx.py` 重新生成含所有图的Word

### 建议（提升质量）
- [ ] 下载艾比湖ARGs核心参考论文 (DOI: 10.1016/j.ecoenv.2021.112455) 通过WebVPN
- [ ] 引言补充更多干旱×ARGs文献（当前10篇，建议15-20篇）
- [ ] 讨论加入与Zhang et al.(2021)艾比湖水体ARGs的对比
- [x] ~~多重比较校正~~ — 已实现BH FDR校正，FDR后8/79仍显著
- [ ] 考虑丰度标准化（RPK/TPM）后重新检验

### 可选（锦上添花）
- [ ] 网络分析（ARG-微生物共现网络）
- [ ] 功能基因分析（如果有KEGG注释数据）

---

## 数据来源

| 数据 | 本地路径 | 原始路径 | 状态 |
|------|---------|---------|------|
| ARG完整注释 | `数据/1_gene_catalog_ardb_annotation.xls` | 手机同步/三星多屏联动/ | ⚠️ 需确认是正式分析用数据 |
| 环境因子 | `数据/ph_swc_ec.xlsx` | OneDrive/相机图片/文档/ | ⚠️ 需确认数据完整性 |
| 筛选子集 | `数据/筛选数据2_小子集_仅参考.xlsx` | OneDrive/ | ❌ 仅345条,**不可用于定量** |

---

## 实验设计

```
研究区：艾比湖湿地 → 沿河岸由近到远设置3个采样带
         ↓
3个干旱梯度 × 3个植物种 × 根际/非根际 × 多重复 = 43样本
         ↓
宏基因组测序 → CARD数据库比对 → 319,005个ARG ORFs
         ↓
统计分析（KW检验 + PCoA + PERMANOVA + Spearman相关）
```

| 代码 | 干旱程度 | 样本数 | SWC范围(%) |
|------|----------|--------|------------|
| A | 轻微(Mild) | 15 | 14.08-19.37 |
| B | 中度(Moderate) | 12 | 5.46-12.59 |
| C | 重度(Severe) | 16 | 1.84-7.04 |

**样本命名规则**：`[A/B/C][D/L/P][1-6]` — 第1位:干旱, 第2位:植物种, 数字:1-3根际/4-6非根际
