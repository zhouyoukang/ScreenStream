#!/usr/bin/env python3
"""
校园书市 v2.2 — 融合三鲜小程序UX精华
精华: 店铺卡片+商品横滑预览+分类Tab+校内badge+销量统计
糟粕: 骑手/开店/个人微信/空banner/社交圈子
"""
import pathlib

BASE = pathlib.Path(r"E:\道\二手书\bookshop-pwa\src")

def write(rel_path, content):
    p = BASE / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"  Written: {rel_path}")

# ══════════════════════════════════════════════
# Home.jsx — 融合三鲜小程序UX（店铺卡片+分类Tab+校内badge）
# ══════════════════════════════════════════════
write("pages/Home.jsx", """
import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Search, ChevronRight, BookOpen, MapPin, ChevronDown, Store, ShoppingBag, Sparkles } from 'lucide-react'
import { fetchGoods, fetchCampuses } from '../data/provider'
import { useCampusStore } from '../store/campus'

function PriceTag({ price }) {
  const p = parseFloat(price || 0)
  return (
    <span className="text-red-500 font-bold text-sm">
      <span className="text-[10px]">¥</span>{p.toFixed(p % 1 === 0 ? 0 : 2)}
    </span>
  )
}

/* ── 店铺卡片（精华：三鲜小程序核心模式） ── */
function ShopCard({ shop, goods }) {
  const activeGoods = goods.filter(g => g.status === 1 && g.stock > 0)
  const previewGoods = activeGoods.slice(0, 6)
  if (activeGoods.length === 0) return null

  return (
    <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
      {/* 店铺头部 */}
      <div className="px-4 pt-3 pb-2 flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-100 to-primary-50 flex items-center justify-center shrink-0">
          <Store size={22} className="text-primary-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-gray-800 truncate">{shop.name}</h3>
            <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 font-medium">校内</span>
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5 flex items-center gap-2">
            <span>{activeGoods.length}件在售</span>
            {shop.type === 'textbook' && <span className="text-primary-500">· 教材预定</span>}
            {shop.type === 'marketplace' && <span className="text-amber-500">· 二手书</span>}
          </div>
        </div>
        <Link to={`/goods`} className="text-xs text-primary-600 flex items-center shrink-0">
          进店 <ChevronRight size={14} />
        </Link>
      </div>

      {/* 商品横滑预览（精华：小程序核心交互） */}
      <div className="flex gap-2.5 px-4 pb-3 overflow-x-auto no-scrollbar">
        {previewGoods.map(item => (
          <Link key={item.id} to={`/goods/${item.id}`}
            className="shrink-0 w-[90px] active:scale-95 transition-transform">
            <div className="w-[90px] h-[90px] rounded-xl bg-gray-100 flex items-center justify-center overflow-hidden">
              {item.image ? (
                <img src={item.image} alt="" className="w-full h-full object-cover" loading="lazy" />
              ) : (
                <BookOpen size={24} className="text-gray-300" />
              )}
            </div>
            <p className="text-[11px] text-gray-600 mt-1 line-clamp-1">{item.name}</p>
            <PriceTag price={item.price} />
          </Link>
        ))}
        {activeGoods.length > 6 && (
          <Link to="/goods" className="shrink-0 w-[90px] flex flex-col items-center justify-center text-gray-400">
            <ChevronRight size={20} />
            <span className="text-[10px] mt-1">更多{activeGoods.length - 6}件</span>
          </Link>
        )}
      </div>
    </div>
  )
}

/* ── 分类Tab（精华：推荐商家/二手书/教材） ── */
const TABS = [
  { key: 'recommend', label: '推荐', icon: Sparkles },
  { key: 'marketplace', label: '二手书市场', icon: ShoppingBag },
  { key: 'textbook', label: '教材预定', icon: BookOpen },
]

export default function Home() {
  const [allGoods, setAllGoods] = useState([])
  const [campuses, setCampuses] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('recommend')
  const navigate = useNavigate()
  const { campusId, campusName } = useCampusStore()

  useEffect(() => {
    Promise.all([fetchGoods(campusId), fetchCampuses()]).then(([g, c]) => {
      setAllGoods(g)
      setCampuses(c)
      setLoading(false)
    })
  }, [campusId])

  const handleSearch = (e) => {
    e.preventDefault()
    if (search.trim()) navigate(`/goods?q=${encodeURIComponent(search.trim())}`)
  }

  // Group goods by campus for shop cards
  const shopMap = {}
  allGoods.forEach(g => {
    const cid = g.campus_id
    if (!shopMap[cid]) shopMap[cid] = []
    shopMap[cid].push(g)
  })

  // Filter shops by tab
  const filteredCampuses = campuses.filter(c => {
    if (activeTab === 'recommend') return c.goods_count > 0
    if (activeTab === 'marketplace') return c.type === 'marketplace' && c.goods_count > 0
    if (activeTab === 'textbook') return c.type === 'textbook' && c.goods_count > 0
    return true
  })

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部（保留绿色主题） */}
      <div className="bg-gradient-to-br from-primary-600 to-primary-700 text-white px-4 pt-10 pb-5 rounded-b-3xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold">校园书市</h1>
            <Link to="/campus" className="text-primary-200 text-xs flex items-center gap-1 mt-0.5">
              <MapPin size={12} /> {campusName || '选择校区'} <ChevronDown size={12} />
            </Link>
          </div>
          <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
            <BookOpen size={20} />
          </div>
        </div>
        <form onSubmit={handleSearch} className="relative">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="搜索书名、教材..."
            className="w-full h-10 pl-10 pr-4 rounded-full bg-white text-gray-800 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-300" />
        </form>
      </div>

      {/* 分类Tab栏（精华：三鲜小程序顶级导航） */}
      <div className="sticky top-0 z-40 bg-white border-b border-gray-100 shadow-sm">
        <div className="flex justify-around">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setActiveTab(key)}
              className={`flex-1 py-2.5 text-center relative transition-colors ${
                activeTab === key ? 'text-primary-600' : 'text-gray-400'
              }`}>
              <div className="flex items-center justify-center gap-1">
                <Icon size={14} />
                <span className="text-xs font-medium">{label}</span>
              </div>
              {activeTab === key && (
                <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-primary-600 rounded-full" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* 店铺卡片列表（精华：三鲜小程序核心） */}
      <div className="px-4 py-3 space-y-3">
        {loading ? (
          [1, 2].map(i => (
            <div key={i} className="bg-white rounded-2xl p-4 animate-pulse">
              <div className="flex gap-3 mb-3">
                <div className="w-12 h-12 rounded-xl bg-gray-200" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-gray-200 rounded w-1/3" />
                  <div className="h-3 bg-gray-200 rounded w-1/4" />
                </div>
              </div>
              <div className="flex gap-2.5">
                {[1, 2, 3, 4].map(j => (
                  <div key={j} className="w-[90px] h-[90px] rounded-xl bg-gray-200 shrink-0" />
                ))}
              </div>
            </div>
          ))
        ) : filteredCampuses.length > 0 ? (
          filteredCampuses.map(campus => (
            <ShopCard key={campus.id} shop={campus} goods={shopMap[campus.id] || []} />
          ))
        ) : (
          <div className="text-center py-16 text-gray-400">
            <Store size={48} className="mx-auto mb-3 opacity-40" />
            <p>暂无{activeTab === 'textbook' ? '教材预定' : '二手书'}商家</p>
          </div>
        )}
      </div>

      <div className="h-4" />
    </div>
  )
}
""")

print("\\n✅ Home.jsx rewritten with sanxian mini-program UX patterns!")
print("Key changes:")
print("  1. Shop-card based browsing (vs flat grid)")
print("  2. Category tabs: 推荐/二手书市场/教材预定")
print("  3. Shop cards with 校内 badge + product horizontal scroll")
print("  4. Loading skeletons match shop card layout")
