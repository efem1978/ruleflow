from __future__ import annotations

from pathlib import Path


from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_project_switch_add_link_errors(monkeypatch, tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path

    # Force MemoryManager.add_link to raise in both pre and post link attempts
    def boom(*_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    monkeypatch.setattr(srv.mm, "add_link", boom)
    out = srv._call_tool("project.switch", {"path": str(tmp_path / "subproj")})
    assert out["ok"] is True
    assert Path(out["root"]).name == "subproj"


def test_fs_apply_patch_disallow_patterns_exception_soft(
    monkeypatch, tmp_path: Path,
) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)

    class TrickyCfg:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, *_a, **_k):  # type: ignore[no-untyped-def]
            # First two calls (outer exec_cfg_eff) return dict; 3rd call (inner try) raises
            self.calls += 1
            if self.calls <= 2:
                return {}
            raise RuntimeError("cfg_boom")

    # Break only the inner disallow_patterns block to exercise except/pass without failing outer exec_cfg
    srv.cfg = TrickyCfg()  # type: ignore[assignment]
    out = srv._call_tool(
        "fs.apply_patch",
        {
            "files": [{"path": "docs/x.md", "content": "hello"}],
            "runChecks": True,
            "dryRun": True,
        },
    )
    assert out.get("ok") is True
    assert out.get("would_write") == [str(tmp_path / "docs/x.md")]


def test_rules_onboard_invalid_yaml_then_apply(monkeypatch, tmp_path: Path) -> None:
    # Prepare invalid YAML to trigger except branch (data = {}) and still apply
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("::not_yaml::", encoding="utf-8")

    out = srv._call_tool(
        "rules.onboard",
        {
            "scenario": "personal",
            "complexity": "small",
            "devMode": "tdd",
            "apply": True,
        },
    )
    assert out.get("ok") is True
    # new config should be valid YAML after apply
    text = cfg.read_text(encoding="utf-8")
    assert "performance:" in text
