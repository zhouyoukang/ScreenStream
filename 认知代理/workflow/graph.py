"""
意图行为图谱 — 参数化工作流定义
=================================
将用户标注的操作序列提取为参数化的工作流图谱。
图谱是 JSON/YAML 格式，人类可读可编辑。

结构:
  {
    "id": "wf_abc123",
    "name": "保存并运行Python脚本",
    "description": "在IDE中保存当前文件，切换到终端执行",
    "version": 1,
    "created_at": "...",
    "parameters": {
      "file_path": {"type": "string", "description": "目标文件路径"},
      "run_command": {"type": "string", "default": "python ${file_path}"}
    },
    "steps": [
      {
        "id": "step_1",
        "action": "hotkey",
        "params": {"key": "ctrl+s"},
        "expected_state": {"file_modified": true},
        "on_failure": "retry",
        "max_retries": 2
      },
      {
        "id": "step_2",
        "action": "hotkey",
        "params": {"key": "ctrl+`"},
        "expected_state": {"focused_app_category": "terminal"}
      },
      {
        "id": "step_3",
        "action": "type_text",
        "params": {"text": "${run_command}\\n"},
        "expected_state": {}
      }
    ],
    "triggers": {
      "manual": true,
      "pattern_match": ["save_file → toggle_terminal"]
    }
  }
"""

import json
import uuid
import time
import copy
import re
import logging
from pathlib import Path

log = logging.getLogger("workflow.graph")


class WorkflowStep:
    """工作流中的一个步骤"""

    def __init__(self, action, params=None, expected_state=None,
                 on_failure="stop", max_retries=1, description=""):
        self.id = f"step_{uuid.uuid4().hex[:6]}"
        self.action = action
        self.params = params or {}
        self.expected_state = expected_state or {}
        self.on_failure = on_failure  # "stop" | "retry" | "skip" | "alternative"
        self.max_retries = max_retries
        self.description = description
        self.alternatives = []  # 备选动作列表

    def to_dict(self):
        d = {
            "id": self.id,
            "action": self.action,
            "params": self.params,
        }
        if self.description:
            d["description"] = self.description
        if self.expected_state:
            d["expected_state"] = self.expected_state
        if self.on_failure != "stop":
            d["on_failure"] = self.on_failure
        if self.max_retries > 1:
            d["max_retries"] = self.max_retries
        if self.alternatives:
            d["alternatives"] = [a.to_dict() for a in self.alternatives]
        return d

    @classmethod
    def from_dict(cls, d):
        step = cls(
            action=d["action"],
            params=d.get("params", {}),
            expected_state=d.get("expected_state", {}),
            on_failure=d.get("on_failure", "stop"),
            max_retries=d.get("max_retries", 1),
            description=d.get("description", ""),
        )
        step.id = d.get("id", step.id)
        step.alternatives = [cls.from_dict(a) for a in d.get("alternatives", [])]
        return step


class Workflow:
    """参数化工作流图谱"""

    def __init__(self, name, description=""):
        self.id = f"wf_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.version = 1
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.updated_at = self.created_at
        self.parameters = {}  # name -> {type, description, default}
        self.steps = []       # List[WorkflowStep]
        self.triggers = {"manual": True}
        self.tags = []
        self.metadata = {}

    def add_parameter(self, name, param_type="string", description="", default=None):
        self.parameters[name] = {
            "type": param_type,
            "description": description,
        }
        if default is not None:
            self.parameters[name]["default"] = default
        return self

    def add_step(self, action, params=None, expected_state=None,
                 on_failure="stop", max_retries=1, description=""):
        step = WorkflowStep(action, params, expected_state, on_failure, max_retries, description)
        self.steps.append(step)
        return step

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parameters": self.parameters,
            "steps": [s.to_dict() for s in self.steps],
            "triggers": self.triggers,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d):
        wf = cls(name=d["name"], description=d.get("description", ""))
        wf.id = d.get("id", wf.id)
        wf.version = d.get("version", 1)
        wf.created_at = d.get("created_at", wf.created_at)
        wf.updated_at = d.get("updated_at", wf.updated_at)
        wf.parameters = d.get("parameters", {})
        wf.steps = [WorkflowStep.from_dict(s) for s in d.get("steps", [])]
        wf.triggers = d.get("triggers", {"manual": True})
        wf.tags = d.get("tags", [])
        wf.metadata = d.get("metadata", {})
        return wf

    @classmethod
    def from_json(cls, json_str):
        return cls.from_dict(json.loads(json_str))

    def resolve_params(self, values):
        """用实际值替换参数占位符 ${param_name}"""
        resolved = copy.deepcopy(self)
        for step in resolved.steps:
            step.params = _resolve_dict(step.params, values, self.parameters)
        return resolved


def _resolve_dict(d, values, param_defs):
    """递归替换字典中的 ${param} 占位符"""
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _resolve_string(v, values, param_defs)
        elif isinstance(v, dict):
            result[k] = _resolve_dict(v, values, param_defs)
        elif isinstance(v, list):
            result[k] = [_resolve_string(i, values, param_defs) if isinstance(i, str) else i for i in v]
        else:
            result[k] = v
    return result


def _resolve_string(s, values, param_defs):
    """替换字符串中的 ${param} 占位符"""
    def replacer(match):
        param_name = match.group(1)
        if param_name in values:
            return str(values[param_name])
        if param_name in param_defs and "default" in param_defs[param_name]:
            return str(param_defs[param_name]["default"])
        return match.group(0)  # 未解析的保持原样

    return re.sub(r'\$\{(\w+)\}', replacer, s)


# ---------------------------------------------------------------------------
# 从意图序列提取工作流
# ---------------------------------------------------------------------------

def extract_workflow_from_intents(intents, name=None, description=None):
    """
    从一组意图记录中自动提取工作流。

    intents: list of intent dicts from semantics.intent.extract_intents()
    """
    if not intents:
        return None

    wf = Workflow(
        name=name or _auto_name(intents),
        description=description or _auto_description(intents),
    )

    # 将每个意图转为工作流步骤
    for intent_rec in intents:
        pattern = intent_rec.get("pattern", "unknown")
        intent_name = intent_rec.get("intent", "")
        context = intent_rec.get("context", {})
        actions = intent_rec.get("actions", [])

        # 根据模式类型映射到工作流动作
        if pattern == "hotkey":
            # 从actions中提取按键
            key_data = _extract_key_from_actions(actions)
            step = wf.add_step(
                action="hotkey",
                params={"key": key_data},
                description=intent_name,
                on_failure="retry",
                max_retries=2,
            )
            # 如果是保存，期望文件变化
            if "保存" in intent_name:
                step.expected_state = {"file_modified": True}

        elif pattern == "typing":
            typed_text = intent_rec.get("pattern_details", {}).get("preview", "")
            # 参数化: 长文本变为参数
            if len(typed_text) > 10:
                param_name = f"text_{len(wf.parameters)}"
                wf.add_parameter(param_name, "string", f"输入文本 (来自: {intent_name})", typed_text)
                step = wf.add_step(
                    action="type_text",
                    params={"text": f"${{{param_name}}}"},
                    description=intent_name,
                )
            else:
                step = wf.add_step(
                    action="type_text",
                    params={"text": typed_text},
                    description=intent_name,
                )

        elif pattern == "click" or pattern == "double_click":
            # 点击不太适合录制回放（坐标会变），但保留为参考
            step = wf.add_step(
                action=pattern,
                params={"note": "坐标依赖当前UI布局，执行时需动态定位"},
                description=intent_name,
                on_failure="skip",
            )

        elif pattern == "file_operation":
            step = wf.add_step(
                action="file_operation",
                params=intent_rec.get("result", {}),
                description=intent_name,
            )

        elif pattern == "app_switch":
            step = wf.add_step(
                action="focus_app",
                params={"app": context.get("app", "")},
                description=intent_name,
            )

        else:
            step = wf.add_step(
                action="unknown",
                params={"original_pattern": pattern},
                description=intent_name,
                on_failure="skip",
            )

    return wf


def _auto_name(intents):
    """自动生成工作流名称"""
    intent_names = [i.get("intent", "") for i in intents if i.get("intent")]
    if len(intent_names) <= 3:
        return " → ".join(intent_names)
    return f"{intent_names[0]} → ... → {intent_names[-1]}"


def _auto_description(intents):
    """自动生成工作流描述"""
    apps = set(i.get("context", {}).get("app", "") for i in intents if i.get("context", {}).get("app"))
    return f"跨 {', '.join(apps)} 的 {len(intents)} 步操作" if apps else f"{len(intents)} 步操作"


def _extract_key_from_actions(actions):
    """从动作列表中提取按键组合"""
    for a in actions:
        data = a.get("data", {})
        mods = data.get("modifiers", [])
        name = data.get("name", "")
        if name:
            if mods:
                return "+".join(mods + [name])
            return name
    return ""


# ---------------------------------------------------------------------------
# 独立测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 创建示例工作流
    wf = Workflow("保存并运行Python", "在IDE中保存当前文件并在终端运行")
    wf.add_parameter("file_path", "string", "Python文件路径", "main.py")
    wf.add_parameter("run_cmd", "string", "运行命令", "python ${file_path}")
    wf.add_step("hotkey", {"key": "ctrl+s"}, {"file_modified": True}, "retry", 2, "保存文件")
    wf.add_step("hotkey", {"key": "ctrl+`"}, {"focused_app_category": "terminal"}, description="切换终端")
    wf.add_step("type_text", {"text": "${run_cmd}\n"}, description="执行命令")

    print("=== 工作流定义 ===")
    print(wf.to_json())

    # 参数化解析
    resolved = wf.resolve_params({"file_path": "server.py"})
    print("\n=== 解析后 (file_path=server.py) ===")
    for step in resolved.steps:
        print(f"  [{step.action}] {step.params}")
