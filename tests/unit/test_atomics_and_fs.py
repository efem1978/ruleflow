from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.atomics import atomic_write_json
from mcp_rules_assistant.fs_wrapper import FSGuard, atomic_write_json as atomic_write_json_mod


def test_write_text_and_json_atomic(tmp_path: Path) -> None:
    g = FSGuard(tmp_path)
    g.write_text_atomic(Path("a.txt"), "hello")
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello"
    g.write_json_atomic(Path("b.json"), {"x": 1}, indent=2)
    assert "\"x\": 1" in (tmp_path / "b.json").read_text(encoding="utf-8")
    # module-level wrapper
    atomic_write_json_mod(tmp_path / "c.json", {"y": 2}, indent=0)
    assert (tmp_path / "c.json").exists()


def test_atomic_write_json_standalone(tmp_path: Path) -> None:
    p = tmp_path / "d.json"
    atomic_write_json(p, {"z": 3})
    assert p.exists() and "\"z\": 3" in p.read_text(encoding="utf-8")

