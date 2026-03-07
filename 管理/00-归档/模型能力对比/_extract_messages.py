"""Extract Metadata and ChatMessage protobuf field definitions"""
import re

JS = r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js"
print("Reading...")
with open(JS, "r", encoding="utf-8", errors="ignore") as f:
    c = f.read()

# Find metadata message type used in GetChatMessageRequest
# From previous: field 1 metadata uses type Ws or Ec.OS9 or $fC
# Search for Metadata protobuf definitions
print("=== Metadata / RequestMetadata ===")
for pat in ['Metadata"', 'RequestMetadata"', 'ApiRequestMetadata"']:
    for m in re.finditer(pat + r'[^[]*newFieldList\(\(\)=>\[([^\]]{20,2000})\]', c):
        fields_str = m.group(1)
        fields = re.findall(r'\{no:(\d+),name:"(\w+)",kind:"(\w+)"(?:,T:(\w+))?(?:,repeated:(\w+))?\}', fields_str)
        if fields and len(fields) >= 2:
            print(f"\n  {pat} @{m.start()} ({len(fields)} fields):")
            for fno, fname, fkind, ftype, frep in fields:
                r = " (repeated)" if frep == "!0" else ""
                print(f"    field {fno}: {fname} ({fkind}, T={ftype}){r}")
            break

# Find ChatMessage type
print("\n=== ChatMessage ===")
for pat in ['"ChatMessage"', '"FormattedChatMessage"', '"RawChatMessage"']:
    count = 0
    for m in re.finditer(pat + r'[^[]*newFieldList\(\(\)=>\[([^\]]{20,2000})\]', c):
        fields_str = m.group(1)
        fields = re.findall(r'\{no:(\d+),name:"(\w+)",kind:"(\w+)"(?:,T:(\w+))?(?:,repeated:(\w+))?\}', fields_str)
        if fields and len(fields) >= 2:
            print(f"\n  {pat} @{m.start()} ({len(fields)} fields):")
            for fno, fname, fkind, ftype, frep in fields:
                r = " (repeated)" if frep == "!0" else ""
                print(f"    field {fno}: {fname} ({fkind}, T={ftype}){r}")
            count += 1
            if count >= 2:
                break

# Find ChatMessageRole enum
print("\n=== ChatMessageRole / Role enums ===")
for m in re.finditer(r'(ROLE_[A-Z_]+)\s*[=:]\s*(\d+)', c):
    print(f"  {m.group(1)} = {m.group(2)}")

# Find message_source or source enum
print("\n=== MessageSource enums ===")  
for m in re.finditer(r'(SOURCE_[A-Z_]+|MESSAGE_SOURCE_[A-Z_]+)\s*[=:]\s*(\d+)', c):
    print(f"  {m.group(1)} = {m.group(2)}")

# Find the exact gRPC service definition with method paths
print("\n=== ChatService Method Registry ===")
for m in re.finditer(r'ChatService["\'][^{]*\{[^}]*GetChatMessage[^}]{0,500}\}', c):
    txt = m.group()[:500]
    print(f"  @{m.start()}: {txt}")

# Find how the request is actually sent (grpc-web transport)
print("\n=== gRPC-web Transport ===")
for m in re.finditer(r'grpc-web[^;]{0,200}', c, re.IGNORECASE):
    txt = m.group()[:200]
    if 'content' in txt.lower() or 'header' in txt.lower():
        print(f"  @{m.start()}: {txt}")
