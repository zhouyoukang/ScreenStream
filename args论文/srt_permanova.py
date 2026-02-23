"""PERMANOVA + ANOSIM for ARG community composition"""
import pandas as pd
import numpy as np
from scipy.spatial.distance import braycurtis, pdist, squareform
from itertools import permutations
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

def get_meta(s):
    drought = {'A':'Mild','B':'Moderate','C':'Severe'}.get(s[0],'X') if len(s)>=2 else 'X'
    plant = {'D':'D','L':'L','P':'P'}.get(s[1],'X') if len(s)>=2 else 'X'
    num = int(''.join(filter(str.isdigit, s))) if any(c.isdigit() for c in s) else 0
    soil = 'Rhizo' if num <= 3 else 'Bulk'
    return drought, plant, soil

df['drought'] = df['sample'].apply(lambda s: get_meta(s)[0])
df = df[df['drought'].isin(['Mild','Moderate','Severe'])]

abundance = df.groupby(['sample','antibiotic']).size().unstack(fill_value=0)
rel = abundance.div(abundance.sum(axis=1), axis=0)

samples = rel.index.tolist()
meta = pd.DataFrame([get_meta(s) for s in samples], columns=['drought','plant','soil'], index=samples)

# Bray-Curtis distance matrix
print("Computing Bray-Curtis distance matrix...")
n = len(samples)
D = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        D[i,j] = braycurtis(rel.iloc[i].values, rel.iloc[j].values)
D = np.nan_to_num(D)

# Simple PERMANOVA implementation
def permanova(D, groups, n_perm=999):
    """Permutation-based PERMANOVA (Anderson 2001)"""
    unique_groups = sorted(set(groups))
    n = len(groups)

    # SS_total
    ss_total = np.sum(D**2) / n

    # SS_within (sum of squared distances within groups, divided by group size)
    def calc_ss_within(grp):
        ss_w = 0
        for g in unique_groups:
            idx = [i for i, x in enumerate(grp) if x == g]
            ng = len(idx)
            if ng > 0:
                for i in range(len(idx)):
                    for j in range(i+1, len(idx)):
                        ss_w += D[idx[i], idx[j]]**2 / ng
        return ss_w

    ss_within_obs = calc_ss_within(groups)
    ss_between_obs = ss_total - ss_within_obs

    k = len(unique_groups)
    f_obs = (ss_between_obs / (k - 1)) / (ss_within_obs / (n - k)) if ss_within_obs > 0 else 0

    # Permutation test
    count = 0
    for _ in range(n_perm):
        perm_groups = list(np.random.permutation(groups))
        ss_w_perm = calc_ss_within(perm_groups)
        ss_b_perm = ss_total - ss_w_perm
        f_perm = (ss_b_perm / (k-1)) / (ss_w_perm / (n-k)) if ss_w_perm > 0 else 0
        if f_perm >= f_obs:
            count += 1

    p_value = (count + 1) / (n_perm + 1)
    r2 = ss_between_obs / ss_total

    return f_obs, p_value, r2

# Run PERMANOVA for each factor
print("\n=== PERMANOVA Results (999 permutations) ===\n")

factors = {
    'Drought': meta['drought'].tolist(),
    'Plant': meta['plant'].tolist(),
    'Soil_type': meta['soil'].tolist(),
}

results = []
for name, groups in factors.items():
    print(f"Testing: {name}...")
    f, p, r2 = permanova(D, groups)
    sig = '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else 'ns'
    print(f"  F={f:.4f}, P={p:.4f} {sig}, R2={r2:.4f} ({r2*100:.1f}% variance explained)")
    results.append({'Factor': name, 'F': f, 'P': p, 'R2': r2, 'sig': sig})

# Pairwise PERMANOVA for drought
print("\n=== Pairwise PERMANOVA (Drought) ===\n")
for d1 in ['Mild','Moderate','Severe']:
    for d2 in ['Mild','Moderate','Severe']:
        if d1 < d2:
            idx = [i for i, s in enumerate(samples) if meta.loc[s,'drought'] in [d1,d2]]
            sub_D = D[np.ix_(idx, idx)]
            sub_groups = [meta.iloc[i]['drought'] for i in idx]
            f, p, r2 = permanova(sub_D, sub_groups, n_perm=499)
            sig = '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else 'ns'
            print(f"  {d1} vs {d2}: F={f:.4f}, P={p:.4f} {sig}, R2={r2:.4f}")

# Save results
res_df = pd.DataFrame(results)
res_df.to_csv(os.path.join(OUT_DIR, 'PERMANOVA_results.csv'), index=False)
print(f"\nResults saved to PERMANOVA_results.csv")

# Summary for paper
print("\n=== 论文可用文本 ===")
print("PERMANOVA分析(基于Bray-Curtis距离, 999次置换)表明：")
for r in results:
    factor_cn = {'Drought':'干旱梯度', 'Plant':'植物种', 'Soil_type':'土壤类型(根际/非根际)'}
    print(f"  {factor_cn[r['Factor']]}解释了ARG组成变异的{r['R2']*100:.1f}%"
          f" (F={r['F']:.2f}, P={r['P']:.3f} {r['sig']})")
