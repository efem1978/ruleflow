from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import load_config


class FSGuard:
    """包裹式文件写入：为将来的门禁预留挂钩（占位）。

    真实实现中，这里应：
    - 在写入前运行计划/规则/影响面检查
    - 写入后运行增量 lint/type/test 等（依据性能模式）
    - 与 git hooks/CI 协同
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = project_root or Path.cwd()
        self.cfg = load_config(self.project_root)

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        full = self.project_root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        # TODO: 调用计划/规则检查（占位）
        full.write_text(content, encoding)
        # TODO: 调用增量检查（占位）
