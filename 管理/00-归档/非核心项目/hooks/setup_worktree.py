#!/usr/bin/env python3
"""Post-setup worktree hook for ScreenStream_v2 Android project.
Copies non-version-controlled files needed for Gradle build."""

import os
import shutil
import sys

ROOT = os.environ.get("ROOT_WORKSPACE_PATH", "")
if not ROOT:
    print("WARNING: ROOT_WORKSPACE_PATH not set")
    sys.exit(0)

# Files to copy from original workspace to worktree
FILES_TO_COPY = [
    "local.properties",
    "google-services.json",
]

copied = 0
for f in FILES_TO_COPY:
    src = os.path.join(ROOT, f)
    if os.path.exists(src):
        shutil.copy2(src, f)
        print(f"Copied {f}")
        copied += 1

if copied == 0:
    print("No extra files needed (project uses env vars for SDK path)")

print("Worktree setup complete for ScreenStream_v2")