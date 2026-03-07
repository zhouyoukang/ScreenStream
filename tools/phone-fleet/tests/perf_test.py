"""
性能基准测试 — 测量优化效果
================================
测试连接池keep-alive、并行senses、自适应等待、熔断器、长链稳定性。

使用: python tests/perf_test.py [--host 192.168.31.32] [--port 8084]

需要手机运行ScreenStream并可达。
"""

import sys, os, time, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phone_lib import Phone, _HttpPool, _CircuitBreaker
from urllib.request import Request, urlopen

# ============================================================
# 测试框架
# ============================================================

passed = 0
failed = 0
results = []

def test(name, fn, expect_pass=True):
    global passed, failed
    try:
        r = fn()
        if expect_pass:
            passed += 1
            results.append(("✅", name, r))
            print(f"  ✅ {name}: {r}")
        else:
            failed += 1
            results.append(("❌", name, f"Expected fail but got: {r}"))
            print(f"  ❌ {name}: Expected fail but got: {r}")
    except Exception as e:
        if not expect_pass:
            passed += 1
            results.append(("✅", name, f"Expected fail: {e}"))
            print(f"  ✅ {name}: Expected fail: {e}")
        else:
            failed += 1
            results.append(("❌", name, str(e)))
            print(f"  ❌ {name}: {e}")

def benchmark(name, fn, rounds=10):
    """测量函数执行时间，返回(avg_ms, min_ms, max_ms)"""
    times = []
    for _ in range(rounds):
        t0 = time.time()
        fn()
        times.append((time.time() - t0) * 1000)
    avg = sum(times) / len(times)
    mn, mx = min(times), max(times)
    print(f"  📊 {name}: avg={avg:.1f}ms min={mn:.1f}ms max={mx:.1f}ms ({rounds}轮)")
    return avg, mn, mx


# ============================================================
# 测试用例
# ============================================================

def test_connection_pool_vs_urllib(base_url):
    """对比: 连接池keep-alive vs urllib(每次新建连接)"""
    print("\n" + "=" * 60)
    print("  § 1. 连接池 keep-alive vs urllib 新建连接")
    print("=" * 60)

    path = "/status"
    rounds = 20

    # urllib (每次新连接)
    def urllib_get():
        req = Request(base_url + path, method="GET")
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    avg_urllib, _, _ = benchmark("urllib(新建连接)", urllib_get, rounds)

    # 连接池 (keep-alive)
    pool = _HttpPool()
    def pool_get():
        _, raw = pool.request("GET", base_url + path, timeout=5)
        return json.loads(raw.decode())

    avg_pool, _, _ = benchmark("连接池(keep-alive)", pool_get, rounds)
    pool.close()

    speedup = avg_urllib / avg_pool if avg_pool > 0 else float('inf')
    saved_ms = avg_urllib - avg_pool
    print(f"\n  🚀 keep-alive加速: {speedup:.1f}x (每次省{saved_ms:.1f}ms)")
    print(f"     连接池统计: {pool.stats}")
    return {"urllib_avg_ms": round(avg_urllib, 1), "pool_avg_ms": round(avg_pool, 1),
            "speedup": round(speedup, 1), "saved_per_call_ms": round(saved_ms, 1)}


def test_parallel_senses(p):
    """对比: 并行senses vs 串行senses"""
    print("\n" + "=" * 60)
    print("  § 2. 并行 senses() vs 串行 senses()")
    print("=" * 60)

    rounds = 5

    # 串行
    def serial(): return p.senses(parallel=False)
    avg_serial, _, _ = benchmark("串行senses", serial, rounds)

    # 并行
    def parallel(): return p.senses(parallel=True)
    avg_parallel, _, _ = benchmark("并行senses", parallel, rounds)

    speedup = avg_serial / avg_parallel if avg_parallel > 0 else float('inf')
    print(f"\n  🚀 并行加速: {speedup:.1f}x ({avg_serial:.0f}ms → {avg_parallel:.0f}ms)")

    # 验证数据完整性
    s = p.senses(parallel=True)
    test("并行senses数据完整", lambda: (
        s.get("_ok") and "vision" in s and "hearing" in s
        and "touch" in s and "smell" in s and "taste" in s
    ))

    return {"serial_avg_ms": round(avg_serial, 1), "parallel_avg_ms": round(avg_parallel, 1),
            "speedup": round(speedup, 1)}


def test_phone_http_perf(p):
    """测试Phone._http连接池效果"""
    print("\n" + "=" * 60)
    print("  § 3. Phone._http 连接池效果")
    print("=" * 60)

    rounds = 20

    def get_status(): return p.status()
    avg, mn, mx = benchmark("GET /status (连接池)", get_status, rounds)

    stats = p.perf_stats()
    pool = stats["pool"]
    reuse_rate = pool["reused"] / max(pool["reused"] + pool["created"], 1) * 100
    print(f"\n  📊 连接复用率: {reuse_rate:.0f}% (reused={pool['reused']}, created={pool['created']})")
    print(f"     熔断器状态: {stats['breaker']}")
    print(f"     平均延迟(最近20): {stats['avg_ms_recent20']}ms")

    return {"avg_ms": round(avg, 1), "min_ms": round(mn, 1), "max_ms": round(mx, 1),
            "reuse_rate_pct": round(reuse_rate, 0), "pool_stats": pool}


def test_circuit_breaker():
    """测试熔断器行为"""
    print("\n" + "=" * 60)
    print("  § 4. 熔断器 (Circuit Breaker)")
    print("=" * 60)

    cb = _CircuitBreaker(threshold=3, cooldown=2)

    test("初始状态=closed", lambda: cb.state == "closed")
    test("允许请求", lambda: cb.allow() == True)

    cb.record_failure()
    cb.record_failure()
    test("2次失败仍closed", lambda: cb.state == "closed")

    cb.record_failure()
    test("3次失败→open", lambda: cb.state == "open")
    test("open时拒绝请求", lambda: cb.allow() == False)

    # 等待cooldown
    time.sleep(2.1)
    test("cooldown后→half_open", lambda: cb.allow() == True)
    test("状态=half_open", lambda: cb.state == "half_open")

    cb.record_success()
    test("成功后→closed", lambda: cb.state == "closed")

    return "6/6"


def test_chain_execution(p):
    """测试长链稳定执行"""
    print("\n" + "=" * 60)
    print("  § 5. 长链稳定执行 (chain)")
    print("=" * 60)

    steps = [
        ("status", lambda: p.status()),
        ("device", lambda: p.device()),
        ("foreground", lambda: p.foreground()),
        ("read", lambda: p.read()),
        ("notifications", lambda: p.notifications(5)),
    ]

    results = p.chain(steps)
    ok_count = sum(1 for _, ok, _, _ in results if ok)
    total_time = sum(t for _, _, _, t in results)

    print(f"\n  📊 链路结果: {ok_count}/{len(results)} 成功")
    for name, ok, _, elapsed in results:
        print(f"     {'✅' if ok else '❌'} {name}: {elapsed:.3f}s")
    print(f"     总耗时: {total_time:.3f}s")

    test("链路全部成功", lambda: ok_count == len(results))

    # 测试失败策略
    bad_steps = [
        ("status", lambda: p.status()),
        ("bad_api", lambda: p.get("/nonexistent_endpoint_xxx")),
        ("device", lambda: p.device()),
    ]

    results_stop = p.chain(bad_steps, on_fail='stop')
    results_skip = p.chain(bad_steps, on_fail='skip')

    test("on_fail=stop在失败处停止", lambda: len(results_stop) == 2)
    test("on_fail=skip跳过失败继续", lambda: len(results_skip) == 3)

    return {"chain_ok": ok_count, "chain_total": len(results),
            "chain_time_s": round(total_time, 3)}


def test_wait_for(p):
    """测试自适应等待"""
    print("\n" + "=" * 60)
    print("  § 6. 自适应等待 (wait_for)")
    print("=" * 60)

    # 立即满足的条件
    t0 = time.time()
    ok = p.wait_for(lambda: True, timeout=5)
    elapsed = (time.time() - t0) * 1000
    test(f"立即满足: {elapsed:.0f}ms", lambda: ok and elapsed < 200)

    # 超时的条件
    t0 = time.time()
    ok = p.wait_for(lambda: False, timeout=0.5)
    elapsed = (time.time() - t0) * 1000
    test(f"超时退出: {elapsed:.0f}ms", lambda: not ok and 400 < elapsed < 700)

    # 实际条件：等前台APP有内容
    t0 = time.time()
    ok = p.wait_for(lambda: bool(p.foreground()), timeout=3)
    elapsed = (time.time() - t0) * 1000
    test(f"等待前台APP: {elapsed:.0f}ms", lambda: ok)


def test_operation_log(p):
    """测试操作日志"""
    print("\n" + "=" * 60)
    print("  § 7. 操作日志 (op_log)")
    print("=" * 60)

    # 执行几个操作
    p.status()
    p.device()
    p.foreground()

    stats = p.perf_stats()
    test("日志有记录", lambda: stats["op_total"] > 0)
    test("有成功记录", lambda: stats["op_ok"] > 0)
    test("recent有数据", lambda: len(stats["recent"]) > 0)
    print(f"  📊 日志统计: total={stats['op_total']} ok={stats['op_ok']} fail={stats['op_fail']}")
    print(f"     最近操作: {stats['recent']}")


def test_rapid_fire(p, count=50):
    """高速连续请求压测"""
    print("\n" + "=" * 60)
    print(f"  § 8. 高速连续请求 ({count}次)")
    print("=" * 60)

    t0 = time.time()
    ok_count = 0
    for i in range(count):
        r = p.status()
        if r and not r.get("_error"):
            ok_count += 1
    elapsed = time.time() - t0
    rps = count / elapsed if elapsed > 0 else 0

    print(f"  📊 {count}次请求: {ok_count}/{count}成功 耗时{elapsed:.2f}s ({rps:.0f} req/s)")
    test(f"成功率>{95}%", lambda: ok_count / count > 0.95)

    stats = p.perf_stats()
    print(f"     连接池: {stats['pool']}")
    print(f"     平均延迟: {stats['avg_ms_recent20']}ms")

    return {"count": count, "ok": ok_count, "elapsed_s": round(elapsed, 2),
            "rps": round(rps, 0), "avg_ms": stats["avg_ms_recent20"]}


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="phone_lib性能基准测试")
    parser.add_argument("--host", help="手机IP")
    parser.add_argument("--port", type=int, default=8084, help="端口")
    parser.add_argument("--url", help="完整URL")
    args = parser.parse_args()

    print("=" * 60)
    print("  phone_lib 性能基准测试")
    print("=" * 60)

    # 连接
    kwargs = {"auto_discover": False, "retry": 1}
    if args.url:
        kwargs["url"] = args.url
    elif args.host:
        kwargs["host"] = args.host
        kwargs["port"] = args.port
    else:
        kwargs["port"] = args.port

    p = Phone(**kwargs)
    print(f"\n  连接: {p}")

    # 预热
    r = p.status()
    if r.get("_error"):
        print(f"\n  ❌ 无法连接到手机: {r}")
        print("  请确保ScreenStream正在运行且可达")
        sys.exit(1)
    print(f"  预热成功: {r.get('connected', '?')}")

    # 运行所有测试
    all_results = {}

    all_results["§1_pool_vs_urllib"] = test_connection_pool_vs_urllib(p.base)
    all_results["§2_parallel_senses"] = test_parallel_senses(p)
    all_results["§3_http_perf"] = test_phone_http_perf(p)
    all_results["§4_circuit_breaker"] = test_circuit_breaker()
    all_results["§5_chain"] = test_chain_execution(p)
    test_wait_for(p)
    test_operation_log(p)
    all_results["§8_rapid_fire"] = test_rapid_fire(p)

    # 汇总
    print("\n" + "=" * 60)
    print(f"  汇总: {passed}通过 / {failed}失败 / {passed+failed}总计")
    print("=" * 60)

    if all_results.get("§1_pool_vs_urllib"):
        r1 = all_results["§1_pool_vs_urllib"]
        print(f"\n  🔑 关键发现:")
        print(f"     连接池加速: {r1['speedup']}x (每次省{r1['saved_per_call_ms']}ms)")
    if all_results.get("§2_parallel_senses"):
        r2 = all_results["§2_parallel_senses"]
        print(f"     并行senses: {r2['speedup']}x ({r2['serial_avg_ms']}ms→{r2['parallel_avg_ms']}ms)")
    if all_results.get("§8_rapid_fire"):
        r8 = all_results["§8_rapid_fire"]
        print(f"     吞吐量: {r8['rps']} req/s, 平均{r8['avg_ms']}ms")

    # 保存结果
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "connection": str(p),
        "passed": passed, "failed": failed,
        "results": all_results,
    }
    report_path = os.path.join(os.path.dirname(__file__), "..", "perf_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  📄 报告已保存: {report_path}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
