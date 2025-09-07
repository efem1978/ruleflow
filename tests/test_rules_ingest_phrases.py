from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_english_at_least_coverage_maps_to_min_module(tmp_path: Path) -> None:
    d = tmp_path / "e.md"
    d.write_text("- at least 90% coverage", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.90) < 1e-6


def test_no_skip_or_xfail_maps_flag(tmp_path: Path) -> None:
    d = tmp_path / "n.md"
    d.write_text("- no skip or xfail", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert pol.get("test.no_skip_xfail") is True


def test_chinese_percent_module(tmp_path: Path) -> None:
    d = tmp_path / "cm.md"
    d.write_text("- 覆盖率 至少 九十五", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.95) < 1e-6


def test_chinese_percent_core(tmp_path: Path) -> None:
    d = tmp_path / "cc.md"
    d.write_text("- 核心 百分之 九十六", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_core")) - 0.96) < 1e-6


def test_english_percent_module_and_core(tmp_path: Path) -> None:
    d = tmp_path / "en.md"
    d.write_text(
        "- coverage at least 90 percent\n- core >= 96 percent", encoding="utf-8"
    )
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.90) < 1e-6
    assert abs(float(pol.get("coverage.min_core")) - 0.96) < 1e-6


def test_english_no_less_than_digits(tmp_path: Path) -> None:
    d = tmp_path / "en2.md"
    d.write_text("- no less than 93% coverage", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.93) < 1e-6


def test_chinese_core_percent_99(tmp_path: Path) -> None:
    d = tmp_path / "cn2.md"
    d.write_text("- 核心 百分之 九十九", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_core")) - 0.99) < 1e-6


def test_coverage_100_caps_to_1(tmp_path: Path) -> None:
    d = tmp_path / "cap.md"
    d.write_text("- 覆盖率 100%", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 1.0) < 1e-6


def test_english_words_percent(tmp_path: Path) -> None:
    d = tmp_path / "en_words.md"
    d.write_text(
        "- at least ninety five percent coverage\n- ninety five percent coverage",
        encoding="utf-8",
    )
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.95) < 1e-6


def test_english_words_percent_seventy_five_and_one_hundred(tmp_path: Path) -> None:
    d = tmp_path / "en_words2.md"
    d.write_text(
        "- seventy five percent coverage\n- core at least one hundred percent",
        encoding="utf-8",
    )
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.75) < 1e-6
    assert abs(float(pol.get("coverage.min_core")) - 1.0) < 1e-6


def test_english_words_percent_over_100_capped(tmp_path: Path) -> None:
    d = tmp_path / "en_words3.md"
    d.write_text("- coverage one hundred and one percent", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 1.0) < 1e-6


def test_chinese_words_over_100_capped(tmp_path: Path) -> None:
    d = tmp_path / "cn_over.md"
    d.write_text("- 覆盖率 一百零一", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 1.0) < 1e-6
