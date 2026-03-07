"""Extract ALL model enums and gRPC chat protocol from Windsurf JS"""
import re, json

JS = r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js"
print("Reading...")
with open(JS, "r", encoding="utf-8", errors="ignore") as f:
    c = f.read()

# 1. ALL MODEL_ strings (complete list)
all_models = sorted(set(re.findall(r'"(MODEL_[A-Z0-9_]+)"', c)))
print(f"Total MODEL_ strings: {len(all_models)}")

# Filter to actual chat models (not internal enums)
chat_models = [m for m in all_models if any(k in m for k in [
    'CLAUDE', 'GPT', 'GEMINI', 'GROK', 'DEEPSEEK', 'QWEN', 'KIMI', 
    'GLM', 'LLAMA', 'MINIMAX', 'SWE', 'CASCADE', 'CODEX', 'O3', 'O4'
])]
print(f"\nChat models ({len(chat_models)}):")
for m in chat_models:
    print(f"  {m}")

# 2. Find model enum numeric values (protobuf field numbers)
print("\n=== Model Enum Values ===")
# Pattern: MODEL_XXX=123 or "MODEL_XXX":123
enum_vals = re.findall(r'(MODEL_(?:CLAUDE|GPT|CHAT_GPT|GEMINI|GROK|DEEPSEEK|QWEN|KIMI|GLM|LLAMA|MINIMAX|SWE|CODEX|O3|O4)[A-Z0-9_]*)["\']?\s*[=:]\s*(\d+)', c)
for name, val in sorted(set(enum_vals), key=lambda x: int(x[1])):
    print(f"  {name} = {val}")

# 3. Find gRPC chat method - the actual RPC path used
print("\n=== gRPC RPC Paths ===")
rpc_paths = re.findall(r'["\'](/exa\.[a-z_]+_pb\.\w+/\w+)["\']', c)
for p in sorted(set(rpc_paths)):
    print(f"  {p}")

# 4. Find ServerStreaming chat patterns
print("\n=== Server Streaming ===")
for m in re.finditer(r'[Ss]erver[Ss]treaming[^;]{0,200}', c):
    txt = m.group().replace('\n', ' ')[:200]
    print(f"  {txt}")
    if m.start() > 10000000:
        break

# 5. Find the chat request builder
print("\n=== Chat Request Builder ===")
for m in re.finditer(r'GetChatMessage(?:Request)?[^;]{0,300}', c):
    txt = m.group().replace('\n', ' ')[:250]
    if 'model' in txt.lower() or 'prompt' in txt.lower() or 'message' in txt.lower():
        print(f"  @{m.start()}: {txt}")

# 6. Find model config with credits
print("\n=== Model Configs ===")
configs = re.findall(r'(MODEL_[A-Z0-9_]+)["\']?\s*[,:]\s*\{[^}]{0,200}(?:credit|cost|tier|multiplier)[^}]{0,100}\}', c, re.IGNORECASE)
for cfg in configs[:20]:
    print(f"  {cfg[:200]}")

# 7. Find how models are sent in requests
print("\n=== Model in Request ===")
pats = re.findall(r'(?:chat_model|chatModel|model_enum|modelEnum)["\']?\s*[=:]\s*[^\n;]{5,100}', c)
for p in sorted(set(pats))[:20]:
    print(f"  {p}")

# Save
with open("_models_full.json", "w", encoding="utf-8") as f:
    json.dump({"all_models": all_models, "chat_models": chat_models, "enum_vals": list(set(enum_vals))}, f, indent=2, ensure_ascii=False)
print(f"\nSaved to _models_full.json")
