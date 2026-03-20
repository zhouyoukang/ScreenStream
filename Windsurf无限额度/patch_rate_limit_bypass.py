#!/usr/bin/env python3
"""
Windsurf Rate Limit Bypass Patch v1.0
=====================================
Patches the checkUserMessageRateLimit gate in workbench.desktop.main.js
to always pass (hasCapacity=true), enabling unlimited message sending.

Architecture:
  - Fail-Open exploit: the rate limit check is in a try/catch that silently continues on error
  - This patch takes the cleaner approach: make the check always return positive
  - Also updates product.json checksum to avoid "corrupt installation" warning

Patches:
  P6: Rate Limit Bypass - !Q1.hasCapacity → !1 (never blocks)
  P7: Capacity Check Bypass - !Pu.hasCapacity (capacity) → !1
  P10: Quota Exhaustion Bypass - DVe()→!1 (QUOTA billing users never exhausted)

Usage:
  python patch_rate_limit_bypass.py status   # Check current patch status
  python patch_rate_limit_bypass.py apply    # Apply patches
  python patch_rate_limit_bypass.py revert   # Revert to backup
"""

import sys
import os
import shutil
import hashlib
import base64
import json
import re
from datetime import datetime

WINDSURF_DIR = r"D:\Windsurf"
WORKBENCH_PATH = os.path.join(WINDSURF_DIR, "resources", "app", "out", "vs", "workbench", "workbench.desktop.main.js")
PRODUCT_JSON = os.path.join(WINDSURF_DIR, "resources", "app", "product.json")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "_windsurf_backups")

PATCHES = {
    "P6_RATE_LIMIT": {
        "name": "Rate Limit Bypass",
        "description": "checkUserMessageRateLimit always passes",
        "find": 'if(!Q1.hasCapacity)return np(),cy(void 0),Ts(Q1.message||"You have reached your message limit for this model. Please try again later or upgrade your account to a paid plan to access higher rate limits. https://windsurf.com/redirect/windsurf/add-credits"),!1',
        "replace": 'if(!1)return np(),cy(void 0),Ts(Q1.message||"You have reached your message limit for this model. Please try again later or upgrade your account to a paid plan to access higher rate limits. https://windsurf.com/redirect/windsurf/add-credits"),!1',
    },
    "P7_CAPACITY_CHECK": {
        "name": "Capacity Check Bypass",
        "description": "checkChatCapacity always passes",
        "find": 'if(!Pu.hasCapacity)return np(),cy(void 0),Ts(Pu.message||"We\'re currently facing high demand for this model. Please try again later."),!1',
        "replace": 'if(!1)return np(),cy(void 0),Ts(Pu.message||"We\'re currently facing high demand for this model. Please try again later."),!1',
    },
    "P8_INPUT_BLOCKER": {
        "name": "Input Blocker Bypass (Layer 1)",
        "description": "INSUFFICIENT_CASCADE_CREDITS error no longer blocks input",
        "find": 'if(_u){if(re?.code)switch(re.code){case Hb.WRITE_CHAT_INSUFFICIENT_CASCADE_CREDITS:et(xGt());break;case Hb.WRITE_CHAT_UPGRADE_FOR_CREDITS:et(TGt())}return!1}',
        "replace": 'if(!1){if(re?.code)switch(re.code){case Hb.WRITE_CHAT_INSUFFICIENT_CASCADE_CREDITS:et(xGt());break;case Hb.WRITE_CHAT_UPGRADE_FOR_CREDITS:et(TGt())}return!1}',
    },
    "P9_GRPC_CREDIT_ERROR": {
        "name": "gRPC Credit Error Neutralizer (Layer 3)",
        "description": "Server 'not enough credits'/'monthly acu limit reached' errors no longer trigger credit block UI",
        "find": 'Qve=(Z,B)=>Z?!!(Z.errorCode===ct.Cy.PermissionDenied&&Z.userErrorMessage.toLowerCase().includes(B)):!1',
        "replace": 'Qve=(Z,B)=>!1',
    },
    "P10_QUOTA_EXHAUSTION": {
        "name": "Quota Exhaustion Bypass (QUOTA billing root)",
        "description": "DVe() never reports quota exhausted — daily/weekly quota checks always pass",
        "find": 'DVe=Z=>vpe(Z)<=0',
        "replace": 'DVe=Z=>!1',
    },
}


def compute_checksum(filepath):
    """Compute SHA-256 checksum in base64 (VS Code format)."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode("ascii").rstrip("=")


def backup_file(filepath):
    """Create timestamped backup."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = os.path.basename(filepath)
    backup_path = os.path.join(BACKUP_DIR, f"{name}.{ts}.bak")
    shutil.copy2(filepath, backup_path)
    return backup_path


def check_status():
    """Check current patch status."""
    if not os.path.exists(WORKBENCH_PATH):
        print(f"ERROR: Workbench not found at {WORKBENCH_PATH}")
        return False

    with open(WORKBENCH_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"Windsurf: {WINDSURF_DIR}")
    print(f"Workbench: {WORKBENCH_PATH}")
    print(f"File size: {len(content):,} chars")
    print()

    all_applied = True
    for pid, patch in PATCHES.items():
        has_original = patch["find"] in content
        # For patches where find != replace, check if replace string exists
        if patch["find"] != patch["replace"]:
            has_patched = patch["replace"] in content
        else:
            has_patched = False

        if has_patched and not has_original:
            status = "APPLIED"
        elif has_patched and has_original:
            # Both exist (unlikely but possible if replace is substring of find)
            status = "APPLIED"
        elif has_original:
            status = "NOT APPLIED"
            all_applied = False
        else:
            status = "NOT FOUND (code changed?)"
            all_applied = False

        print(f"  {pid} ({patch['name']}): {status}")

    print()

    # Check product.json checksum
    current_checksum = compute_checksum(WORKBENCH_PATH)
    with open(PRODUCT_JSON, "r", encoding="utf-8") as f:
        product = json.load(f)

    stored_checksum = product.get("checksums", {}).get(
        "vs/workbench/workbench.desktop.main.js", ""
    )

    checksum_match = current_checksum == stored_checksum
    print(f"  Checksum match: {'YES' if checksum_match else 'NO (will show corrupt warning)'}")
    print(f"    Current:  {current_checksum}")
    print(f"    Stored:   {stored_checksum}")

    return all_applied


def apply_patches():
    """Apply all patches."""
    if not os.path.exists(WORKBENCH_PATH):
        print(f"ERROR: Workbench not found at {WORKBENCH_PATH}")
        return False

    # Backup
    backup = backup_file(WORKBENCH_PATH)
    product_backup = backup_file(PRODUCT_JSON)
    print(f"Backup: {backup}")
    print(f"Product backup: {product_backup}")

    with open(WORKBENCH_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    applied = 0
    for pid, patch in PATCHES.items():
        if patch["replace"] in content:
            print(f"  {pid}: Already applied, skipping")
            applied += 1
            continue

        if patch["find"] not in content:
            print(f"  {pid}: NOT FOUND - code may have changed")
            continue

        content = content.replace(patch["find"], patch["replace"], 1)
        print(f"  {pid}: APPLIED - {patch['description']}")
        applied += 1

    # Write patched workbench
    with open(WORKBENCH_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    # Update checksum in product.json
    new_checksum = compute_checksum(WORKBENCH_PATH)
    with open(PRODUCT_JSON, "r", encoding="utf-8") as f:
        product = json.load(f)

    if "checksums" in product:
        product["checksums"]["vs/workbench/workbench.desktop.main.js"] = new_checksum

    with open(PRODUCT_JSON, "w", encoding="utf-8") as f:
        json.dump(product, f, indent="\t")

    print(f"\n  Checksum updated: {new_checksum}")
    print(f"\n  {applied}/{len(PATCHES)} patches applied")
    print(f"\n  RESTART Windsurf to activate patches")

    return applied == len(PATCHES)


def revert():
    """Revert to most recent backup."""
    if not os.path.exists(BACKUP_DIR):
        print("No backups found")
        return False

    # Find most recent workbench backup
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("workbench") and f.endswith(".bak")],
        reverse=True,
    )

    if not backups:
        print("No workbench backups found")
        return False

    backup_path = os.path.join(BACKUP_DIR, backups[0])
    shutil.copy2(backup_path, WORKBENCH_PATH)
    print(f"Reverted workbench from: {backups[0]}")

    # Revert product.json
    product_backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("product") and f.endswith(".bak")],
        reverse=True,
    )

    if product_backups:
        product_backup = os.path.join(BACKUP_DIR, product_backups[0])
        shutil.copy2(product_backup, PRODUCT_JSON)
        print(f"Reverted product.json from: {product_backups[0]}")

    # Update checksum
    new_checksum = compute_checksum(WORKBENCH_PATH)
    with open(PRODUCT_JSON, "r", encoding="utf-8") as f:
        product = json.load(f)
    if "checksums" in product:
        product["checksums"]["vs/workbench/workbench.desktop.main.js"] = new_checksum
    with open(PRODUCT_JSON, "w", encoding="utf-8") as f:
        json.dump(product, f, indent="\t")

    print(f"Checksum updated: {new_checksum}")
    print("RESTART Windsurf to activate revert")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python patch_rate_limit_bypass.py [status|apply|revert]")
        return

    cmd = sys.argv[1].lower()
    if cmd == "status":
        check_status()
    elif cmd == "apply":
        apply_patches()
    elif cmd == "revert":
        revert()
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
