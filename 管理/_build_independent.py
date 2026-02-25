#!/usr/bin/env python3
"""
校园书市v2.0 — 独立多校区版构建脚本
从三鲜快照导出种子数据 → 生成静态JSON → 重写数据层
"""
import json, pathlib, re, shutil

BASE = pathlib.Path(r"E:\道\二手书\bookshop-pwa")
SNAP_DIR = pathlib.Path(r"E:\道\二手书\data\sanxian")
DATA_OUT = BASE / "public" / "data"

# ── Step 1: Load sanxian snapshot ──
snap = sorted(SNAP_DIR.glob("snapshot_*.json"), reverse=True)[0]
raw = json.loads(snap.read_text(encoding="utf-8"))
goods_all = raw["goods"]["rows"]
orders_all = raw["school_orders"]["rows"]
businesses = raw["businesses"]["rows"]
categories = raw["goods_types"]["rows"]

print(f"Loaded: {len(goods_all)} goods, {len(orders_all)} orders, {len(businesses)} businesses, {len(categories)} categories")

# ── Step 2: Organize by campus (business) ──
DATA_OUT.mkdir(parents=True, exist_ok=True)

# Filter test products
def is_test(name):
    return bool(re.search(r'test|TEST|Modified|API-TEST', name or ''))

# Filter bad categories
def is_good_category(name):
    if not name: return False
    if len(name) > 15: return False
    if re.search(r'微信|blxn|配送|统一', name): return False
    return True

# Build campus map
campus_map = {}
for b in businesses:
    bid = str(b.get("business_id", ""))
    campus_map[bid] = {
        "id": bid,
        "name": b.get("business_name", "未知店铺"),
        "address": b.get("business_address", ""),
        "phone": b.get("phone", ""),
        "image": b.get("business_image", ""),
    }

# Organize goods by campus
campus_goods = {}
for g in goods_all:
    if is_test(g.get("goods_name")): continue
    bid = str(g.get("business_id", "unknown"))
    campus_goods.setdefault(bid, []).append({
        "id": g["id"],
        "name": g.get("goods_name", ""),
        "price": float(g.get("price", 0)),
        "image": g.get("goods_img", ""),
        "stock": int(g.get("stock", 0)),
        "status": int(g.get("status", 0)),
        "category_id": str(g.get("goods_type_id", "")),
        "category": g.get("goods_type_name", ""),
        "description": g.get("goods_content", ""),
        "campus_id": bid,
    })

# Filter categories
clean_cats = []
seen_names = set()
for c in categories:
    name = c.get("goods_type_name", "")
    if is_good_category(name) and name not in seen_names:
        seen_names.add(name)
        clean_cats.append({
            "id": str(c.get("goods_type_id", "")),
            "name": name,
            "campus_id": str(c.get("business_id", "")),
        })

# ── Step 3: Write static JSON files ──

# Campuses index
campuses_list = []
for bid, info in campus_map.items():
    goods = campus_goods.get(bid, [])
    active = [g for g in goods if g["status"] == 1 and g["stock"] > 0]
    campuses_list.append({
        **info,
        "goods_count": len(active),
        "slug": f"campus-{bid}",
    })
campuses_list.sort(key=lambda x: -x["goods_count"])

(DATA_OUT / "campuses.json").write_text(
    json.dumps(campuses_list, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Written: campuses.json ({len(campuses_list)} campuses)")

# All goods (flat, for simple loading)
all_goods = []
for bid, goods in campus_goods.items():
    all_goods.extend(goods)
all_goods.sort(key=lambda x: -x["stock"])

(DATA_OUT / "goods.json").write_text(
    json.dumps(all_goods, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Written: goods.json ({len(all_goods)} goods, test products filtered)")

# Categories
(DATA_OUT / "categories.json").write_text(
    json.dumps(clean_cats, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Written: categories.json ({len(clean_cats)} categories, bad names filtered)")

# Per-campus goods (for future campus-specific loading)
for bid, goods in campus_goods.items():
    campus_dir = DATA_OUT / f"campus-{bid}"
    campus_dir.mkdir(exist_ok=True)
    (campus_dir / "goods.json").write_text(
        json.dumps(goods, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nStatic data exported to {DATA_OUT}")
print(f"Campuses: {[c['name'] for c in campuses_list]}")

# ── Step 4: Write new data provider (replaces api/client.js) ──
provider_code = '''/**
 * 数据提供者 — 独立版（无外部API依赖）
 * 从静态JSON加载数据，支持多校区筛选
 */

const BASE = import.meta.env.BASE_URL + 'data'
let _goodsCache = null
let _categoriesCache = null
let _campusesCache = null

async function loadJSON(path) {
  try {
    const res = await fetch(`${BASE}/${path}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.warn(`Load ${path} failed:`, err)
    return []
  }
}

// ==================== 校区 ====================

export async function fetchCampuses() {
  if (!_campusesCache) _campusesCache = await loadJSON('campuses.json')
  return _campusesCache
}

// ==================== 商品 ====================

export async function fetchGoods(campusId = null) {
  if (!_goodsCache) _goodsCache = await loadJSON('goods.json')
  let goods = _goodsCache
  if (campusId) {
    goods = goods.filter(g => String(g.campus_id) === String(campusId))
  }
  return goods
}

export async function fetchGoodsById(id) {
  const goods = await fetchGoods()
  return goods.find(g => String(g.id) === String(id)) || null
}

// ==================== 分类 ====================

export async function fetchCategories(campusId = null) {
  if (!_categoriesCache) _categoriesCache = await loadJSON('categories.json')
  let cats = _categoriesCache
  if (campusId) {
    cats = cats.filter(c => String(c.campus_id) === String(campusId))
  }
  return cats
}

// ==================== 状态 ====================

export async function fetchStatus() {
  const goods = await fetchGoods()
  const campuses = await fetchCampuses()
  const active = goods.filter(g => g.status === 1 && g.stock > 0)
  return {
    success: true,
    goods_count: active.length,
    campuses_count: campuses.length,
    categories_count: (await fetchCategories()).length,
    data_source: 'static',
  }
}
'''

(BASE / "src" / "data").mkdir(exist_ok=True)
(BASE / "src" / "data" / "provider.js").write_text(provider_code, encoding="utf-8")
print("Written: src/data/provider.js")

# ── Step 5: Write campus store ──
campus_store = '''import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useCampusStore = create(
  persist(
    (set) => ({
      campusId: null,
      campusName: null,
      setCampus: (id, name) => set({ campusId: id, campusName: name }),
      clearCampus: () => set({ campusId: null, campusName: null }),
    }),
    { name: 'bookshop-campus' }
  )
)
'''
(BASE / "src" / "store" / "campus.js").write_text(campus_store, encoding="utf-8")
print("Written: src/store/campus.js")

print("\n✅ All files generated successfully!")
print("Next: Rewrite pages to use data/provider.js instead of api/client.js")
