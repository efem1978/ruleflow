from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        '    <class filename="pkg/a.py" line-rate="0.880"/>\n'
        '    <class filename="pkg/b.py" line-rate="0.905"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_mcp_server_coverage_export(tmp_path: Path, monkeypatch) -> None:
    # prepare project
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\ncoverage:\n  near: {within: 0.03, top: 50}\n",
        encoding="utf-8",
    )
    _write_cov_xml(tmp_path / "coverage.xml")
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool(
        "coverage.export",
        {
            "outDir": str(tmp_path / ".mcp/dashboard"),
            "weakTop": 10,
            "nearTop": 10,
            "within": 0.03,
        },
    )
    assert out.get("ok") is True
    dash = tmp_path / ".mcp/dashboard"
    assert (dash / "coverage_summary.json").exists()
    assert (dash / "weak_top.csv").exists()
    assert (dash / "near_top.csv").exists()
    assert (dash / "groups.csv").exists()
    # headers
    assert (dash / "weak_top.csv").read_text(encoding="utf-8").splitlines()[
        0
    ] == "file,coverage,threshold,delta"
    assert (dash / "near_top.csv").read_text(encoding="utf-8").splitlines()[
        0
    ] == "file,coverage,threshold,delta_up"
    assert (dash / "groups.csv").read_text(encoding="utf-8").splitlines()[
        0
    ] == "prefix,coverage,threshold,weak_count,files_count"


def test_mcp_server_license_verify(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("license.verify", {})
    # ok/False both acceptable in absence of license; ensure shape
    assert isinstance(out, dict)
    assert "ok" in out
