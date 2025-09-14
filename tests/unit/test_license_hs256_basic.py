import json
from pathlib import Path

from mcp_rules_assistant.license_utils import generate_license, verify_license


def test_hs256_generate_and_verify(tmp_path: Path) -> None:
    lic = generate_license(
        issued_to="user@example.com", expires="2030-01-01", machine="local"
    )
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic, ensure_ascii=False), encoding="utf-8")
    out = verify_license(path=p)
    assert out.get("activated") is True
    assert out.get("ok") is True
    assert out.get("signature_ok") is True
    assert out.get("date_ok") is True


def test_verify_invalid_date(tmp_path: Path) -> None:
    lic = generate_license(issued_to="u", expires="2030-01-01", machine="m")
    lic["expires"] = "bad-date"
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic, ensure_ascii=False), encoding="utf-8")
    out = verify_license(path=p)
    assert out.get("activated") is True
    assert out.get("ok") is False
    assert out.get("date_ok") is False
