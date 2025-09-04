from __future__ import annotations

from pathlib import Path
from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_project_detect_node_and_rust(tmp_path: Path) -> None:
    srv = JsonRpcServer(); srv.project_root = tmp_path
    # Node detection via package.json
    (tmp_path / 'package.json').write_text('{"name":"x","version":"0.0.1"}', encoding='utf-8')
    d1 = srv._call_tool('project.detect', {})
    assert d1.get('language') == 'node'
    # Rust detection via Cargo.toml (prefer rust when present and no node indicators?)
    # To ensure rust branch, remove node indicators
    (tmp_path / 'package.json').unlink()
    (tmp_path / 'Cargo.toml').write_text('[package]\nname="x"\nversion="0.1.0"\n', encoding='utf-8')
    d2 = srv._call_tool('project.detect', {})
    assert d2.get('language') == 'rust'

