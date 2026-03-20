"""Tiny DNS proxy for CFW - returns 127.0.0.1 for windsurf/codeium domains.
Usage: python _dns_proxy.py [--bind 0.0.0.0] [--port 53] [--upstream 192.168.31.1]
"""
import socket, struct, sys, threading

BIND = "0.0.0.0"
PORT = 53
UPSTREAM = "192.168.31.1"
OVERRIDE_IP = "127.0.0.1"
INTERCEPT_DOMAINS = {
    b"server.self-serve.windsurf.com",
    b"server.codeium.com",
}

for i, a in enumerate(sys.argv):
    if a == "--bind" and i+1 < len(sys.argv): BIND = sys.argv[i+1]
    if a == "--port" and i+1 < len(sys.argv): PORT = int(sys.argv[i+1])
    if a == "--upstream" and i+1 < len(sys.argv): UPSTREAM = sys.argv[i+1]

def parse_qname(data, offset):
    labels = []
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:  # pointer
            offset += 2
            break
        offset += 1
        labels.append(data[offset:offset+length])
        offset += length
    return b".".join(labels), offset

def build_response(query, ip_str):
    # Copy header, set QR=1 (response), RA=1, ANCOUNT=1
    resp = bytearray(query[:12])
    resp[2] = 0x81  # QR=1, RD=1
    resp[3] = 0x80  # RA=1
    resp[6:8] = struct.pack("!H", 1)  # ANCOUNT=1
    # Copy question section
    resp += query[12:]
    # Add answer: pointer to qname + type A + class IN + TTL 60 + rdlength 4 + IP
    resp += b'\xc0\x0c'  # pointer to qname at offset 12
    resp += struct.pack("!HHI", 1, 1, 60)  # type=A, class=IN, TTL=60
    resp += struct.pack("!H", 4)  # rdlength
    resp += socket.inet_aton(ip_str)
    return bytes(resp)

def handle(sock, data, addr):
    try:
        qname, _ = parse_qname(data, 12)
        qname_lower = qname.lower()
        if qname_lower in INTERCEPT_DOMAINS:
            resp = build_response(data, OVERRIDE_IP)
            sock.sendto(resp, addr)
            print(f"[INTERCEPT] {qname.decode()} -> {OVERRIDE_IP}")
            return
        # Forward to upstream
        up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        up.settimeout(5)
        up.sendto(data, (UPSTREAM, 53))
        resp, _ = up.recvfrom(4096)
        up.close()
        sock.sendto(resp, addr)
    except Exception as e:
        print(f"[ERROR] {e}")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((BIND, PORT))
    print(f"DNS Proxy: {BIND}:{PORT} upstream={UPSTREAM}")
    print(f"Intercepting: {[d.decode() for d in INTERCEPT_DOMAINS]} -> {OVERRIDE_IP}")
    while True:
        data, addr = sock.recvfrom(4096)
        threading.Thread(target=handle, args=(sock, data, addr), daemon=True).start()

if __name__ == "__main__":
    main()
