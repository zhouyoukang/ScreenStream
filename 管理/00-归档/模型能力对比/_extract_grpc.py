"""Extract gRPC chat protocol and model enumeration from Windsurf JS"""
import re, json

JS_FILE = r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js"
OUT = r"D:\道\道生一\一生二\模型能力对比\_grpc_extract.json"

print("Reading JS file...")
with open(JS_FILE, "r", encoding="utf-8", errors="ignore") as f:
    c = f.read()
print(f"  Size: {len(c)/1024/1024:.1f}MB")

results = {}

# 1. Extract all MODEL_ enum values
print("\n=== Model Enums ===")
model_enums = re.findall(r'(MODEL_[A-Z0-9_]+)\s*[=:]\s*["\']?(\d+)["\']?', c)
# Also try string format
model_strings = re.findall(r'"(MODEL_[A-Z0-9_]+)"', c)
unique_models = sorted(set(m for m in model_strings))
print(f"  Found {len(unique_models)} unique MODEL_ strings")
results["model_strings"] = unique_models[:100]

# 2. Extract model display names mapping
print("\n=== Model Display Names ===")
# Look for model name -> display name mappings
display_maps = re.findall(r'(MODEL_[A-Z0-9_]+)["\']?\s*[,:]\s*["\']([^"\']{3,50})["\']', c)
results["display_names"] = list(set(display_maps))[:80]
print(f"  Found {len(results['display_names'])} mappings")

# 3. Extract gRPC service definitions
print("\n=== gRPC Services ===")
grpc_services = re.findall(r'exa\.[a-z_]+_pb\.[A-Za-z_/]+', c)
unique_services = sorted(set(grpc_services))
results["grpc_types"] = unique_services
print(f"  Found {len(unique_services)} unique gRPC types")

# 4. Find GetChatMessageRequest fields
print("\n=== GetChatMessageRequest ===")
for m in re.finditer(r'GetChatMessageRequest', c):
    ctx = c[max(0,m.start()-100):m.start()+300]
    results.setdefault("chat_request_contexts", []).append(ctx)
    if len(results.get("chat_request_contexts", [])) >= 5:
        break

# 5. Find RawGetChatMessageRequest fields  
print("\n=== RawGetChatMessageRequest ===")
for m in re.finditer(r'RawGetChatMessageRequest', c):
    ctx = c[max(0,m.start()-100):m.start()+300]
    results.setdefault("raw_chat_request_contexts", []).append(ctx)
    if len(results.get("raw_chat_request_contexts", [])) >= 5:
        break

# 6. Find model_id or modelId patterns
print("\n=== Model Selection ===")
model_sel = re.findall(r'model[_.]?[iI]d["\']?\s*[=:]\s*[^\n;]{5,80}', c)
results["model_id_patterns"] = list(set(model_sel))[:30]
print(f"  Found {len(results['model_id_patterns'])} model_id patterns")

# 7. Find chat/completions or streaming patterns
print("\n=== Streaming/Chat Patterns ===")
stream_pats = re.findall(r'(stream[Cc]hat|chatStream|ServerStreaming)[^}]{0,100}', c)
results["stream_patterns"] = list(set(stream_pats))[:20]
print(f"  Found {len(results['stream_patterns'])} streaming patterns")

# 8. Find the actual gRPC method paths
print("\n=== gRPC Method Paths ===")
method_paths = re.findall(r'/exa\.[a-z_]+_pb\.[A-Za-z]+Service/[A-Za-z]+', c)
unique_methods = sorted(set(method_paths))
results["grpc_methods"] = unique_methods
print(f"  Found {len(unique_methods)} gRPC methods")
for m in unique_methods:
    print(f"  {m}")

# 9. Find credit/cost multiplier patterns
print("\n=== Credit Multipliers ===")
credit_pats = re.findall(r'credits?[Mm]ultiplier["\']?\s*[=:]\s*[^\n;]{3,50}', c)
results["credit_patterns"] = list(set(credit_pats))[:20]

# 10. Find model tier/category
tier_pats = re.findall(r'(premium|standard|lite|free)["\']?\s*[,})\]]\s*[^\n]{0,50}(MODEL_|model)', c)
results["tier_patterns"] = [str(t) for t in list(set(tier_pats))[:20]]

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nSaved to {OUT}")
