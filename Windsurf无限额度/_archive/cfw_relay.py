"""CFW TCP Relay — 将LAN入站转发到本地CFW(127.0.0.1:443)
用法: python cfw_relay.py [--port 18443]
"""
import socket, threading, sys, time

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = int(sys.argv[sys.argv.index("--port")+1]) if "--port" in sys.argv else 18443
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 443

def relay(src, dst, label):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle(client, addr):
    try:
        target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target.settimeout(10)
        target.connect((TARGET_HOST, TARGET_PORT))
        t1 = threading.Thread(target=relay, args=(client, target, f"{addr}->CFW"), daemon=True)
        t2 = threading.Thread(target=relay, args=(target, client, f"CFW->{addr}"), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except Exception as e:
        try: client.close()
        except: pass

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, LISTEN_PORT))
    srv.listen(32)
    print(f"CFW Relay: {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}")
    print(f"Laptop should portproxy 127.0.0.1:443 -> 192.168.31.141:{LISTEN_PORT}")
    while True:
        client, addr = srv.accept()
        threading.Thread(target=handle, args=(client, addr), daemon=True).start()

if __name__ == "__main__":
    main()
