from __future__ import annotations

from pathlib import Path
from typing import Optional, List

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
        # 预留：写入前检查（计划/规则等）
        full.write_text(content, encoding)
        # 可选：写入后执行轻量增量检查（受配置 execution.fs_guard_post_checks 控制，默认关闭）
        try:
            exec_cfg = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            if bool(exec_cfg.get("fs_guard_post_checks", False)):
                # 惰性导入，避免基础路径下的开销
                from . import checks as _checks

                files: List[Path] = [full.resolve()]
                perf = (
                    self.cfg.get("performance", {})
                    if isinstance(self.cfg.get("performance", {}), dict)
                    else {}
                )
                on_commit = (
                    perf.get("on_commit", {})
                    if isinstance(perf.get("on_commit", {}), dict)
                    else {}
                )
                do_type = bool(on_commit.get("typecheck_incremental", True))
                res = _checks.run_checks(
                    files,
                    cwd=self.project_root,
                    do_lint=True,
                    do_type=do_type,
                    do_quick_tests=True,
                )
                if bool(exec_cfg.get("fs_guard_strict", False)) and not bool(
                    res.get("ok", True)
                ):
                    raise ValueError("FSGuard post checks failed under strict mode")
        except Exception:
            # 安全兜底：不因检查失败影响写入；若严格模式开启，则向上抛出
            ex_cfg = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            if bool(ex_cfg.get("fs_guard_strict", False)):
                raise
            pass
