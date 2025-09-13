from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


def test_jb_ui_verify_includes_memory_turns(tmp_path: Path) -> None:
    # Arrange: replicate minimal repo layout under tmp
    root = tmp_path
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    # copy the verify script
    src = Path("scripts/jb-ui-verify.sh").resolve()
    text = src.read_text(encoding="utf-8")
    (scripts / "jb-ui-verify.sh").write_text(text, encoding="utf-8")
    os.chmod(scripts / "jb-ui-verify.sh", stat.S_IRWXU)
    # minimal .mcp files
    dash = root / ".mcp/dashboard"
    dash.mkdir(parents=True)
    (dash / "status.json").write_text(
        json.dumps(
            {
                "plan": {"status": "in_progress", "current": "X"},
                "coverage": {"weak": []},
            }
        ),
        encoding="utf-8",
    )
    mem = root / ".mcp/memory.json"
    mem.write_text(
        json.dumps(
            {
                "turns": [{"role": "user", "content": "hi", "meta": {}}],
                "summary": "x",
                "links": [],
            }
        ),
        encoding="utf-8",
    )

    # Act
    subprocess.run(
        ["bash", str(scripts / "jb-ui-verify.sh")],
        cwd=root,
        check=True,
        capture_output=True,
    )

    # Assert
    outp = dash / "jb_verify.json"
    assert outp.exists(), "jb_verify.json not produced"
    data = json.loads(outp.read_text(encoding="utf-8"))
    assert data.get("memory", {}).get("turns_count") == 1
    assert data.get("memory", {}).get("has_summary") is True
