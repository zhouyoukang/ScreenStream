import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests
import warnings, os
warnings.filterwarnings('ignore')

from config import ARG_FILE, OUT_DIR

# Load
df = pd.read_csv(
    ARG_FILE,
    sep='\t', header=0, dtype=str,
    names=['gene','accession','annotation','resistance_type','antibiotic','description'],
    on_bad_lines='skip')
df['sample'] = df['gene'].str.extract(r'^([A-Z]+\d+)_orf_')
df = df.dropna(subset=['sample'])

def get_drought(s):
    return {'A':'Mild','B':'Moderate','C':'Severe'}.get(s[0],'X') if len(s)>=2 else 'X'
def get_plant(s):
    return {'D':'D','L':'L','P':'P'}.get(s[1],'X') if len(s)>=2 else 'X'

df['drought'] = df['sample'].apply(get_drought)
df['plant'] = df['sample'].apply(get_plant)
df = df[df['drought'].isin(['Mild','Moderate','Severe'])]

# Abundance matrix
abundance = df.groupby(['sample','antibiotic']).size().unstack(fill_value=0)
rel = abundance.div(abundance.sum(axis=1), axis=0)

# Per-class KW test across drought
results = []
for ab in rel.columns:
    g = {d: rel.loc[[s for s in rel.index if get_drought(s)==d], ab].values
         for d in ['Mild','Moderate','Severe']}
    try:
        h, p = stats.kruskal(g['Mild'], g['Moderate'], g['Severe'])
    except:
        continue
    m = {d: np.mean(v) for d,v in g.items()}
    if m['Mild'] < m['Moderate'] < m['Severe']:
        trend = 'UP'
    elif m['Mild'] > m['Moderate'] > m['Severe']:
        trend = 'DOWN'
    else:
        trend = 'NONLINEAR'
    results.append({
        'ARG': ab, 'P': p, 'H': h, 'sig': '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else '',
        'Mild': m['Mild'], 'Mod': m['Moderate'], 'Sev': m['Severe'], 'trend': trend
    })

res = pd.DataFrame(results).sort_values('P')

# Benjamini-Hochberg FDR correction
rej, qvals, _, _ = multipletests(res['P'].values, method='fdr_bh')
res['q'] = qvals
res['fdr_sig'] = ['***' if q<0.001 else '**' if q<0.01 else '*' if q<0.05 else '' for q in qvals]

sig = res[res['P']<0.05]
sig_fdr = res[res['q']<0.05]

print(f"=== {len(sig)} SIGNIFICANT (P<0.05) | {len(sig_fdr)} after FDR (q<0.05) | of {len(res)} total ===\n")
for _, r in sig.iterrows():
    fdr_mark = f" [FDR q={r['q']:.4f}{r['fdr_sig']}]" if r['q']<0.05 else f" [FDR q={r['q']:.3f} ns]"
    print(f"  {r['ARG']:22s} P={r['P']:.5f}{r['sig']:4s} {r['trend']:10s} Mi={r['Mild']:.4f} Mo={r['Mod']:.4f} Se={r['Sev']:.4f}{fdr_mark}")

border = res[(res['P']>=0.05) & (res['P']<0.10)]
print(f"\n=== {len(border)} BORDERLINE (0.05-0.10) ===")
for _, r in border.iterrows():
    print(f"  {r['ARG']:22s} P={r['P']:.5f} {r['trend']:10s} Mi={r['Mild']:.4f} Mo={r['Mod']:.4f} Se={r['Sev']:.4f}")

# Plant effect on significant ARGs
print(f"\n=== PLANT vs DROUGHT effect on sig ARGs ===")
for _, r in sig.iterrows():
    ab = r['ARG']
    gp = {p: rel.loc[[s for s in rel.index if get_plant(s)==p], ab].values for p in ['D','L','P']}
    try:
        hp, pp = stats.kruskal(gp['D'], gp['L'], gp['P'])
        stronger = 'PLANT' if pp < r['P'] else 'DROUGHT'
        print(f"  {ab:22s} Drought P={r['P']:.5f} | Plant P={pp:.5f} -> {stronger} stronger")
    except:
        pass

# Two-way: drought x plant interaction proxy
print(f"\n=== TOP PATTERNS ===")
up_drought = sig[sig['trend']=='UP']
down_drought = sig[sig['trend']=='DOWN']
nonlin = sig[sig['trend']=='NONLINEAR']
print(f"  Increase with drought: {len(up_drought)} ARGs")
for _, r in up_drought.iterrows():
    print(f"    {r['ARG']}: {r['Mild']:.4f} -> {r['Mod']:.4f} -> {r['Sev']:.4f}")
print(f"  Decrease with drought: {len(down_drought)} ARGs")
for _, r in down_drought.iterrows():
    print(f"    {r['ARG']}: {r['Mild']:.4f} -> {r['Mod']:.4f} -> {r['Sev']:.4f}")
print(f"  Non-linear: {len(nonlin)} ARGs")

res.to_csv(os.path.join(OUT_DIR, 'per_class_stats.csv'), index=False)
print(f"\nSaved to per_class_stats.csv")
