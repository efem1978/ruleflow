from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .audit import log_security_event as _audit
from .config import load_config
from .fs_wrapper import atomic_write_json as _atomic_write_json

DEFAULT_MEMORY_FILE = Path(".mcp/memory.json")


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str
    meta: dict[str, Any]


class MemoryManager:
    def __init__(
        self,
        project_root: Path | None = None,
        window: int = 20,
        max_bytes: int = 64 * 1024,
        file_override: Path | None = None,
    ) -> None:
        self.project_root = project_root or Path.cwd()
        self.window = window
        self.max_bytes = max(1024, int(max_bytes))
        self.path = (
            file_override
            if isinstance(file_override, Path)
            else self.project_root / DEFAULT_MEMORY_FILE
        )
        # optional masking patterns from config
        self._mask_re: list[re.Pattern[str]] = []
        self._hard_disable: bool = False
        try:
            cfg = load_config(self.project_root)
            mem = (
                cfg.get("memory", {}) if isinstance(cfg.get("memory", {}), dict) else {}
            )
            # hard-disable switch: when true, any write attempt must fail
            self._hard_disable = bool(mem.get("hard_disable", False))
            pats = mem.get("mask_patterns")
            if isinstance(pats, list):
                for pat in pats:
                    if isinstance(pat, str) and pat.strip():
                        try:
                            self._mask_re.append(re.compile(pat))
                        except Exception:
                            pass
        except Exception:
            self._mask_re = []
            self._hard_disable = False
        self._ensure_file()

    def _resolve_target_inside_project(self) -> Path | None:
        """Resolve memory file path and ensure it stays within <project>/.mcp.

        Returns the resolved path when safe; otherwise returns None. The check is
        defensive against symlinks or path tricks that could point outside the
        current project's .mcp directory (cross‑project leakage).
        """
        try:
            root = self.project_root.resolve()
            mcp_dir = (root / ".mcp").resolve()
            target = self.path.resolve()
            # Pathlib >=3.11: Path.is_relative_to
            try:
                inside = target.is_relative_to(mcp_dir)  # type: ignore[attr-defined]
            except Exception:
                inside = str(target).startswith(str(mcp_dir) + "/") or str(
                    target,
                ) == str(mcp_dir)
            if not inside:
                try:
                    _audit(
                        self.project_root,
                        "memory.read_denied",
                        {"reason": "path_outside_mcp", "target": str(target)},
                    )
                except Exception:
                    pass
                return None
            # Optionally disallow reading through symlinks entirely (more strict)
            import os as _os

            trust_symlink = str(
                _os.environ.get("MCP_MEMORY_TRUST_SYMLINK", ""),
            ).strip().lower() in {"1", "true", "on", "yes", "y"}
            try:
                if not trust_symlink and self.path.is_symlink():
                    try:
                        _audit(
                            self.project_root,
                            "memory.read_denied",
                            {"reason": "symlink_disallowed", "path": str(self.path)},
                        )
                    except Exception:
                        pass
                    return None
            except Exception:
                # If symlink check fails, prefer to deny
                return None
            # Disallow hard-linked targets by default to avoid cross-project shared content
            try:
                import os as _os

                allow_hardlink = str(
                    _os.environ.get("MCP_MEMORY_TRUST_HARDLINK", ""),
                ).strip().lower() in {"1", "true", "on", "yes", "y"}
                st = self.path if self.path.exists() else target
                stinfo = st.stat() if hasattr(st, "stat") else None
                nlink = int(getattr(stinfo, "st_nlink", 1)) if stinfo else 1
                if not allow_hardlink and nlink > 1:
                    try:
                        _audit(
                            self.project_root,
                            "memory.read_denied",
                            {
                                "reason": "hardlink_disallowed",
                                "path": str(self.path),
                                "nlink": nlink,
                            },
                        )
                    except Exception:
                        pass
                    return None
            except Exception:
                # On error, be conservative
                return None
            return target
        except Exception:
            return None

    def _ensure_file(self) -> None:
        # Ensure .mcp directory exists under current project
        try:
            root = self.project_root.resolve()
            (root / ".mcp").mkdir(parents=True, exist_ok=True)
        except Exception:
            return
        # Create file only when safe (inside .mcp and not disallowed symlink)
        try:
            safe = self._resolve_target_inside_project()
            if safe is None:
                return  # do not create unsafe target
            if not safe.exists():
                _atomic_write_json(
                    safe,
                    {"turns": [], "summary": "", "links": []},
                    indent=2,
                )
        except Exception:
            # Best-effort init; skip on failure
            return

    def append_turn(
        self, role: str, content: str, meta: dict[str, Any] | None = None,
    ) -> None:
        masked = content
        if self._mask_re:
            try:
                for r in self._mask_re:
                    masked = r.sub("***", masked)
            except Exception:
                masked = content
        data = self._read()
        data["turns"].append(asdict(Turn(role=role, content=masked, meta=meta or {})))
        # window 表示保留的“消息条数”（turns），直接裁剪到最近 window 条
        data["turns"] = data["turns"][-self.window :]
        data["summary"] = self._summarize(data["turns"], data.get("summary", ""))
        data = self._compress_if_needed(data)
        self._write(data)

    def snapshot(self) -> dict[str, Any]:
        return self._read()

    def add_link(self, project: str, task: str, note: str = "") -> None:
        data = self._read()
        links = data.get("links")
        if not isinstance(links, list):
            links = []
        from time import time as _now

        links.append(
            {"project": project, "task": task, "note": note, "ts": int(_now())},
        )
        links = links[-200:]
        data["links"] = links
        self._write(data)

    def _summarize(self, turns: list[dict[str, Any]], prev: str) -> str:
        # 轻量占位：保留用户指令、AI 关键决策与TODO 的简要摘要
        # 未来可插拔本地小模型，当前使用简单规则抽取
        important = []
        for t in turns[-self.window :]:
            if not isinstance(t, dict):
                continue
            text = str(t.get("content", "")).strip().replace("\n", " ")
            if t["role"] == "user":
                important.append(f"Q: {text[:160]}")
            else:
                # 粗略提取：包含“计划/下一步/总结/进度/规则”关键词
                if any(
                    k in text
                    for k in [
                        "计划",
                        "下一步",
                        "总结",
                        "进度",
                        "规则",
                        "plan",
                        "next",
                        "summary",
                        "progress",
                        "rule",
                    ]
                ):
                    important.append(f"A: {text[:200]}")
        return "\n".join(important[-40:])

    def _read(self) -> dict[str, Any]:
        safe = self._resolve_target_inside_project()
        if safe is None:
            # Safe fallback: do not read anything outside .mcp; return empty snapshot
            return {"turns": [], "summary": "", "links": []}
        try:
            return json.loads(safe.read_text("utf-8"))
        except Exception:
            # Corrupted or unreadable → fallback to empty snapshot
            return {"turns": [], "summary": "", "links": []}

    def _write(self, data: dict[str, Any]) -> None:
        # Global emergency hard-disable via env (highest priority)
        try:
            import os as _os

            if str(_os.environ.get("MCP_MEMORY_HARD_DISABLE", "")).strip().lower() in {
                "1",
                "true",
                "on",
                "yes",
                "y",
            }:
                _audit(
                    self.project_root,
                    "memory.write_denied",
                    {"reason": "env_hard_disable"},
                )
                raise ValueError("memory write blocked by MCP_MEMORY_HARD_DISABLE")
        except Exception:
            pass
        # honor hard-disable (project-level kill switch)
        if self._hard_disable:
            _audit(self.project_root, "memory.write_denied", {"reason": "hard_disable"})
            raise ValueError("memory.hard_disable is true; writes are blocked")
        # 路径强校验：仅允许写入到 <project_root>/.mcp 下；拒绝通过符号链接/硬链接写入
        try:
            root = self.project_root.resolve()
            target = self.path.resolve()
            mcp_dir = (root / ".mcp").resolve()
            try:
                ok = target.is_relative_to(mcp_dir)  # py311+
            except AttributeError:
                ok = str(target).startswith(str(mcp_dir) + "/") or str(target) == str(
                    mcp_dir,
                )
            if not ok:
                _audit(
                    self.project_root,
                    "memory.write_denied",
                    {"reason": "path_outside_mcp", "target": str(target)},
                )
                raise ValueError("memory write path outside project .mcp")
            # reject symlink writes and (by default) hard-linked targets
            try:
                if self.path.is_symlink():
                    _audit(
                        self.project_root,
                        "memory.write_denied",
                        {"reason": "symlink_target"},
                    )
                    raise ValueError("memory write denied: symlink target")
            except Exception:
                # if symlink check fails, deny
                _audit(
                    self.project_root,
                    "memory.write_denied",
                    {"reason": "symlink_check_error"},
                )
                raise
            try:
                import os as _os

                allow_hardlink = str(
                    _os.environ.get("MCP_MEMORY_TRUST_HARDLINK", ""),
                ).strip().lower() in {"1", "true", "on", "yes", "y"}
                st = self.path.stat() if self.path.exists() else None
                nlink = int(getattr(st, "st_nlink", 1)) if st else 1
                if not allow_hardlink and nlink > 1:
                    _audit(
                        self.project_root,
                        "memory.write_denied",
                        {"reason": "hardlink_target", "nlink": nlink},
                    )
                    raise ValueError("memory write denied: hardlink target")
            except Exception:
                # on error, deny
                _audit(
                    self.project_root,
                    "memory.write_denied",
                    {"reason": "hardlink_check_error"},
                )
                raise
        except Exception:
            # 容错：若强校验异常，宁可拒绝写入
            raise
        # 使用原子写入，避免异常或并发导致的部分写入/损坏
        _atomic_write_json(self.path, data, indent=2)

    # ---- helpers ----
    def _compress_if_needed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure serialized memory does not exceed max_bytes via lossy trimming.

        Strategy (stable/deterministic):
        - Keep window constraint already applied.
        - If size > max_bytes, then for older turns first (excluding the last 2),
          truncate 'content' to <= 120 chars with ellipsis, and drop large meta.
        - Repeat once; if still too large, drop oldest turns beyond half window (but never below 3).
        """
        try:
            txt = json.dumps(data, ensure_ascii=False)
            if len(txt.encode("utf-8")) <= self.max_bytes:
                return data
            # Trim older turns' content
            turns = (
                list(data.get("turns", []))
                if isinstance(data.get("turns", []), list)
                else []
            )
            n = len(turns)
            for i in range(max(0, n - 3)):
                t = turns[i]
                if not isinstance(t, dict):
                    continue
                c = str(t.get("content", ""))
                if len(c) > 120:
                    t["content"] = c[:117] + "..."
                m = t.get("meta")
                if isinstance(m, dict) and len(json.dumps(m)) > 200:
                    t["meta"] = {k: v for k, v in list(m.items())[:5]}
            data["turns"] = turns
            txt = json.dumps(data, ensure_ascii=False)
            if len(txt.encode("utf-8")) <= self.max_bytes:
                return data
            # As a last resort, drop oldest quarter of turns, keeping >=3
            keep = max(3, int(len(turns) * 0.75))
            data["turns"] = turns[-keep:]
            return data
        except Exception:
            return data
