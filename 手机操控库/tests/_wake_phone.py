"""尝试唤醒Doze冻结的手机"""
import socket, time, sys
sys.path.insert(0, '..')
ip = "192.168.10.122"
ports = [8086, 8084, 8081]

print(f"尝试唤醒 {ip}...")
for attempt in range(10):
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((ip, port))
            s.send(b"GET /status HTTP/1.1\r\nHost: phone\r\nConnection: close\r\n\r\n")
            data = s.recv(4096)
            s.close()
            if data:
                text = data.decode(errors="replace")
                print(f"  Round {attempt+1}: {ip}:{port} -> {len(data)}b")
                if "connected" in text or "HTTP" in text:
                    print(f"  AWAKE! Response: {text[:200]}")
                    sys.exit(0)
        except socket.timeout:
            pass
        except Exception as e:
            print(f"  {ip}:{port}: {type(e).__name__}")
    print(f"  Round {attempt+1}: no HTTP response")
    time.sleep(2)

print("Phone in deep Doze - cannot wake via TCP alone")
