"""Extract model enum numeric values from Windsurf JS"""
import re, json

JS = r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js"
print("Reading...")
with open(JS, "r", encoding="utf-8", errors="ignore") as f:
    c = f.read()

# Find the Model enum definition block
# Pattern: MODEL_XXX=N (protobuf enum values)
# They appear as: L[L.MODEL_XXX=N]="MODEL_XXX" or MODEL_XXX:N
results = {}

# Pattern 1: L[L.MODEL_XXX=123]="MODEL_XXX"
p1 = re.findall(r'\[[\w.]+\.(MODEL_[A-Z0-9_]+)\s*=\s*(\d+)\]\s*=\s*"MODEL_', c)
print(f"Pattern1 (L[L.X=N]): {len(p1)} matches")
for name, val in p1:
    results[name] = int(val)

# Pattern 2: MODEL_XXX:123 in enum object
p2 = re.findall(r'"?(MODEL_[A-Z0-9_]+)"?\s*:\s*(\d+)\s*[,}]', c)
print(f"Pattern2 (X:N): {len(p2)} matches")
for name, val in p2:
    if name not in results:
        results[name] = int(val)

# Pattern 3: {MODEL_XXX:N,MODEL_YYY:M,...}
p3 = re.findall(r'(MODEL_[A-Z0-9_]+)\s*=\s*(\d+)', c)
print(f"Pattern3 (X=N): {len(p3)} matches")
for name, val in p3:
    if name not in results:
        results[name] = int(val)

# Filter to chat models only
chat_keywords = ['CLAUDE', 'GPT', 'CHAT_GPT', 'GEMINI', 'GROK', 'DEEPSEEK', 'QWEN', 
                 'KIMI', 'GLM', 'LLAMA', 'MINIMAX', 'SWE', 'CODEX', 'O3_', 'O4_',
                 'CASCADE', 'UNSPECIFIED']
chat_enums = {k: v for k, v in sorted(results.items(), key=lambda x: x[1]) 
              if any(kw in k for kw in chat_keywords)}

print(f"\nChat model enums ({len(chat_enums)}):")
for name, val in sorted(chat_enums.items(), key=lambda x: x[1]):
    print(f"  {val:6d} = {name}")

# Also find the GetChatMessageRequest full field list
print("\n=== GetChatMessageRequest Fields ===")
for m in re.finditer(r'GetChatMessageRequest"[^[]*\[([^\]]{50,2000})\]', c):
    fields_str = m.group(1)
    # Parse field definitions
    fields = re.findall(r'\{no:(\d+),name:"(\w+)",kind:"(\w+)"(?:,T:(\w+))?(?:,repeated:(\w+))?\}', fields_str)
    if fields:
        print(f"  @{m.start()}:")
        for fno, fname, fkind, ftype, frepeated in fields:
            rep = " (repeated)" if frepeated == "!0" else ""
            print(f"    field {fno}: {fname} ({fkind}, T={ftype}){rep}")
        print()

# Find ChatMessage fields (the message type in chat_messages)
print("\n=== ChatMessage Fields ===")
for m in re.finditer(r'(?:class \w+ extends|")(ChatMessage|RawChatMessage)"[^[]*newFieldList\(\(\)=>\[([^\]]{50,2000})\]', c):
    name = m.group(1)
    fields_str = m.group(2)
    fields = re.findall(r'\{no:(\d+),name:"(\w+)",kind:"(\w+)"(?:,T:(\w+))?', fields_str)
    if fields:
        print(f"  {name} @{m.start()}:")
        for fno, fname, fkind, ftype in fields:
            print(f"    field {fno}: {fname} ({fkind}, T={ftype})")
        print()
        break  # just first one

# Save complete results
with open("_enum_values.json", "w", encoding="utf-8") as f:
    json.dump({"all_enums": results, "chat_enums": chat_enums}, f, indent=2, ensure_ascii=False)
print(f"\nSaved {len(results)} total enums, {len(chat_enums)} chat enums to _enum_values.json")
