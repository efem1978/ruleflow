from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple


PLAN_MD = Path(".mcp/plan.md")


DEFAULT_PLAN = (
    "# 项目计划 / Project Plan\n\n"
    "- 状态: planned\n"
    "- 当前步骤: （填写）\n"
    "- 下一步: （填写）\n"
    "- 风险与阻塞: （填写）\n"
)


def ensure_plan(project_root: Optional[Path] = None) -> Path:
    root = (project_root or Path.cwd()).resolve()
    path = root / PLAN_MD
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(DEFAULT_PLAN, encoding="utf-8")
    return path


def read_plan(project_root: Optional[Path] = None) -> str:
    path = ensure_plan(project_root)
    return path.read_text(encoding="utf-8")


def write_plan(text: str, project_root: Optional[Path] = None) -> Path:
    path = ensure_plan(project_root)
    path.write_text(text, encoding="utf-8")
    return path


def parse_plan(text: str) -> Tuple[str, str, str]:
    status = "planned"
    current = ""
    nxt = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- 状态:") or line.lower().startswith("- status:"):
            status = line.split(":", 1)[1].strip().lower()
        elif line.startswith("- 当前步骤:") or line.lower().startswith("- current step:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("- 下一步:") or line.lower().startswith("- next:"):
            nxt = line.split(":", 1)[1].strip()
    return status, current, nxt


def update_plan_fields(project_root: Optional[Path] = None, *, status: Optional[str] = None, current: Optional[str] = None, nxt: Optional[str] = None) -> Path:
    text = read_plan(project_root)
    lines = text.splitlines()
    def repl(prefix_cn: str, prefix_en: str, value: Optional[str]) -> None:
        nonlocal lines
        if value is None:
            return
        done = False
        for i, line in enumerate(lines):
            if line.strip().startswith(prefix_cn) or line.strip().lower().startswith(prefix_en.lower()):
                lines[i] = f"{prefix_cn} {value}"
                done = True
                break
        if not done:
            lines.append(f"{prefix_cn} {value}")
    if status is not None:
        repl("- 状态:", "- status:", status)
    if current is not None:
        repl("- 当前步骤:", "- current step:", current)
    if nxt is not None:
        repl("- 下一步:", "- next:", nxt)
    new_text = "\n".join(lines) + ("\n" if not lines[-1].endswith("\n") else "")
    return write_plan(new_text, project_root)
