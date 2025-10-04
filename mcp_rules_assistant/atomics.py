from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write text to a file.

    Writes to a same-directory temp file and moves into place to minimize
    risks of partial writes or corruption on interruption.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    try:
        tmp.write_text(content, encoding=encoding)
        shutil.move(str(tmp), str(path))
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            # best-effort cleanup; ignoring cleanup errors is intentional
            pass  # nosec B110


def atomic_write_json(path: Path, data: Any, *, indent: int | None = None) -> None:
    """Atomically write JSON (UTF-8, no ASCII escaping)."""
    import json as _json

    txt = _json.dumps(data, ensure_ascii=False, indent=indent)
    atomic_write_text(path, txt, encoding="utf-8")
