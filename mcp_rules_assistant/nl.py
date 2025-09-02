from __future__ import annotations

from typing import Dict, Optional

SYNONYMS: Dict[str, str] = {
    # 记忆
    "开启滚动记忆": "memory.toggle_auto",
    "关闭滚动记忆": "memory.toggle_auto",
    "enable rolling memory": "memory.toggle_auto",
    "disable rolling memory": "memory.toggle_auto",
    "记忆快照": "memory.snapshot",
    "snapshot": "memory.snapshot",
    # 规则/钩子/环境
    "安装钩子": "git.install_hooks",
    "install hooks": "git.install_hooks",
    "初始化规则": "rules.init",
    "init rules": "rules.init",
    "摄取规则": "rules.ingest",
    "ingest rules": "rules.ingest",
    "校验规则": "rules.validate",
    "validate rules": "rules.validate",
    "应用门禁": "rules.enforce",
    "enforce rules": "rules.enforce",
    "apply gates": "rules.enforce",
    "生成 ci": "ci.generate",
    "生成CI": "ci.generate",
    "校验 ci": "ci.validate",
    "自修复 ci": "ci.autofix",
    "载入规则": "resources.read",
    "load rules": "resources.read",
    "加载建议": "resources.read",
    "load suggestions": "resources.read",
    "加载覆盖率": "resources.read",
    "load coverage": "resources.read",
    "近阈值": "coverage.near",
    "near threshold": "coverage.near",
    "准备环境": "env.prepare",
    "prepare environment": "env.prepare",
    "prepare env": "env.prepare",
    "开启记忆": "memory.toggle_auto",
    "关闭记忆": "memory.toggle_auto",
}


def parse(text: str) -> Optional[str]:
    t = text.strip().lower()
    for k, v in SYNONYMS.items():
        if k.lower() in t:
            return v
    return None
