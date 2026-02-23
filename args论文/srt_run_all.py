"""
SRT论文项目 — 一键运行全部分析管线
执行顺序: full_analysis → deep_stats → sig_figs → permanova → final_figs → make_docx
"""
import subprocess, sys, time, os

SCRIPTS = [
    ('srt_full_analysis.py',  'Fig1-6 + 定量结果'),
    ('srt_deep_stats.py',     '逐类别KW检验 → per_class_stats.csv'),
    ('srt_sig_figs.py',       'Fig7/8/9 + 结果草稿'),
    ('srt_permanova.py',      'PERMANOVA分析'),
    ('srt_final_figs.py',     'Fig9修正 + Fig10 + Table2'),
    ('srt_make_docx.py',      'Word文档生成'),
]

BASE = os.path.dirname(os.path.abspath(__file__))
total_start = time.time()
failed = []

print("=" * 60)
print("SRT论文 — 完整分析管线")
print("=" * 60)

for i, (script, desc) in enumerate(SCRIPTS, 1):
    path = os.path.join(BASE, script)
    if not os.path.exists(path):
        print(f"\n[{i}/6] ❌ {script} — 文件不存在!")
        failed.append(script)
        continue

    print(f"\n{'─'*60}")
    print(f"[{i}/6] ▶ {script} — {desc}")
    print(f"{'─'*60}")

    start = time.time()
    result = subprocess.run([sys.executable, path], capture_output=False, text=True, cwd=BASE)
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\n  ❌ {script} 失败 (exit code {result.returncode}, {elapsed:.1f}s)")
        failed.append(script)
    else:
        print(f"\n  ✅ {script} 完成 ({elapsed:.1f}s)")

total = time.time() - total_start
print(f"\n{'='*60}")
print(f"管线完成! 总耗时 {total:.1f}s")

if failed:
    print(f"⚠️ 失败的脚本: {', '.join(failed)}")
else:
    print("✅ 全部6个脚本成功")

# Verify outputs
out_dir = os.path.join(BASE, 'figures')
expected = [
    'Fig1_ARG_abundance_drought.png', 'Fig2_PCoA_ARG.png', 'Fig3_Heatmap_ARG.png',
    'Fig4_EnvFactor_correlation.png', 'Fig5_ARG_composition.png', 'Fig6_Rhizo_vs_Bulk.png',
    'Fig7_SigARGs_UP.png', 'Fig8_SigARGs_DOWN.png', 'Fig9_Volcano_ARG.png',
    'Fig10_SigARG_EnvCorr.png', 'per_class_stats.csv', 'Table2_SigARGs_summary.csv',
    'PERMANOVA_results.csv', 'results_draft_v2.txt', 'quantitative_results_full.txt',
]
print(f"\n{'='*60}")
print(f"产出验证 ({out_dir})")
print(f"{'='*60}")
missing = []
for f in expected:
    p = os.path.join(out_dir, f)
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"  ✅ {f} ({sz//1024}KB)" if sz > 1024 else f"  ✅ {f} ({sz}B)")
    else:
        print(f"  ❌ {f} — 缺失!")
        missing.append(f)

docx = os.path.join(BASE, '论文', 'SRT_论文完整版.docx')
if os.path.exists(docx):
    print(f"\n  ✅ SRT_论文完整版.docx ({os.path.getsize(docx)//1024}KB)")
else:
    print(f"\n  ❌ SRT_论文完整版.docx — 缺失!")

if not missing and not failed:
    print(f"\n🎉 全部{len(expected)}个产出文件 + Word文档就绪!")
