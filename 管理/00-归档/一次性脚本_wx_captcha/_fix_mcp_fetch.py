"""Fix fetch MCP: add PYTHONIOENCODING env var to prevent pipe encoding issues."""
import json, os, shutil

config_path = os.path.expanduser(r"~\.codeium\windsurf\mcp_config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

fetch = config.get("mcpServers", {}).get("fetch", {})
print(f"Before: {json.dumps(fetch, indent=2)}")

# Fix 1: Add PYTHONIOENCODING env var (official recommendation)
if "env" not in fetch:
    fetch["env"] = {}
fetch["env"]["PYTHONIOENCODING"] = "utf-8"

# Fix 2: Add --ignore-robots-txt to avoid robots.txt blocking
if "--ignore-robots-txt" not in fetch.get("args", []):
    fetch["args"].append("--ignore-robots-txt")

config["mcpServers"]["fetch"] = fetch
print(f"\nAfter: {json.dumps(fetch, indent=2)}")

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("\n✅ mcp_config.json updated. Restart MCP servers to apply.")
