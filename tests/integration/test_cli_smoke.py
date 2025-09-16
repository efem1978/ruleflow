from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import cli


def test_cli_version_and_explain_performance(tmp_path: Path, capsys) -> None:
    # prepare minimal config
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "performance: { mode: fast }\n", encoding="utf-8"
    )

    # change CWD for load_config()
    import os

    cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        cli.version()
        out = capsys.readouterr().out
        assert "mcp-rules-assistant" in out

        cli.explain_performance()
        out2 = capsys.readouterr().out
        assert "Performance Summary" in out2
    finally:
        try:
            os.chdir(cwd)
        except (FileNotFoundError, OSError):
            # If original directory was deleted, just continue
            pass
