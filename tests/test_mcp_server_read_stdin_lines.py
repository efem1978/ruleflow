from __future__ import annotations

import io
import sys

import mcp_rules_assistant.mcp_server as msv


def test__read_stdin_lines(monkeypatch) -> None:
    fake = io.StringIO("a\nb\n")
    monkeypatch.setattr(sys, "stdin", fake)
    lines = msv._read_stdin_lines()
    assert lines == ["a", "b"]
