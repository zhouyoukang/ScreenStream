"""
工作流存储 — YAML/JSON持久化 + 版本管理
=========================================
工作流以JSON文件存储在 workflows/ 目录下，
支持列表/加载/保存/删除/版本管理。

单独测试:
  cd 认知代理
  python -m workflow.storage
"""

import json
import os
import shutil
import time
import logging
from pathlib import Path

log = logging.getLogger("workflow.storage")

# 默认存储目录
_STORE_DIR = Path(__file__).parent.parent / "data" / "workflows"
_STORE_DIR.mkdir(parents=True, exist_ok=True)


def save(workflow_dict, overwrite=True):
    """
    保存工作流到文件。
    workflow_dict: Workflow.to_dict() 的输出
    """
    wf_id = workflow_dict.get("id", "wf_unknown")
    filepath = _STORE_DIR / f"{wf_id}.json"

    if filepath.exists() and not overwrite:
        # 版本递增
        existing = load(wf_id)
        if existing:
            workflow_dict["version"] = existing.get("version", 0) + 1

    # 备份旧版本
    if filepath.exists():
        backup_dir = _STORE_DIR / "_versions"
        backup_dir.mkdir(exist_ok=True)
        version = workflow_dict.get("version", 1)
        backup_path = backup_dir / f"{wf_id}_v{version - 1}.json"
        shutil.copy2(filepath, backup_path)

    workflow_dict["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(workflow_dict, f, ensure_ascii=False, indent=2)

    log.info("Saved workflow: %s → %s", wf_id, filepath)
    return {"ok": True, "id": wf_id, "path": str(filepath)}


def load(wf_id):
    """加载工作流"""
    filepath = _STORE_DIR / f"{wf_id}.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def list_all():
    """列出所有工作流"""
    workflows = []
    for f in sorted(_STORE_DIR.glob("wf_*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                d = json.load(fh)
                workflows.append({
                    "id": d.get("id"),
                    "name": d.get("name"),
                    "description": d.get("description", ""),
                    "version": d.get("version", 1),
                    "steps": len(d.get("steps", [])),
                    "created_at": d.get("created_at"),
                    "updated_at": d.get("updated_at"),
                    "tags": d.get("tags", []),
                })
        except Exception as e:
            log.warning("Failed to read %s: %s", f, e)
    return workflows


def delete(wf_id):
    """删除工作流"""
    filepath = _STORE_DIR / f"{wf_id}.json"
    if filepath.exists():
        filepath.unlink()
        log.info("Deleted workflow: %s", wf_id)
        return {"ok": True, "id": wf_id}
    return {"error": "not found", "id": wf_id}


def get_versions(wf_id):
    """获取工作流的版本历史"""
    versions = []
    backup_dir = _STORE_DIR / "_versions"
    if backup_dir.exists():
        for f in sorted(backup_dir.glob(f"{wf_id}_v*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    d = json.load(fh)
                    versions.append({
                        "version": d.get("version", 0),
                        "updated_at": d.get("updated_at"),
                        "file": f.name,
                    })
            except Exception:
                pass
    return versions


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print(f"Store dir: {_STORE_DIR}")
    print(f"Workflows: {len(list_all())}")
    for wf in list_all():
        print(f"  {wf['id']}: {wf['name']} (v{wf['version']}, {wf['steps']} steps)")
