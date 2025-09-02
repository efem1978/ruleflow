from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MEMORY_FILE = Path(".mcp/memory.json")


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str
    meta: Dict[str, Any]


class MemoryManager:
    def __init__(self, project_root: Optional[Path] = None, window: int = 20) -> None:
        self.project_root = project_root or Path.cwd()
        self.window = window
        self.path = self.project_root / DEFAULT_MEMORY_FILE
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps({"turns": [], "summary": ""}, ensure_ascii=False), "utf-8"
            )

    def append_turn(
        self, role: str, content: str, meta: Optional[Dict[str, Any]] = None
    ) -> None:
        data = self._read()
        data["turns"].append(asdict(Turn(role=role, content=content, meta=meta or {})))
        data["turns"] = data["turns"][-self.window :]
        data["summary"] = self._summarize(data["turns"], data.get("summary", ""))
        self._write(data)

    def snapshot(self) -> Dict[str, Any]:
        return self._read()

    def _summarize(self, turns: List[Dict[str, Any]], prev: str) -> str:
        # 轻量占位：保留用户指令、AI 关键决策与TODO 的简要摘要
        # 未来可插拔本地小模型，当前使用简单规则抽取
        important = []
        for t in turns[-self.window :]:
            text = t["content"].strip().replace("\n", " ")
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
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
