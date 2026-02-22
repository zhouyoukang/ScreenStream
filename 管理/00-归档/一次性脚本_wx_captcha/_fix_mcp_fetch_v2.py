"""Fix fetch MCP: switch from uvx (broken pipe) to npx (all npx MCPs work fine)."""
import json, os

config_path = os.path.expanduser(r"~\.codeium\windsurf\mcp_config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

print(f"Before fetch config: {json.dumps(config['mcpServers']['fetch'], indent=2)}")

# Replace uvx with npx - all npx-based MCPs work reliably
config["mcpServers"]["fetch"] = {
    "command": "npx",
    "args": ["-y", "mcp-fetch"],
    "disabled": False
}

print(f"\nAfter fetch config: {json.dumps(config['mcpServers']['fetch'], indent=2)}")

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("\n✅ fetch MCP switched from uvx → npx. Need MCP refresh to apply.")
