from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def log_security_event(
    project_root: Path, event: str, details: dict[str, Any] | None = None,
) -> None:
    """Append a structured security audit entry under .mcp/dashboard/security_audit.jsonl.

    Best-effort: never raises.
    Entry schema:
      { time: <ISO8601Z>, event: <str>, project: <str>, details?: <object> }
    """
    try:
        root = project_root.resolve()
        dash = root / ".mcp" / "dashboard"
        dash.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "time": _now_iso(),
            "event": str(event),
            "project": str(root),
        }
        if details:
            entry["details"] = details
        with (dash / "security_audit.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Never propagate audit failures
        return
