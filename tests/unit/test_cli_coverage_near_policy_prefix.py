from __future__ import annotations

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_coverage_near_policy_prefix_filters_to_none(tmp_path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # create minimal coverage.xml with something near threshold via CLI helper path
        # Reuse dev flow: run a no-op pytest to generate an empty coverage then skip; instead, write a tiny XML
        Path = __import__("pathlib").Path
        (Path("coverage.xml")).write_text(
            """<?xml version='1.0' encoding='UTF-8'?>
<coverage version="7.0" timestamp="0" branch-rate="0" line-rate="1.0">
  <packages>
    <package name="x">
      <classes>
        <class name="m" filename="mcp_rules_assistant/dummy.py" line-rate="0.97" lines-valid="100" lines-covered="97"/>
      </classes>
    </package>
  </packages>
</coverage>
""",
            encoding="utf-8",
        )
        # policy-prefix set to something mismatching to ensure the 'no near files' branch runs
        r = runner.invoke(
            app, ["coverage-near", "--within", "3", "--policy-prefix", "not_a_prefix/"],
        )
        out = r.stdout or ""
        assert r.exit_code == 0
        assert "无近阈值文件" in out or "no near" in out.lower()
