"""VP99 APK全量分析 — 零依赖, 纯zipfile+字符串提取"""
import zipfile, os, json

APK_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'vp99_extracted', 'apks')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'vp99_extracted')

def analyze_apk(path):
    fname = os.path.basename(path)
    size_mb = os.path.getsize(path) / 1024 / 1024
    try:
        z = zipfile.ZipFile(path)
        names = z.namelist()
        dex_files = [n for n in names if n.endswith('.dex')]
        so_files = [n for n in names if n.endswith('.so')]
        has_arm64 = any('arm64' in n for n in names)
        assets = [n for n in names if n.startswith('assets/')]

        # Extract key strings from first DEX
        key_strings = set()
        ble_uuids = set()
        urls = set()
        activities = set()

        for dex_name in dex_files[:2]:  # Limit to 2 DEX files
            try:
                dex_data = z.read(dex_name)
                strings = extract_ascii(dex_data, min_len=8)

                for s in strings:
                    sl = s.lower()
                    # BLE UUIDs (format: xxxx-xxxx or 0000xxxx)
                    if ('0000' in s and len(s) < 40 and '-' in s) or 'uuid' in sl:
                        ble_uuids.add(s)
                    # URLs
                    if ('http://' in sl or 'https://' in sl) and len(s) < 200:
                        urls.add(s)
                    # Activities
                    if 'Activity' in s and '/' in s and len(s) < 80:
                        activities.add(s)
            except Exception:
                pass

        z.close()
        return {
            'file': fname,
            'size_mb': round(size_mb, 1),
            'entries': len(names),
            'dex_count': len(dex_files),
            'native_count': len(so_files),
            'arm64': has_arm64,
            'asset_count': len(assets),
            'so_libs': [os.path.basename(s) for s in so_files],
            'ble_uuids': sorted(ble_uuids)[:20],
            'urls': sorted(urls)[:20],
            'activities': sorted(activities)[:30],
        }
    except Exception as e:
        return {'file': fname, 'size_mb': round(size_mb, 1), 'error': str(e)}


def extract_ascii(data, min_len=8):
    strings = []
    current = []
    for b in data:
        if 32 <= b <= 126:
            current.append(chr(b))
        else:
            if len(current) >= min_len:
                strings.append(''.join(current))
            current = []
    return strings


def main():
    results = []
    for fname in sorted(os.listdir(APK_DIR)):
        if not fname.endswith('.apk'):
            continue
        path = os.path.join(APK_DIR, fname)
        print(f"  Analyzing: {fname[:50]}...", flush=True)
        r = analyze_apk(path)
        results.append(r)

    # Save full analysis
    out_file = os.path.join(OUT_DIR, 'apk_deep_analysis.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    total_mb = sum(r.get('size_mb', 0) for r in results)
    total_entries = sum(r.get('entries', 0) for r in results)
    arm64 = sum(1 for r in results if r.get('arm64'))
    native = sum(1 for r in results if r.get('native_count', 0) > 0)
    all_urls = set()
    all_uuids = set()
    for r in results:
        all_urls.update(r.get('urls', []))
        all_uuids.update(r.get('ble_uuids', []))

    print(f"\n{'='*60}")
    print(f"VP99 APK Deep Analysis Complete")
    print(f"{'='*60}")
    print(f"APKs: {len(results)} | Total: {total_mb:.0f}MB | Files: {total_entries}")
    print(f"ARM64: {arm64} | Native: {native}")
    print(f"Unique URLs: {len(all_urls)} | BLE UUIDs: {len(all_uuids)}")

    print(f"\n--- Per-APK Summary ---")
    for r in results:
        if 'error' in r:
            print(f"  ERR {r['file'][:45]}: {r['error']}")
        else:
            tag = '64' if r['arm64'] else '32'
            print(f"  {r['file'][:45]:45s} {r['size_mb']:>7.1f}MB {r['entries']:>5d}f {r['dex_count']}d {r['native_count']:>3d}so {tag}")

    if all_urls:
        print(f"\n--- Discovered URLs ({len(all_urls)}) ---")
        for u in sorted(all_urls)[:30]:
            print(f"  {u}")

    if all_uuids:
        print(f"\n--- BLE UUIDs ({len(all_uuids)}) ---")
        for u in sorted(all_uuids)[:20]:
            print(f"  {u}")

    print(f"\nSaved to: {out_file}")


if __name__ == '__main__':
    main()
