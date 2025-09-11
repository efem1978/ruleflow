from __future__ import annotations

import io
import os
from pathlib import Path

import pytest


def test_cli_coverage_export_no_coverage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 确保在临时目录中执行，且不存在 coverage.xml
    monkeypatch.chdir(tmp_path)
    # 由于缺少 coverage.xml，应打印警告并 Exit(1)
    import typer

    from mcp_rules_assistant.cli import coverage_export as cli_cov_export

    with pytest.raises(typer.Exit):
        cli_cov_export(
            out_dir=str(tmp_path / ".mcp" / "dashboard"),
            weak_top=20,
            near_top=50,
            within=None,
        )


def test_cli_coverage_export_writes_csv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 在当前仓库根下执行，避免依赖 .mcp 配置
    # monkeypatch 覆盖 cov_summary/cov_groups/cov_near 以提供最小数据，覆盖 CSV 写入路径
    import mcp_rules_assistant.cli as cli

    def fake_summary(**kwargs):
        return {
            "ok": True,
            "weak": [{"file": "x.py", "coverage": 0.80, "threshold": 0.90}],
        }

    def fake_groups(**kwargs):
        return {"ok": True, "groups": []}

    def fake_near(**kwargs):
        return {"ok": True, "near": []}

    monkeypatch.setattr(cli, "cov_summary", fake_summary)
    monkeypatch.setattr(cli, "cov_groups", fake_groups)
    monkeypatch.setattr(cli, "cov_near", fake_near)
    outd = tmp_path / ".mcp" / "dashboard"
    # 不应抛异常；应成功生成 CSV/JSON
    cli.coverage_export(out_dir=str(outd), weak_top=20, near_top=50, within=None)
    assert (outd / "coverage_summary.json").exists()
    assert (outd / "weak_top.csv").exists()


def test_cli_license_require_on_off_with_invalid_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 使用临时项目根，准备损坏的 YAML 以覆盖 except 分支
    monkeypatch.chdir(tmp_path)
    p = tmp_path / ".mcp"
    p.mkdir(parents=True, exist_ok=True)
    (p / "assistant.yaml").write_text(":: not yaml ::", encoding="utf-8")
    from mcp_rules_assistant.cli import license_require_off, license_require_on

    # off/on 均应能吞掉 YAML 解析异常并写回新内容
    license_require_off()
    license_require_on()
    text = (p / "assistant.yaml").read_text(encoding="utf-8")
    assert "license" in text and "required" in text


def test_cli_health_status_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 让 auto_status.generate_status 抛异常，覆盖 health 中的 fallback 分支
    import mcp_rules_assistant.auto_status as auto_status
    from mcp_rules_assistant.cli import health

    def boom(*args, **kwargs):  # noqa: ANN001, ANN002
        raise RuntimeError("broken")

    monkeypatch.setattr(auto_status, "generate_status", boom)
    # 仅验证不抛异常并输出 JSON 文本
    health(json_out=True)
    out = capsys.readouterr().out
    assert "coverage" in out and "status_ok" in out
