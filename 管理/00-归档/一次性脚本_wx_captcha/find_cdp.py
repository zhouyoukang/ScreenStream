"""Find all Chrome CDP ports and their pages"""
import subprocess, re, requests

result = subprocess.run(
    ['powershell', '-c', 'Get-Process chrome -EA 0 | Select-Object Id,CommandLine | Format-List'],
    capture_output=True, text=True
)
ports = set()
for line in result.stdout.split('\n'):
    m = re.search(r'remote-debugging-port=(\d+)', line)
    if m:
        ports.add(m.group(1))

print(f"Ports found: {ports}")

for port in sorted(ports):
    try:
        targets = requests.get(f"http://localhost:{port}/json", timeout=2).json()
        print(f"\nPort {port}: {len(targets)} targets")
        for t in targets:
            title = t.get("title", "")[:40]
            url = t.get("url", "")[:80]
            print(f"  {title} | {url}")
    except Exception as e:
        print(f"Port {port}: error - {e}")
