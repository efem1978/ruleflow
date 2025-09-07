from __future__ import annotations

import shutil
from pathlib import Path

from mcp_rules_assistant.atomics import atomic_write_text


def test_atomic_cleanup_except_on_move_failure(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "file.txt"

    # Force shutil.move to fail so that temp file remains and cleanup runs
    def bad_move(src: str, dst: str):  # type: ignore[no-untyped-def]
        raise OSError("simulated move failure")

    monkeypatch.setattr(shutil, "move", bad_move)

    # Make unlink raise to exercise the except branch inside finally cleanup
    calls = {"n": 0}
    orig_unlink = Path.unlink

    def bad_unlink(self):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        raise OSError("unlink fail")

    monkeypatch.setattr(Path, "unlink", bad_unlink)

    # Move failure will propagate; we still exercise cleanup except branch
    import pytest

    with pytest.raises(OSError):
        atomic_write_text(target, "content")

    # Restore unlink to avoid cross-test side effects
    monkeypatch.setattr(Path, "unlink", orig_unlink)
