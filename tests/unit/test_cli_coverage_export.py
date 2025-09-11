from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _write_cov_xml(path: Path) -> None:
    # one weak (<0.90), one near (~0.905 with threshold 0.90)
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        '    <class filename="mod/weak.py" line-rate="0.880"/>\n'
        '    <class filename="mod/near.py" line-rate="0.905"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_cli_coverage_export_outputs(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        Path(".mcp/assistant.yaml").write_text(
            "performance:\n  on_push:\n    coverage: {min_module: 0.90}\ncoverage:\n  near: {within: 0.03, top: 50}\n",
            encoding="utf-8",
        )
        _write_cov_xml(Path("coverage.xml"))

        out_dir = Path(".mcp/dashboard")
        r = runner.invoke(
            app,
            [
                "coverage-export",
                "--out-dir",
                str(out_dir),
                "--weak-top",
                "10",
                "--near-top",
                "10",
                "--within",
                "3",
            ],
        )
        assert r.exit_code == 0
        # files exist
        for name in [
            "coverage_summary.json",
            "weak_top.csv",
            "near_top.csv",
            "groups.csv",
        ]:
            assert (out_dir / name).exists(), f"missing {name}"
        # check headers
        assert (out_dir / "weak_top.csv").read_text(encoding="utf-8").splitlines()[
            0
        ] == "file,coverage,threshold,delta"
        assert (out_dir / "near_top.csv").read_text(encoding="utf-8").splitlines()[
            0
        ] == "file,coverage,threshold,delta_up"
        assert (out_dir / "groups.csv").read_text(encoding="utf-8").splitlines()[
            0
        ] == "prefix,coverage,threshold,weak_count,files_count"
