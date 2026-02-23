"""Fix volcano plot + deep correlation for 18 sig ARGs + summary table"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings, os, openpyxl
warnings.filterwarnings('ignore')

from config import ARG_FILE, ENV_FILE, OUT_DIR

# Load ARG data
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

# Load env data
wb = openpyxl.load_workbook(ENV_FILE, data_only=True)
ws = wb['Sheet1']
env = {}
for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    name = str(row[0].value) if row[0].value else ''
    if name:
        env[name] = {
            'pH': float(row[1].value) if row[1].value else None,
            'EC': float(row[2].value) if row[2].value else None,
            'SWC': float(row[3].value) if row[3].value else None
        }

# Stats from previous run
stats_df = pd.read_csv(os.path.join(OUT_DIR, 'per_class_stats.csv'))
sig_args = stats_df[stats_df['P'] < 0.05]['ARG'].tolist()

# --- Fix Fig9: Volcano with capped effect size ---
print("Fixing Fig9 volcano plot...")
fig, ax = plt.subplots(figsize=(10, 7))

# Use log2 fold change instead
stats_df['log2fc'] = np.log2((stats_df['Sev'] + 1e-6) / (stats_df['Mild'] + 1e-6))
stats_df['neg_log_p'] = -np.log10(stats_df['P'])

for _, r in stats_df.iterrows():
    if r['P'] < 0.05 and r['trend'] == 'UP':
        c, s = '#e74c3c', 90
    elif r['P'] < 0.05 and r['trend'] == 'DOWN':
        c, s = '#2ecc71', 90
    elif r['P'] < 0.05:
        c, s = '#f39c12', 90
    else:
        c, s = '#bdc3c7', 30
    ax.scatter(r['log2fc'], r['neg_log_p'], c=c, s=s, edgecolors='black', linewidths=0.3, zorder=3)
    if r['P'] < 0.05:
        offset = (5, 5) if r['log2fc'] > 0 else (-5, 5)
        ax.annotate(r['ARG'], (r['log2fc'], r['neg_log_p']), fontsize=7, 
                   ha='left' if r['log2fc']>0 else 'right', va='bottom',
                   xytext=offset, textcoords='offset points')

ax.axhline(y=-np.log10(0.05), color='gray', linestyle='--', alpha=0.5)
ax.axvline(x=0, color='gray', linestyle='--', alpha=0.3)
ax.set_xlabel('log2(Fold Change: Severe / Mild)', fontsize=11)
ax.set_ylabel('-log10(P-value)', fontsize=11)
ax.set_title('Differential ARG classes across drought gradient', fontsize=13)

from matplotlib.lines import Line2D
legend = [
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#e74c3c', markersize=10, label='Sig. increase with drought'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#2ecc71', markersize=10, label='Sig. decrease with drought'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#f39c12', markersize=10, label='Sig. non-linear'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#bdc3c7', markersize=10, label='Not significant'),
]
ax.legend(handles=legend, fontsize=9, loc='upper left')

# Set reasonable x limits (cap at +-5)
xlim = max(abs(stats_df['log2fc'].quantile(0.02)), abs(stats_df['log2fc'].quantile(0.98))) * 1.2
xlim = min(xlim, 5)
ax.set_xlim(-xlim, xlim)

plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'Fig9_Volcano_ARG.png'), dpi=300, bbox_inches='tight')
plt.close()
print("  -> Fig9 fixed")

# --- Fig10: Sig ARGs correlation with env factors ---
print("Generating Fig10: Sig ARGs vs env factors...")

# Build per-sample relative abundance for sig ARGs + env
sig_data = rel[sig_args].copy()
for s in sig_data.index:
    if s in env:
        for var in ['pH', 'EC', 'SWC']:
            sig_data.loc[s, var] = env[s][var]

sig_data = sig_data.dropna(subset=['pH', 'EC', 'SWC'])

# Correlation matrix: sig ARGs vs env factors
corr_results = []
for ab in sig_args:
    for var in ['SWC', 'EC', 'pH']:
        valid = sig_data.dropna(subset=[ab, var])
        if len(valid) > 5:
            rho, p = stats.spearmanr(valid[var].astype(float), valid[ab].astype(float))
            corr_results.append({'ARG': ab, 'EnvFactor': var, 'rho': rho, 'P': p,
                                'sig': '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else ''})

corr_df = pd.DataFrame(corr_results)

# Heatmap of correlations
corr_matrix = corr_df.pivot(index='ARG', columns='EnvFactor', values='rho')
sig_matrix = corr_df.pivot(index='ARG', columns='EnvFactor', values='sig')

# Order by drought trend
trend_order = stats_df[stats_df['P']<0.05].sort_values(['trend', 'P'])['ARG'].tolist()
corr_matrix = corr_matrix.reindex(trend_order)
sig_matrix = sig_matrix.reindex(trend_order)

fig, ax = plt.subplots(figsize=(6, 10))
sns.heatmap(corr_matrix[['SWC','EC','pH']], cmap='RdBu_r', center=0, vmin=-0.6, vmax=0.6,
            ax=ax, linewidths=0.5, linecolor='white', annot=True, fmt='.2f', annot_kws={'size': 8})

# Add significance stars
for i, arg in enumerate(corr_matrix.index):
    for j, var in enumerate(['SWC', 'EC', 'pH']):
        star = sig_matrix.loc[arg, var] if pd.notna(sig_matrix.loc[arg, var]) else ''
        if star:
            ax.text(j + 0.5, i + 0.8, star, ha='center', va='center', fontsize=8, color='black', fontweight='bold')

ax.set_title('Spearman correlation: Sig. ARGs vs Environmental factors', fontsize=10)
ax.set_ylabel('ARG class (ordered by drought response)', fontsize=9)

plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'Fig10_SigARG_EnvCorr.png'), dpi=300, bbox_inches='tight')
plt.close()
print("  -> Fig10 saved")

# Print significant correlations
print("\n=== Significant ARG-Environment correlations ===")
sig_corr = corr_df[corr_df['P'] < 0.05].sort_values('P')
for _, r in sig_corr.iterrows():
    print(f"  {r['ARG']:22s} ~ {r['EnvFactor']:4s}: rho={r['rho']:.3f}, P={r['P']:.5f} {r['sig']}")

# --- Summary table ---
print("\nGenerating summary table...")
summary = stats_df[stats_df['P']<0.05][['ARG', 'P', 'sig', 'Mild', 'Mod', 'Sev', 'trend']].copy()
summary['FC_Sev_Mild'] = ((summary['Sev'] + 1e-6) / (summary['Mild'] + 1e-6)).round(2)

# Add env correlations
for var in ['SWC', 'EC', 'pH']:
    summary[f'{var}_rho'] = summary['ARG'].map(
        corr_df[corr_df['EnvFactor']==var].set_index('ARG')['rho'])
    summary[f'{var}_sig'] = summary['ARG'].map(
        corr_df[corr_df['EnvFactor']==var].set_index('ARG')['sig'])

summary.to_csv(os.path.join(OUT_DIR, 'Table2_SigARGs_summary.csv'), index=False)
print("  -> Table2_SigARGs_summary.csv saved")
print("\nDone!")
