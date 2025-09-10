from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.memory import MemoryManager


def test_fs_apply_patch_rejects_symlink(tmp_path: Path) -> None:
    # Prepare a symlink destination inside project
    proj = tmp_path
    docs = proj / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    real = docs / "real.md"
    real.write_text("orig", encoding="utf-8")
    link = docs / "link.md"
    # Create a symlink pointing to real file
    try:
        link.symlink_to(real)
    except Exception:
        pytest.skip("symlink not supported on this platform")

    # Write strict config before server init so FSGuard picks it up
    (proj / ".mcp").mkdir(parents=True, exist_ok=True)
    (proj / ".mcp/assistant.yaml").write_text(
        "execution:\n  fs_guard_strict: true\n",
        encoding="utf-8",
    )
    srv = JsonRpcServer()
    srv.project_root = proj
    from mcp_rules_assistant.fs_wrapper import FSGuard  # local import for test

    srv.fs = FSGuard(proj)

    # Attempt to write via fs.apply_patch should be rejected for symlink
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {
                "files": [{"path": "docs/link.md", "content": "updated"}],
                "runChecks": False,
                "strict": False,
                "dryRun": False,
            },
        )


def test_rules_onboard_apply_with_invalid_yaml(tmp_path: Path) -> None:
    # Write invalid YAML to trigger parse-except branch in server.apply path
    m = tmp_path / ".mcp"
    m.mkdir(parents=True, exist_ok=True)
    (m / "assistant.yaml").write_text(": {", encoding="utf-8")

    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("rules.onboard", {"apply": True})
    assert out.get("ok") is True and out.get("applied") is True
    # The server should have repaired/rewritten config despite YAML parse error
    assert (m / "assistant.yaml").exists()


def test_project_switch_add_link_errors_are_tolerated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Patch MemoryManager.add_link to raise, so both 'switched_to' and 'switched_from' branches hit except-pass
    def boom(self, project: str, task: str, note: str = "") -> None:  # noqa: ANN001
        raise RuntimeError("no link")

    monkeypatch.setattr(MemoryManager, "add_link", boom, raising=True)

    p1 = tmp_path / "a"
    p2 = tmp_path / "b"
    p1.mkdir()
    p2.mkdir()
    srv = JsonRpcServer()
    srv.project_root = p1
    srv.mm = MemoryManager(p1)
    out = srv._call_tool("project.switch", {"path": str(p2)})
    assert out.get("ok") is True and out.get("root") == str(p2)
