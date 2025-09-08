from pathlib import Path

from mcp_rules_assistant.config import get_min_module, load_config


def test_get_min_module_from_project_yaml(tmp_path: Path) -> None:
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        """
performance:
  on_push:
    coverage:
      min_module: 0.96
""".strip(),
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert abs(get_min_module(cfg, default=0.90) - 0.96) < 1e-9

