import sys
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
from vam.scenes import list_scenes, get_scene_info

scenes = list_scenes()
print(f"{len(scenes)} scenes found\n")
for s in scenes[:20]:
    print(f"  {s['name'][:55]:55s} {s['size_kb']:8.1f}KB  {s['modified']}  gen={s['is_generated']}")

# Show details of largest/most complex scenes
print("\n--- Scene details (top 5 by size) ---")
by_size = sorted(scenes, key=lambda x: x['size_kb'], reverse=True)[:5]
for s in by_size:
    try:
        info = get_scene_info(s['path'])
        print(f"\n  {s['name']}:")
        print(f"    atoms={info['atom_count']}, types={info['atom_types']}")
        if info['plugins']:
            print(f"    plugins={info['plugins'][:5]}")
        if info['voxta_characters']:
            print(f"    voxta={info['voxta_characters']}")
    except Exception as e:
        print(f"  {s['name']}: ERROR {e}")
