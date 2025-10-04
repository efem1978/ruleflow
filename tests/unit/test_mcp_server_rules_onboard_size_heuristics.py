from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_onboard_complexity_medium_by_size(tmp_path: Path) -> None:
    # create ~250 python files to trigger medium branch
    d = tmp_path / "src"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(0, 250):
        (d / f"f{i}.py").write_text("\n", encoding="utf-8")
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("rules.onboard", {"apply": False})
    assert out.get("complexity") == "medium"
