from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fs_wrapper import atomic_write_json as _atomic_write_json

DEFAULT_MEMORY_FILE = Path(".mcp/memory.json")


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str
    meta: Dict[str, Any]


class MemoryManager:
    def __init__(
        self,
        project_root: Optional[Path] = None,
        window: int = 20,
        max_bytes: int = 64 * 1024,
        file_override: Optional[Path] = None,
    ) -> None:
        self.project_root = project_root or Path.cwd()
        self.window = window
        self.max_bytes = max(1024, int(max_bytes))
        self.path = (
            file_override
            if isinstance(file_override, Path)
            else self.project_root / DEFAULT_MEMORY_FILE
        )
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps(
                    {"turns": [], "summary": "", "links": []}, ensure_ascii=False
                ),
                "utf-8",
            )

    def append_turn(
        self, role: str, content: str, meta: Optional[Dict[str, Any]] = None
    ) -> None:
        data = self._read()
        data["turns"].append(asdict(Turn(role=role, content=content, meta=meta or {})))
        # window 表示保留的“消息条数”（turns），直接裁剪到最近 window 条
        data["turns"] = data["turns"][-self.window :]
        data["summary"] = self._summarize(data["turns"], data.get("summary", ""))
        data = self._compress_if_needed(data)
        self._write(data)

    def snapshot(self) -> Dict[str, Any]:
        return self._read()

    def add_link(self, project: str, task: str, note: str = "") -> None:
        data = self._read()
        links = data.get("links")
        if not isinstance(links, list):
            links = []
        from time import time as _now

        links.append(
            {"project": project, "task": task, "note": note, "ts": int(_now())}
        )
        links = links[-200:]
        data["links"] = links
        self._write(data)

    def _summarize(self, turns: List[Dict[str, Any]], prev: str) -> str:
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

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text("utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        # 使用原子写入，避免异常或并发导致的部分写入/损坏
        _atomic_write_json(self.path, data, indent=2)

    # ---- helpers ----
    def _compress_if_needed(self, data: Dict[str, Any]) -> Dict[str, Any]:
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
