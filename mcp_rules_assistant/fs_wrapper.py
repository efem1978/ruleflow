from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomics import atomic_write_json as _atomic_write_json_impl
from .atomics import atomic_write_text as _atomic_write_text_impl
from .config import load_config


class FSGuard:
    """包裹式文件写入：提供可选的轻量门禁挂钩。

    当前实现：
    - 写入前：路径/扩展名白名单与符号链接保护（可严格模式）。
    - 写入后：可选运行增量 lint/type/test（execution.fs_guard_post_checks）。
    - 与 git hooks/CI 协同：重型门禁仍由 push/CI 执行，保持“快速内环”。
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = project_root or Path.cwd()
        self.cfg = load_config(self.project_root)

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        full = self.project_root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        # 禁止对现有符号链接写入，以避免间接覆盖目标文件
        try:
            if full.exists() and full.is_symlink():
                raise ValueError("FSGuard: 目标是符号链接，拒绝写入")
        except Exception:
            ex_cfg: Dict[str, Any] = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            if bool(ex_cfg.get("fs_guard_strict", False)):
                raise
        # 前置：路径白名单/扩展名白名单（若配置）
        try:
            exec_cfg: Dict[str, Any] = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            root_res = self.project_root.resolve()
            dest = full.resolve()
            dest.relative_to(root_res)
            prefixes = exec_cfg.get("allowed_write_prefixes")
            if isinstance(prefixes, list) and prefixes:
                rel = str(dest.relative_to(root_res)).replace("\\", "/")
                okp = any(
                    str(prefix) and rel.startswith(str(prefix)) for prefix in prefixes
                )
                if not okp:
                    raise ValueError("FSGuard: 路径不在允许前缀清单内")
            exts = exec_cfg.get("allowed_write_extensions")
            if isinstance(exts, list) and exts:
                if dest.suffix.lower() not in [
                    str(e).lower() for e in exts if isinstance(e, str)
                ]:
                    raise ValueError("FSGuard: 扩展名不在允许清单内")
        except Exception:
            # 如启用严格模式，向上抛出；否则仅作提示性保护
            ex_cfg2: Dict[str, Any] = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            if bool(ex_cfg2.get("fs_guard_strict", False)):
                raise
        # 预留：写入前检查（计划/规则等）
        full.write_text(content, encoding)
        # 可选：写入后执行轻量增量检查（受配置 execution.fs_guard_post_checks 控制，默认关闭）
        try:
            exec_cfg_post: Dict[str, Any] = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            if bool(exec_cfg_post.get("fs_guard_post_checks", False)):
                # 惰性导入，避免基础路径下的开销
                from . import checks as _checks

                files: List[Path] = [full.resolve()]
                perf: Dict[str, Any] = (
                    self.cfg.get("performance", {})
                    if isinstance(self.cfg.get("performance", {}), dict)
                    else {}
                )
                on_commit: Dict[str, Any] = (
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
                if bool(exec_cfg_post.get("fs_guard_strict", False)) and not bool(
                    res.get("ok", True)
                ):
                    raise ValueError("FSGuard post checks failed under strict mode")
        except Exception:
            # 安全兜底：不因检查失败影响写入；若严格模式开启，则向上抛出
            ex_cfg_fallback: Dict[str, Any] = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            if bool(ex_cfg_fallback.get("fs_guard_strict", False)):
                raise

    # ---- Atomic helpers ----
    def write_text_atomic(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> None:
        """原子方式写入文本：委托共用实现，降低重复与风险。"""
        full = self.project_root / path
        _atomic_write_text_impl(full, content, encoding=encoding)

    def write_json_atomic(
        self, path: Path, data: Any, *, indent: int | None = None
    ) -> None:
        """原子方式写入 JSON（UTF-8，不转义），indent 可选。"""
        _atomic_write_json_impl(self.project_root / path, data, indent=indent)


# Module-level utility for callers not using FSGuard instance
def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """原子写文本（保持 API 向后兼容，内部委托共用实现）。"""
    _atomic_write_text_impl(path, content, encoding=encoding)


def atomic_write_json(path: Path, data: Any, *, indent: int | None = None) -> None:
    """原子写 JSON（保持 API 向后兼容，内部委托共用实现）。"""
    _atomic_write_json_impl(path, data, indent=indent)
