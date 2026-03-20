import socket, threading, sys, time
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 443
TARGET_HOST = "192.168.31.179"
TARGET_PORT = 443

def relay(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data: break
            dst.sendall(data)
    except: pass
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
        t1 = threading.Thread(target=relay, args=(client, target), daemon=True)
        t2 = threading.Thread(target=relay, args=(target, client), daemon=True)
        t1.start(); t2.start(); t1.join(); t2.join()
    except Exception as e:
        print(f"Relay error: {e}")
        try: client.close()
        except: pass

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((LISTEN_HOST, LISTEN_PORT))
srv.listen(32)
print(f"CFW Relay: {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}")
while True:
    client, addr = srv.accept()
    print(f"Connection from {addr}")
    threading.Thread(target=handle, args=(client, addr), daemon=True).start()