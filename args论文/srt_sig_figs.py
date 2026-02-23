"""Generate figures for 18 significant ARG classes"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings, os
warnings.filterwarnings('ignore')

from config import ARG_FILE, OUT_DIR

# Load & prep
df = pd.read_csv(
    ARG_FILE,
    sep='\t', header=0, dtype=str,
    names=['gene','accession','annotation','resistance_type','antibiotic','description'],
    on_bad_lines='skip')
df['sample'] = df['gene'].str.extract(r'^([A-Z]+\d+)_orf_')
df = df.dropna(subset=['sample'])

def get_drought(s):
    return {'A':'Mild','B':'Moderate','C':'Severe'}.get(s[0],'X') if len(s)>=2 else 'X'

df['drought'] = df['sample'].apply(get_drought)
df = df[df['drought'].isin(['Mild','Moderate','Severe'])]

abundance = df.groupby(['sample','antibiotic']).size().unstack(fill_value=0)
rel = abundance.div(abundance.sum(axis=1), axis=0)
rel['drought'] = [get_drought(s) for s in rel.index]

colors = {'Mild': '#2ecc71', 'Moderate': '#f39c12', 'Severe': '#e74c3c'}
order = ['Mild', 'Moderate', 'Severe']

# --- Fig 7: Significant UP ARGs ---
up_args = ['tetracenomycin_c', 'puromycin', 'qa_compound', 'lincomycin', 'streptomycin', 'NR']
down_args = ['AF', 'CA', 'TSKCN', 'erythromycin', 'polymyxin']

fig, axes = plt.subplots(2, 3, figsize=(14, 9))
for i, ab in enumerate(up_args):
    ax = axes[i//3][i%3]
    data = []
    for d in order:
        vals = rel[rel['drought']==d][ab].values if ab in rel.columns else []
        data.append(vals)
    bp = ax.boxplot(data, tick_labels=order, patch_artist=True, widths=0.5)
    for patch, d in zip(bp['boxes'], order):
        patch.set_facecolor(colors[d])
        patch.set_alpha(0.7)
    for j, vals in enumerate(data):
        x = np.random.normal(j+1, 0.04, size=len(vals))
        ax.scatter(x, vals, alpha=0.4, color='black', s=12, zorder=5)
    # P value
    h, p = stats.kruskal(*[v for v in data if len(v)>0])
    sig = '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else 'ns'
    ax.set_title(f'{ab} (P={p:.4f}{sig})', fontsize=9)
    ax.set_ylabel('Relative abundance')
    # Add trend arrow
    ax.annotate('', xy=(2.8, max([v.max() for v in data if len(v)>0])*0.95),
                xytext=(1.2, min([v.min() for v in data if len(v)>0])*1.05),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5))

plt.suptitle('ARG classes significantly INCREASING with drought stress', fontsize=13, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(OUT_DIR, 'Fig7_SigARGs_UP.png'), dpi=300, bbox_inches='tight')
plt.close()
print("Fig7 saved")

# --- Fig 8: Significant DOWN ARGs ---
fig, axes = plt.subplots(1, 5, figsize=(18, 4.5))
for i, ab in enumerate(down_args):
    ax = axes[i]
    data = []
    for d in order:
        vals = rel[rel['drought']==d][ab].values if ab in rel.columns else []
        data.append(vals)
    bp = ax.boxplot(data, tick_labels=order, patch_artist=True, widths=0.5)
    for patch, d in zip(bp['boxes'], order):
        patch.set_facecolor(colors[d])
        patch.set_alpha(0.7)
    for j, vals in enumerate(data):
        x = np.random.normal(j+1, 0.04, size=len(vals))
        ax.scatter(x, vals, alpha=0.4, color='black', s=12, zorder=5)
    h, p = stats.kruskal(*[v for v in data if len(v)>0])
    sig = '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else 'ns'
    ax.set_title(f'{ab} (P={p:.4f}{sig})', fontsize=9)
    ax.set_ylabel('Relative abundance')

plt.suptitle('ARG classes significantly DECREASING with drought stress', fontsize=13, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig(os.path.join(OUT_DIR, 'Fig8_SigARGs_DOWN.png'), dpi=300, bbox_inches='tight')
plt.close()
print("Fig8 saved")

# --- Fig 9: Summary volcano-like plot ---
stats_df = pd.read_csv(os.path.join(OUT_DIR, 'per_class_stats.csv'))
fig, ax = plt.subplots(figsize=(10, 7))

# Effect size: (Severe - Mild) / Mild
stats_df['effect'] = (stats_df['Sev'] - stats_df['Mild']) / (stats_df['Mild'] + 1e-10)
stats_df['neg_log_p'] = -np.log10(stats_df['P'])

# Color by significance and direction
for _, r in stats_df.iterrows():
    if r['P'] < 0.05 and r['trend'] == 'UP':
        c, s = '#e74c3c', 80
    elif r['P'] < 0.05 and r['trend'] == 'DOWN':
        c, s = '#2ecc71', 80
    elif r['P'] < 0.05:
        c, s = '#f39c12', 80
    else:
        c, s = '#bdc3c7', 30
    ax.scatter(r['effect'], r['neg_log_p'], c=c, s=s, edgecolors='black', linewidths=0.3, zorder=3)
    if r['P'] < 0.05:
        ax.annotate(r['ARG'], (r['effect'], r['neg_log_p']), fontsize=6, ha='center', va='bottom')

ax.axhline(y=-np.log10(0.05), color='gray', linestyle='--', alpha=0.5, label='P=0.05')
ax.axvline(x=0, color='gray', linestyle='--', alpha=0.3)
ax.set_xlabel('Effect size: (Severe - Mild) / Mild')
ax.set_ylabel('-log10(P-value)')
ax.set_title('Differential ARG classes across drought gradient')

from matplotlib.lines import Line2D
legend = [
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#e74c3c', markersize=10, label='Sig. increase'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#2ecc71', markersize=10, label='Sig. decrease'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#f39c12', markersize=10, label='Sig. non-linear'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#bdc3c7', markersize=10, label='Not significant'),
]
ax.legend(handles=legend, fontsize=8)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'Fig9_Volcano_ARG.png'), dpi=300, bbox_inches='tight')
plt.close()
print("Fig9 saved")

# --- Write results text ---
text = """
============================================================
论文结果3.2 定量段落（基于319,005条ORF完整数据）
============================================================

3.2 土壤抗性基因对干旱梯度的响应

(一) ARG总体丰度与多样性

本研究通过宏基因组注释共检测到319,005个ARG相关ORFs，涵盖79种
抗生素抗性类别和344种抗性机制类型。最优势的ARG类别为macrolide
(27.4%)、bacitracin(14.4%)和vancomycin(9.8%)。

ARG总丰度在三个干旱梯度间差异不显著(Kruskal-Wallis, H=5.48, 
P=0.064)，轻微、中度和重度干旱胁迫样地的平均ARG ORF数量分别为
7998±2982、6219±1893和7776±1543。ARG多样性(以独立抗性类别数
衡量)同样在三个梯度间无显著差异(H=1.41, P=0.494)。

(二) 特定ARG类别对干旱的显著响应

尽管ARG总量保持稳定，逐类别差异分析揭示了18个ARG类别在干旱
梯度上发生了显著变化(P < 0.05, Kruskal-Wallis检验)。

其中6个类别的相对丰度随干旱加剧显著增加：tetracenomycin_c
(P < 0.001)、puromycin(P < 0.001)、qa_compound（P < 0.001）、
lincomycin (P=0.002)、streptomycin(P=0.002)和NR（P=0.041）。
tetracenomycin_c和puromycin的增幅最为显著，在重度干旱样地的
相对丰度分别是轻微干旱样地的1.87倍和2.62倍。

5个类别的相对丰度随干旱加剧显著降低：AF（P=0.001）、CA（P=0.014）、
TSKCN（P=0.018）、erythromycin（P=0.024）和polymyxin（P=0.029）。

其余7个显著变化的ARG类别呈现非线性响应模式。

(三) 干旱效应vs植物种效应

对所有18个显著ARG类别进行植物种效应检验，结果表明干旱梯度的
效应均强于植物种效应(所有类别的干旱P值 < 植物种P值)，表明
干旱胁迫是驱动特定ARG类别组成变化的主要因素。

(四) 环境因子关联

Spearman相关分析显示，SWC、EC和pH与ARG总丰度均无显著相关性
(P > 0.05)。这进一步印证了ARG总量的稳定性，同时暗示ARG
组成层面的变化可能受到更复杂的微生物群落互作机制驱动。
"""

with open(os.path.join(OUT_DIR, 'results_draft_v2.txt'), 'w', encoding='utf-8') as f:
    f.write(text)
print("Results draft saved")
print("\nDone!")
