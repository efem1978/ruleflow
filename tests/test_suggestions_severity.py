from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant import rules_ingest as ri
from mcp_rules_assistant.cli import app


def test_suggestions_have_severity_and_cli_summarizes(tmp_path: Path) -> None:
    d = tmp_path / "doc.md"
    d.write_text(
        "\n".join(
            [
                "- 覆盖率 90%",  # min -> enforce must
                "- 覆盖率 80%",  # conflict -> unify warn
                "- 覆盖率 不超过 95%",  # upper bound -> monitor info
            ],
        ),
        encoding="utf-8",
    )
    res = ri.ingest([str(d)], project_root=tmp_path)
    comp = res.get("compiled") or {}
    sugg = comp.get("suggestions") or []
    kinds = {s.get("severity") for s in sugg if isinstance(s, dict)}
    assert {"must", "warn", "info"}.issubset(kinds)

    # write compiled json and run CLI rules-explain --json
    m = tmp_path / ".mcp"
    m.mkdir(parents=True, exist_ok=True)
    (m / "rules_compiled.json").write_text(
        (
            (tmp_path / ".mcp" / "rules_compiled.json").read_text(encoding="utf-8")
            if (tmp_path / ".mcp" / "rules_compiled.json").exists()
            else ""
        ),
        encoding="utf-8",
    )
    # The above line copies compiled file if ingest() wrote it in .mcp; otherwise no-op
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Ensure compiled exists in this isolated FS
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        (Path(".mcp") / "rules_compiled.json").write_text(
            (tmp_path / ".mcp" / "rules_compiled.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        r = runner.invoke(app, ["rules-explain", "--json"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert (
            '"suggestions_severity"' in out
            and '"must"' in out
            and '"warn"' in out
            and '"info"' in out
        )
