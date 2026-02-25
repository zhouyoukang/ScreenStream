#!/usr/bin/env python3
"""
校园书市v2.0 — 重写所有页面为独立版（无API依赖）
"""
import pathlib

BASE = pathlib.Path(r"E:\道\二手书\bookshop-pwa\src")

def write(rel_path, content):
    p = BASE / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"  Written: {rel_path}")

# ══════════════════════════════════════════════
# App.jsx — 路由（加校区选择页）
# ══════════════════════════════════════════════
write("App.jsx", """
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import GoodsList from './pages/GoodsList'
import GoodsDetail from './pages/GoodsDetail'
import Cart from './pages/Cart'
import Orders from './pages/Orders'
import Profile from './pages/Profile'
import CampusSelect from './pages/CampusSelect'

export default function App() {
  return (
    <Routes>
      <Route path="/campus" element={<CampusSelect />} />
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="/goods" element={<GoodsList />} />
        <Route path="/goods/:id" element={<GoodsDetail />} />
        <Route path="/cart" element={<Cart />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
    </Routes>
  )
}
""")

# ══════════════════════════════════════════════
# CampusSelect.jsx — 校区选择页（首次进入或切换）
# ══════════════════════════════════════════════
write("pages/CampusSelect.jsx", """
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapPin, ChevronRight, BookOpen } from 'lucide-react'
import { fetchCampuses } from '../data/provider'
import { useCampusStore } from '../store/campus'

export default function CampusSelect() {
  const [campuses, setCampuses] = useState([])
  const [loading, setLoading] = useState(true)
  const setCampus = useCampusStore(s => s.setCampus)
  const navigate = useNavigate()

  useEffect(() => {
    fetchCampuses().then(c => { setCampuses(c); setLoading(false) })
  }, [])

  const handleSelect = (campus) => {
    setCampus(campus.id, campus.name)
    navigate('/', { replace: true })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-600 to-primary-800 flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="w-20 h-20 rounded-3xl bg-white/20 flex items-center justify-center mb-6">
          <BookOpen size={40} className="text-white" />
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">校园书市</h1>
        <p className="text-primary-200 text-sm mb-10">选择你的校区，开始淘书</p>

        <div className="w-full max-w-sm space-y-3">
          {loading ? (
            [1,2,3].map(i => (
              <div key={i} className="bg-white/10 rounded-2xl h-16 animate-pulse" />
            ))
          ) : campuses.map(campus => (
            <button
              key={campus.id}
              onClick={() => handleSelect(campus)}
              className="w-full bg-white rounded-2xl px-4 py-3.5 flex items-center gap-3 active:scale-[0.98] transition-transform shadow-lg"
            >
              <div className="w-10 h-10 rounded-xl bg-primary-50 flex items-center justify-center shrink-0">
                <MapPin size={20} className="text-primary-600" />
              </div>
              <div className="flex-1 text-left">
                <div className="font-medium text-gray-800">{campus.name}</div>
                <div className="text-xs text-gray-400">{campus.goods_count} 件在售商品</div>
              </div>
              <ChevronRight size={18} className="text-gray-300" />
            </button>
          ))}
        </div>

        <button
          onClick={() => { setCampus(null, '全部校区'); navigate('/', { replace: true }) }}
          className="mt-6 text-white/60 text-sm underline underline-offset-4"
        >
          跳过，查看全部校区
        </button>
      </div>
    </div>
  )
}
""")

# ══════════════════════════════════════════════
# Home.jsx — 首页（多校区感知）
# ══════════════════════════════════════════════
write("pages/Home.jsx", """
import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Search, ChevronRight, BookOpen, Bike, Shirt, ShoppingBag, Cpu, FlaskConical, MapPin, ChevronDown } from 'lucide-react'
import { fetchGoods } from '../data/provider'
import { useCampusStore } from '../store/campus'

const QUICK_CATS = [
  { icon: BookOpen, label: '教材', color: 'bg-green-100 text-green-600' },
  { icon: Cpu, label: '考研', color: 'bg-blue-100 text-blue-600' },
  { icon: FlaskConical, label: '实验器材', color: 'bg-purple-100 text-purple-600' },
  { icon: Bike, label: '单车', color: 'bg-orange-100 text-orange-600' },
  { icon: Shirt, label: '干洗', color: 'bg-pink-100 text-pink-600' },
  { icon: ShoppingBag, label: '零食', color: 'bg-yellow-100 text-yellow-600' },
]

function PriceTag({ price }) {
  const p = parseFloat(price || 0)
  return (
    <span className="text-red-500 font-bold">
      <span className="text-xs">¥</span>{p.toFixed(p % 1 === 0 ? 0 : 2)}
    </span>
  )
}

function GoodsCard({ item }) {
  return (
    <Link to={`/goods/${item.id}`} className="bg-white rounded-xl overflow-hidden shadow-sm active:scale-[0.98] transition-transform">
      <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden">
        {item.image ? (
          <img src={item.image} alt={item.name} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <BookOpen size={40} className="text-gray-300" />
        )}
      </div>
      <div className="p-2.5">
        <h3 className="text-sm font-medium text-gray-800 line-clamp-2 leading-tight min-h-[2.5em]">
          {item.name}
        </h3>
        <div className="flex items-center justify-between mt-1.5">
          <PriceTag price={item.price} />
          <span className="text-[10px] text-gray-400">库存{item.stock}</span>
        </div>
      </div>
    </Link>
  )
}

export default function Home() {
  const [goods, setGoods] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const { campusId, campusName } = useCampusStore()

  useEffect(() => {
    fetchGoods(campusId).then(g => {
      setGoods(g.filter(i => i.status === 1 && i.stock > 0))
      setLoading(false)
    })
  }, [campusId])

  const handleSearch = (e) => {
    e.preventDefault()
    if (search.trim()) navigate(`/goods?q=${encodeURIComponent(search.trim())}`)
  }

  const recommended = goods.slice(0, 20)

  return (
    <div className="min-h-screen">
      <div className="bg-gradient-to-br from-primary-600 to-primary-700 text-white px-4 pt-10 pb-6 rounded-b-3xl">
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
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索教材、考研资料..."
            className="w-full h-10 pl-10 pr-4 rounded-full bg-white text-gray-800 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-300"
          />
        </form>
      </div>

      <div className="px-4 -mt-3">
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="grid grid-cols-6 gap-3">
            {QUICK_CATS.map(({ icon: Icon, label, color }) => (
              <Link key={label} to={`/goods?q=${encodeURIComponent(label)}`} className="flex flex-col items-center gap-1.5">
                <div className={`w-11 h-11 rounded-xl ${color} flex items-center justify-center`}>
                  <Icon size={20} />
                </div>
                <span className="text-[11px] text-gray-600">{label}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="px-4 mt-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-bold text-gray-800">为你推荐</h2>
          <Link to="/goods" className="text-xs text-primary-600 flex items-center">
            查看全部 <ChevronRight size={14} />
          </Link>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 gap-3">
            {[1,2,3,4].map(i => (
              <div key={i} className="bg-white rounded-xl overflow-hidden animate-pulse">
                <div className="aspect-square bg-gray-200" />
                <div className="p-2.5 space-y-2">
                  <div className="h-3 bg-gray-200 rounded w-3/4" />
                  <div className="h-3 bg-gray-200 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : recommended.length > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {recommended.map(item => <GoodsCard key={item.id} item={item} />)}
          </div>
        ) : (
          <div className="text-center py-12 text-gray-400">
            <BookOpen size={48} className="mx-auto mb-3 opacity-50" />
            <p>暂无商品</p>
          </div>
        )}
      </div>
      <div className="h-8" />
    </div>
  )
}
""")

# ══════════════════════════════════════════════
# GoodsList.jsx — 书市（多校区+本地数据）
# ══════════════════════════════════════════════
write("pages/GoodsList.jsx", """
import { useState, useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, X, SlidersHorizontal, BookOpen } from 'lucide-react'
import { fetchGoods, fetchCategories } from '../data/provider'
import { useCartStore } from '../store/cart'
import { useCampusStore } from '../store/campus'

function PriceTag({ price }) {
  const p = parseFloat(price || 0)
  return (
    <span className="text-red-500 font-bold">
      <span className="text-xs">¥</span>{p.toFixed(p % 1 === 0 ? 0 : 2)}
    </span>
  )
}

export default function GoodsList() {
  const [goods, setGoods] = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedCat, setSelectedCat] = useState(null)
  const [sortBy, setSortBy] = useState('default')
  const [showFilter, setShowFilter] = useState(false)
  const [searchParams] = useSearchParams()
  const addItem = useCartStore(s => s.addItem)
  const campusId = useCampusStore(s => s.campusId)

  useEffect(() => {
    Promise.all([fetchGoods(campusId), fetchCategories(campusId)]).then(([g, c]) => {
      setGoods(g.filter(i => i.status === 1))
      setCategories(c)
      setLoading(false)
    })
  }, [campusId])

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) setSearch(q)
  }, [searchParams])

  const filtered = useMemo(() => {
    let result = [...goods]
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter(g =>
        (g.name || '').toLowerCase().includes(q) ||
        (g.category || '').toLowerCase().includes(q)
      )
    }
    if (selectedCat) {
      result = result.filter(g => String(g.category_id) === String(selectedCat))
    }
    if (sortBy === 'price_asc') result.sort((a, b) => a.price - b.price)
    else if (sortBy === 'price_desc') result.sort((a, b) => b.price - a.price)
    else if (sortBy === 'stock') result.sort((a, b) => b.stock - a.stock)
    return result
  }, [goods, search, selectedCat, sortBy])

  const handleQuickAdd = (e, item) => {
    e.preventDefault()
    e.stopPropagation()
    addItem({ id: item.id, goods_name: item.name, price: item.price, goods_img: item.image, stock: item.stock })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="sticky top-0 z-40 bg-white shadow-sm">
        <div className="flex items-center gap-2 px-3 py-2.5">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="搜索书名、分类..."
              className="w-full h-9 pl-9 pr-8 rounded-full bg-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400" />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
                <X size={16} className="text-gray-400" />
              </button>
            )}
          </div>
          <button onClick={() => setShowFilter(!showFilter)}
            className={`p-2 rounded-lg ${showFilter ? 'bg-primary-100 text-primary-600' : 'text-gray-500'}`}>
            <SlidersHorizontal size={18} />
          </button>
        </div>

        <div className="flex items-center gap-2 px-3 pb-2 overflow-x-auto no-scrollbar">
          <button onClick={() => setSelectedCat(null)}
            className={`shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors ${!selectedCat ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
            全部
          </button>
          {categories.map(cat => (
            <button key={cat.id} onClick={() => setSelectedCat(String(cat.id))}
              className={`shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                selectedCat === String(cat.id) ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600'
              }`}>
              {cat.name}
            </button>
          ))}
        </div>

        {showFilter && (
          <div className="flex items-center gap-3 px-3 pb-2 border-t border-gray-100 pt-2">
            {[{ key: 'default', label: '默认' }, { key: 'price_asc', label: '价格↑' }, { key: 'price_desc', label: '价格↓' }, { key: 'stock', label: '库存多' }].map(s => (
              <button key={s.key} onClick={() => setSortBy(s.key)}
                className={`text-xs px-2.5 py-1 rounded ${sortBy === s.key ? 'bg-primary-50 text-primary-600 font-medium' : 'text-gray-500'}`}>
                {s.label}
              </button>
            ))}
            <span className="ml-auto text-xs text-gray-400">{filtered.length}件</span>
          </div>
        )}
      </div>

      <div className="p-3">
        {loading ? (
          <div className="grid grid-cols-2 gap-3">
            {[1,2,3,4,5,6].map(i => (
              <div key={i} className="bg-white rounded-xl overflow-hidden animate-pulse">
                <div className="aspect-square bg-gray-200" />
                <div className="p-2.5 space-y-2"><div className="h-3 bg-gray-200 rounded w-3/4" /><div className="h-3 bg-gray-200 rounded w-1/3" /></div>
              </div>
            ))}
          </div>
        ) : filtered.length > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {filtered.map(item => (
              <Link key={item.id} to={`/goods/${item.id}`}
                className="bg-white rounded-xl overflow-hidden shadow-sm active:scale-[0.98] transition-transform">
                <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden relative">
                  {item.image ? (
                    <img src={item.image} alt="" className="w-full h-full object-cover" loading="lazy" />
                  ) : (
                    <BookOpen size={40} className="text-gray-300" />
                  )}
                  {item.stock === 0 && (
                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                      <span className="text-white text-sm font-bold">已售罄</span>
                    </div>
                  )}
                </div>
                <div className="p-2.5">
                  <h3 className="text-sm text-gray-800 line-clamp-2 leading-tight min-h-[2.5em]">{item.name}</h3>
                  <div className="flex items-center justify-between mt-1.5">
                    <PriceTag price={item.price} />
                    <button onClick={(e) => handleQuickAdd(e, item)}
                      className="w-6 h-6 rounded-full bg-primary-600 text-white flex items-center justify-center text-lg leading-none active:bg-primary-700">
                      +
                    </button>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-center py-20 text-gray-400">
            <Search size={48} className="mx-auto mb-3 opacity-50" />
            <p>没有找到相关商品</p>
            {search && <button onClick={() => setSearch('')} className="mt-2 text-primary-600 text-sm">清除搜索</button>}
          </div>
        )}
      </div>
    </div>
  )
}
""")

# ══════════════════════════════════════════════
# GoodsDetail.jsx — 商品详情（本地数据）
# ══════════════════════════════════════════════
write("pages/GoodsDetail.jsx", """
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ShoppingCart, Minus, Plus, BookOpen, Package, Check } from 'lucide-react'
import { fetchGoodsById } from '../data/provider'
import { useCartStore } from '../store/cart'

export default function GoodsDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [item, setItem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [qty, setQty] = useState(1)
  const [added, setAdded] = useState(false)
  const addItem = useCartStore(s => s.addItem)
  const cartCount = useCartStore(s => s.items.reduce((n, i) => n + i.qty, 0))

  useEffect(() => {
    fetchGoodsById(id).then(g => { setItem(g); setLoading(false) })
  }, [id])

  const handleAdd = () => {
    if (!item) return
    const cartItem = { id: item.id, goods_name: item.name, price: item.price, goods_img: item.image, stock: item.stock }
    for (let i = 0; i < qty; i++) addItem(cartItem)
    setAdded(true)
    setTimeout(() => setAdded(false), 1500)
  }

  const handleBuy = () => { handleAdd(); setTimeout(() => navigate('/cart'), 200) }

  if (loading) {
    return (
      <div className="min-h-screen bg-white animate-pulse">
        <div className="aspect-square bg-gray-200" />
        <div className="p-4 space-y-3"><div className="h-5 bg-gray-200 rounded w-3/4" /><div className="h-4 bg-gray-200 rounded w-1/3" /></div>
      </div>
    )
  }

  if (!item) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center text-gray-400">
        <BookOpen size={64} className="mb-4 opacity-50" />
        <p className="text-lg">商品不存在</p>
        <button onClick={() => navigate(-1)} className="mt-4 text-primary-600">返回</button>
      </div>
    )
  }

  const price = parseFloat(item.price || 0)
  const stock = item.stock || 0

  return (
    <div className="min-h-screen bg-white pb-20">
      <div className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-3 pt-8 pb-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 rounded-full bg-black/30 backdrop-blur-sm text-white flex items-center justify-center">
          <ArrowLeft size={20} />
        </button>
        <button onClick={() => navigate('/cart')} className="w-9 h-9 rounded-full bg-black/30 backdrop-blur-sm text-white flex items-center justify-center relative">
          <ShoppingCart size={18} />
          {cartCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">{cartCount}</span>
          )}
        </button>
      </div>

      <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden">
        {item.image ? (
          <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
        ) : (
          <div className="flex flex-col items-center text-gray-300"><BookOpen size={80} /><span className="text-sm mt-2">暂无图片</span></div>
        )}
      </div>

      <div className="bg-gradient-to-r from-red-500 to-red-400 text-white px-4 py-3">
        <div className="flex items-baseline gap-1">
          <span className="text-sm">¥</span>
          <span className="text-3xl font-bold">{price.toFixed(price % 1 === 0 ? 0 : 2)}</span>
        </div>
      </div>

      <div className="px-4 py-3">
        <h1 className="text-lg font-bold text-gray-800 leading-snug">{item.name}</h1>
        <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
          <span className="flex items-center gap-1"><Package size={14} /> 库存 {stock}</span>
          {item.category && <span className="flex items-center gap-1"><BookOpen size={14} /> {item.category}</span>}
        </div>
      </div>

      <div className="h-2 bg-gray-50" />

      <div className="px-4 py-3">
        <h3 className="text-sm font-medium text-gray-700 mb-2">商品详情</h3>
        <div className="text-sm text-gray-500 leading-relaxed">
          {item.description || (
            <div className="text-center py-4 text-gray-300">
              <BookOpen size={32} className="mx-auto mb-2 opacity-40" />
              <span className="text-sm">暂无详细描述</span>
            </div>
          )}
        </div>
      </div>

      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-2.5 safe-bottom z-50">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-gray-100 rounded-full px-1">
            <button onClick={() => setQty(Math.max(1, qty - 1))} className="w-7 h-7 rounded-full flex items-center justify-center text-gray-500 active:bg-gray-200"><Minus size={14} /></button>
            <span className="w-6 text-center text-sm font-medium">{qty}</span>
            <button onClick={() => setQty(Math.min(stock, qty + 1))} className="w-7 h-7 rounded-full flex items-center justify-center text-gray-500 active:bg-gray-200"><Plus size={14} /></button>
          </div>
          <button onClick={handleAdd} disabled={stock === 0}
            className={`flex-1 h-10 rounded-full font-medium text-sm flex items-center justify-center gap-1.5 transition-all ${
              added ? 'bg-green-500 text-white' : stock === 0 ? 'bg-gray-200 text-gray-400' : 'bg-primary-50 text-primary-600 border border-primary-200 active:bg-primary-100'
            }`}>
            {added ? <><Check size={16} /> 已加入</> : <><ShoppingCart size={16} /> 加入购物车</>}
          </button>
          <button onClick={handleBuy} disabled={stock === 0}
            className={`flex-1 h-10 rounded-full font-medium text-sm ${stock === 0 ? 'bg-gray-300 text-gray-500' : 'bg-primary-600 text-white active:bg-primary-700'}`}>
            {stock === 0 ? '已售罄' : '立即购买'}
          </button>
        </div>
      </div>
    </div>
  )
}
""")

# ══════════════════════════════════════════════
# Orders.jsx — 订单（本地订单，无API）
# ══════════════════════════════════════════════
write("pages/Orders.jsx", """
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ClipboardList, ShoppingBag, BookOpen } from 'lucide-react'
import { useCartStore } from '../store/cart'

export default function Orders() {
  // 本地订单（从localStorage读取历史购物记录）
  const cartItems = useCartStore(s => s.items)
  const [tab, setTab] = useState('pending')

  // 独立版：暂无真实订单系统，引导用户使用购物车
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white px-4 pt-10 pb-4">
        <h1 className="text-xl font-bold text-gray-800">订单</h1>
        <div className="flex gap-4 mt-4">
          {['pending', 'done'].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-400'
              }`}>
              {t === 'pending' ? '待处理' : '已完成'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <ClipboardList size={64} className="mb-4 opacity-30" />
        <p className="text-base font-medium text-gray-500">暂无订单</p>
        <p className="text-xs text-gray-400 mt-1">在购物车中确认商品后联系卖家下单</p>
        {cartItems.length > 0 ? (
          <Link to="/cart" className="mt-4 px-6 py-2 bg-primary-600 text-white rounded-full text-sm active:bg-primary-700">
            去购物车结算 ({cartItems.length}件)
          </Link>
        ) : (
          <Link to="/goods" className="mt-4 px-6 py-2 bg-primary-600 text-white rounded-full text-sm active:bg-primary-700">
            去逛逛书市
          </Link>
        )}
      </div>
    </div>
  )
}
""")

# ══════════════════════════════════════════════
# Profile.jsx — 我的（无后端依赖）
# ══════════════════════════════════════════════
write("pages/Profile.jsx", """
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, ShoppingBag, MapPin, RefreshCw, Database, Globe } from 'lucide-react'
import { fetchStatus, fetchCampuses } from '../data/provider'
import { useCampusStore } from '../store/campus'

export default function Profile() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const { campusName } = useCampusStore()

  const load = () => {
    setLoading(true)
    fetchStatus().then(s => { setStatus(s); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  return (
    <div className="min-h-screen bg-gray-50 pb-4">
      <div className="bg-gradient-to-br from-primary-600 to-primary-700 text-white px-4 pt-10 pb-6 rounded-b-3xl">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-white/20 flex items-center justify-center">
            <BookOpen size={32} />
          </div>
          <div>
            <h2 className="text-xl font-bold">校园书市</h2>
            <p className="text-primary-200 text-sm mt-0.5">{campusName || '多校区二手书平台'}</p>
          </div>
        </div>
      </div>

      <div className="px-4 -mt-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: ShoppingBag, label: '在售', value: status?.goods_count || '-', color: 'text-blue-500' },
              { icon: MapPin, label: '校区', value: status?.campuses_count || '-', color: 'text-green-500' },
              { icon: Database, label: '分类', value: status?.categories_count || '-', color: 'text-purple-500' },
            ].map(({ icon: Icon, label, value, color }) => (
              <div key={label} className="text-center">
                <Icon size={20} className={`mx-auto ${color}`} />
                <div className="text-lg font-bold text-gray-800 mt-1">{value}</div>
                <div className="text-[10px] text-gray-400">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="px-4 mt-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-gray-700">设置</h3>
        </div>
        <div className="bg-white rounded-2xl overflow-hidden shadow-sm">
          <Link to="/campus" className="flex items-center gap-3 px-4 py-3 border-b border-gray-50 active:bg-gray-50">
            <MapPin size={18} className="text-green-500" />
            <div className="flex-1">
              <div className="text-sm text-gray-700">切换校区</div>
              <div className="text-xs text-gray-400">{campusName || '未选择'}</div>
            </div>
          </Link>
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-50">
            <Globe size={18} className="text-blue-500" />
            <div className="flex-1">
              <div className="text-sm text-gray-700">数据来源</div>
              <div className="text-xs text-gray-400">本地静态数据（离线可用）</div>
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-green-50 text-green-600">独立</span>
          </div>
          <div className="flex items-center gap-3 px-4 py-3">
            <Database size={18} className="text-purple-500" />
            <div className="flex-1">
              <div className="text-sm text-gray-700">购物车数据</div>
              <div className="text-xs text-gray-400">存储在本地浏览器中</div>
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 mt-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <h3 className="text-sm font-bold text-gray-700 mb-2">关于</h3>
          <div className="text-xs text-gray-400 space-y-1">
            <p>校园书市 v2.0 — 独立多校区版</p>
            <p>无需网络即可浏览商品信息</p>
            <p>教材·考研资料·学习用品，校园低价互助</p>
          </div>
        </div>
      </div>
    </div>
  )
}
""")

# ══════════════════════════════════════════════
# Layout.jsx — 底部导航（保持不变，已经很好）
# ══════════════════════════════════════════════
# Layout doesn't need changes - it already uses cart store properly

print("\n✅ All 7 pages rewritten for independent multi-campus mode!")
print("Files changed: App.jsx, CampusSelect.jsx, Home.jsx, GoodsList.jsx, GoodsDetail.jsx, Orders.jsx, Profile.jsx")
