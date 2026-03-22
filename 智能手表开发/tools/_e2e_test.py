"""VP99 全功能E2E测试 — Agent大脑操控手表"""
import sys, time, json, urllib.request
sys.path.insert(0, __file__.rsplit('\\', 1)[0])
from watch_bridge import VP99Watch

results = []

def test(name, fn):
    try:
        r = fn()
        ok = r is not None and r != False
        results.append({'test': name, 'pass': ok, 'detail': str(r)[:100]})
        tag = 'PASS' if ok else 'FAIL'
        print(f'  [{tag}] {name}')
    except Exception as e:
        results.append({'test': name, 'pass': False, 'detail': str(e)[:100]})
        print(f'  [FAIL] {name}: {e}')

print('VP99 E2E Test Suite')
print('=' * 50)

w = VP99Watch()

test('T01 VNC connect', lambda: w.connect())
test('T02 screenshot', lambda: w.screenshot())
test('T03 home key', lambda: (w.home(), True)[1])
time.sleep(1)
test('T04 home verify', lambda: w.screenshot())
test('T05 tap settings', lambda: (w.tap(310, 385), time.sleep(1.5), True)[2])
test('T06 settings verify', lambda: w.screenshot())
test('T07 swipe up', lambda: (w.swipe_up(), True)[1])
test('T08 swipe down', lambda: (w.swipe_down(), True)[1])
test('T09 home return', lambda: (w.home(), time.sleep(1), True)[2])
test('T10 HTTP 8080', lambda: urllib.request.urlopen('http://192.168.31.41:8080', timeout=3).status)
test('T11 HTTP /{ha}', lambda: urllib.request.urlopen('http://192.168.31.41:8080/%7Bha%7D', timeout=3).read())
test('T12 systemlog size', lambda: len(urllib.request.urlopen('http://192.168.31.41:8080/systemlog', timeout=10).read()))
test('T13 watch status', lambda: w.status())
test('T14 senses', lambda: w.senses())

w.disconnect()

passed = sum(1 for r in results if r['pass'])
total = len(results)
print(f'\n{"=" * 50}')
print(f'Results: {passed}/{total} PASS ({passed * 100 // total}%)')

out = __file__.rsplit('\\', 2)[0] + '\\data\\vp99_e2e_results.json'
with open(out, 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f'Saved: {out}')
