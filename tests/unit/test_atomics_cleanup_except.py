from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.atomics import atomic_write_text


def test_atomic_cleanup_except(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    # Monkeypatch Path.unlink to raise on cleanup path
    calls = {"n": 0}

    orig_unlink = Path.unlink

    def bad_unlink(self):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        raise OSError("unlink fail")

    # patch only for tmp path cleanup by intercepting Path.unlink globally
    monkeypatch.setattr(Path, "unlink", bad_unlink)
    # This should not raise despite unlink failure and will exercise except branch
    atomic_write_text(target, "x")
    # ensure file exists
    assert target.exists()

    # restore to avoid side effects in other tests
    monkeypatch.setattr(Path, "unlink", orig_unlink)
