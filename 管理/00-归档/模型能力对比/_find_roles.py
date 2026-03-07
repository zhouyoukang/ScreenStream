import re
with open(r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js","r",encoding="utf-8",errors="ignore") as f:
    c = f.read()

# Find chat role enum values
print("=== Chat Role Enums ===")
for pat in ["ROLE_USER", "ROLE_ASSISTANT", "ROLE_SYSTEM", "ROLE_BOT", 
            "CHAT_MESSAGE_ROLE", "ChatRole", "MessageRole"]:
    matches = re.findall(pat + r'\s*[=:]\s*(\d+)', c)
    if matches:
        print(f"  {pat} = {matches[:5]}")

# Broader search for role-related enums near chat context
print("\n=== Role enum definitions ===")
for m in re.finditer(r'(ROLE_[A-Z_]+)\s*=\s*(\d+)', c):
    name, val = m.group(1), m.group(2)
    if int(val) < 20:  # small enum values
        print(f"  {name} = {val}")

# Search for enum with user/assistant/system
print("\n=== User/System/Assistant enum values ===")
for m in re.finditer(r'([A-Z_]*(?:USER|SYSTEM|ASSISTANT|BOT)[A-Z_]*)\s*=\s*(\d+)', c):
    name, val = m.group(1), m.group(2)
    if int(val) < 20 and len(name) < 40:
        print(f"  {name} = {val}")

# Find the RawGetChatMessageRequest for comparison
print("\n=== RawGetChatMessageRequest Fields ===")
for m in re.finditer(r'RawGetChatMessageRequest"[^[]*newFieldList\(\(\)=>\[([^\]]{20,2000})\]', c):
    fields = re.findall(r'\{no:(\d+),name:"(\w+)",kind:"(\w+)"(?:,T:(\w+))?(?:,repeated:(\w+))?\}', m.group(1))
    if fields:
        print(f"  @{m.start()} ({len(fields)} fields):")
        for fno, fn, fk, ft, fr in fields:
            r = " (repeated)" if fr == "!0" else ""
            print(f"    field {fno}: {fn} ({fk}, T={ft}){r}")
        print()

# Find RawChatMessage
print("\n=== RawChatMessage Fields ===")
for m in re.finditer(r'RawChatMessage"[^[]*newFieldList\(\(\)=>\[([^\]]{20,2000})\]', c):
    fields = re.findall(r'\{no:(\d+),name:"(\w+)",kind:"(\w+)"(?:,T:(\w+))?(?:,repeated:(\w+))?\}', m.group(1))
    if fields:
        print(f"  @{m.start()} ({len(fields)} fields):")
        for fno, fn, fk, ft, fr in fields:
            r = " (repeated)" if fr == "!0" else ""
            print(f"    field {fno}: {fn} ({fk}, T={ft}){r}")
        print()
        break

# Search for how chatModel enum maps to display names
print("\n=== Model Display Mapping ===")
# Look for switch/case or map with model enum values
for m in re.finditer(r'case\s+(\d{3})\s*:', c):
    val = int(m.group(1))
    if 200 <= val <= 430:
        ctx = c[m.start():m.start()+200]
        name_match = re.search(r'["\']([^"\']{5,50})["\']', ctx)
        if name_match:
            print(f"  case {val}: {name_match.group(1)}")
