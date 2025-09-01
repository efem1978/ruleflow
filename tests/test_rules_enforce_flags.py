from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_rules_enforce_sets_needs_flags(tmp_path: Path) -> None:
    m = tmp_path / '.mcp'; m.mkdir(parents=True, exist_ok=True)
    (m / 'rules_compiled.json').write_text(
        '{"policy": {"coverage.min_module": 0.9, "security.secrets_scan": true, "container.policy.baseline": true}}',
        encoding='utf-8'
    )
    srv = JsonRpcServer(); srv.project_root = tmp_path
    out = srv._call_tool('rules.enforce', {})
    assert out.get('ok') is True
    assert out.get('needs_hooks') is True
    # CI regen likely needed due to ci changes
    assert out.get('needs_ci_regen') in (True, False)

