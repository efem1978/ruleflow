from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mcp_rules_assistant import checks
from mcp_rules_assistant.hooks import (
    generate_pre_commit_config,
    install_git_hooks,
    render_github_ci_yaml,
)
from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.progress import write_plan


def test_checks_skip_when_no_impacted_and_missing_tools(tmp_path: Path) -> None:
    # No tests dir; change a non-test file — quick tests should be skipped
    f = tmp_path / "foo.py"
    f.write_text("print('x')\n", encoding="utf-8")
    res = checks.run_checks(
        [f], cwd=tmp_path, do_lint=True, do_type=True, do_quick_tests=True
    )
    assert res.get("ok") is True
    steps = res.get("steps") or []
    # Expect lint/type/tests steps present; some may be skipped if tools missing
    assert any("lint" in s for s in steps)
    assert any("type" in s for s in steps)
    assert any("tests" in s for s in steps)
    # Quick tests step likely skipped due to no impacted tests
    t = next((s for s in steps if "tests" in s), None)
    assert t is not None and (t["tests"].get("skipped") or t["tests"].get("ok"))


def test_render_github_ci_yaml_respects_compiled_rules(tmp_path: Path) -> None:
    # Prepare compiled rules enabling secrets scan, container required, and SAST strict
    compiled = tmp_path / ".mcp/rules_compiled.json"
    compiled.parent.mkdir(parents=True, exist_ok=True)
    import json

    compiled.write_text(
        json.dumps(
            {
                "policy": {
                    "security.secrets_scan": True,
                    "container.required": True,
                    "security.sast_strict": True,
                }
            }
        ),
        encoding="utf-8",
    )
    yml = render_github_ci_yaml(tmp_path)
    assert "Pre-commit (all files)" in yml  # secrets scan triggers pre-commit in CI
    assert (
        "Check Dockerfile existence" in yml
    )  # container.required triggers Dockerfile check
    assert "SAST (semgrep)" in yml  # sast strict triggers semgrep step


def test_pre_commit_config_contains_secrets_when_rule_enabled(tmp_path: Path) -> None:
    # Enable security.secrets_scan via compiled rules
    compiled = tmp_path / ".mcp/rules_compiled.json"
    compiled.parent.mkdir(parents=True, exist_ok=True)
    compiled.write_text(
        '{"policy": {"security.secrets_scan": true}}',
        encoding="utf-8",
    )
    cfg = generate_pre_commit_config(tmp_path)
    text = cfg.read_text(encoding="utf-8")
    assert "detect-secrets" in text


def test_plan_gate_script_requires_step_token(tmp_path: Path) -> None:
    # Install hooks to generate .mcp/plan_gate.py
    install_git_hooks(tmp_path)
    # Write plan as in_progress with a current step
    plan_text = (
        "# 项目计划 / Project Plan\n\n"
        "- 状态: in_progress\n"
        "- 当前步骤: 实现A\n"
        "- 下一步: B\n"
    )
    write_plan(plan_text, tmp_path)
    # Message without token should fail
    msg = tmp_path / "COMMIT_MSG.txt"
    msg.write_text("feat: something without token", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(tmp_path / ".mcp/plan_gate.py"), "commit-msg", str(msg)],
        cwd=tmp_path,
    )
    assert p.returncode != 0
    # With token should pass
    msg.write_text("feat: impl [step:实现A]", encoding="utf-8")
    p2 = subprocess.run(
        [sys.executable, str(tmp_path / ".mcp/plan_gate.py"), "commit-msg", str(msg)],
        cwd=tmp_path,
    )
    assert p2.returncode == 0


def test_fs_apply_patch_strict_rejects_skip_marker(tmp_path: Path) -> None:
    # Start server in temp project
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Attempt to write a test file containing skip marker in strict mode
    try:
        srv._call_tool(
            "fs.apply_patch",
            {
                "files": [
                    {
                        "path": "tests/test_x.py",
                        "content": "import pytest\n@pytest.mark.skip\ndef test_a(): pass\n",
                    }
                ],
                "runChecks": True,
                "strict": True,
            },
        )
        assert False, "should have raised"
    except Exception as e:
        assert "skip/xfail" in str(e)


def test_run_quick_tests_picks_impacted_tests(tmp_path: Path) -> None:
    # Create a module and its test
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "foo.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
    (tmp_path / "tests/test_foo.py").write_text(
        "from foo import add\n\ndef test_add(): assert add(1,2)==3\n", encoding="utf-8"
    )
    res = checks.run_quick_tests([tmp_path / "foo.py"], cwd=tmp_path)
    assert res.get("ok") is True


def test_quick_tests_ordering_uses_failure_history_and_recency(tmp_path: Path) -> None:
    # Prepare last_failed_tests.json with two tests and different histories
    last = tmp_path / ".mcp/last_failed_tests.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    import json
    import time

    now = time.time()
    t1 = str((tmp_path / "tests/test_slow.py").resolve())
    t2 = str((tmp_path / "tests/test_flaky.py").resolve())
    data = {
        "tests": [t1, t2],
        "nodeids": [],
        "test_counts": {t1: 3, t2: 1},  # slow failed more in total
        "node_counts": {},
        # But flaky had a very recent failure → should get high bonus and be ordered first
        "events": [
            {
                "nodeid": "tests/test_slow.py::test_a",
                "file": t1,
                "ts": str(now - 10 * 24 * 3600),
            },
            {
                "nodeid": "tests/test_flaky.py::test_b",
                "file": t2,
                "ts": str(now - 3600),
            },
        ],
    }
    last.write_text(json.dumps(data), encoding="utf-8")
    res = checks.run_quick_tests([], cwd=tmp_path)
    cmd = res.get("cmd") or []
    # Extract tail arguments that are files (simple heuristic)
    files = [c for c in cmd if isinstance(c, str) and c.endswith(".py")]
    assert t2 in files and t1 in files
    # Ensure flaky (recent) appears before slow in the ordered list
    assert files.index(t2) < files.index(t1)


def test_dockerfile_baseline_gate(tmp_path: Path) -> None:
    # Enable container.policy.baseline and install hooks to generate gate
    compiled = tmp_path / ".mcp/rules_compiled.json"
    compiled.parent.mkdir(parents=True, exist_ok=True)
    compiled.write_text(
        '{"policy": {"container.policy.baseline": true}}', encoding="utf-8"
    )
    install_git_hooks(tmp_path)
    gate = tmp_path / ".mcp/dockerfile_gate.py"
    assert gate.exists()
    import subprocess
    import sys

    # Bad Dockerfile (violates baseline)
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.11-slim\nUSER root\n", encoding="utf-8"
    )
    p = subprocess.run([sys.executable, str(gate)], cwd=tmp_path)
    assert p.returncode != 0
    # Good Dockerfile (passes baseline)
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.11-slim\nRUN echo ok\n", encoding="utf-8"
    )
    p2 = subprocess.run([sys.executable, str(gate)], cwd=tmp_path)
    assert p2.returncode == 0


def test_no_skip_xfail_grep_command(tmp_path: Path) -> None:
    # Initialize a git repo and create a file with xfail marker
    import subprocess

    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    bad = tmp_path / "tests/test_bad.py"
    bad.write_text(
        "import pytest\n\n@pytest.mark.xfail\ndef test_bad(): pass\n", encoding="utf-8"
    )
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # The grep used in pre-commit should detect the marker
    r = subprocess.run(
        ["git", "grep", "-nE", r"pytest\.mark\.(skip|xfail)", "--", "."], cwd=tmp_path
    )
    assert r.returncode == 0  # found

    # Now replace content to remove markers and ensure not found
    bad.write_text("def test_ok(): assert 1\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "-A"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    r2 = subprocess.run(
        ["git", "grep", "-nE", r"pytest\.mark\.(skip|xfail)", "--", "."], cwd=tmp_path
    )
    assert r2.returncode != 0  # not found


def test_quick_tests_nodeid_ordering(tmp_path: Path) -> None:
    # Seed last_failed with tests and nodeids so quick tests builds a cmd including them
    import json
    import time

    last = tmp_path / ".mcp/last_failed_tests.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    tfile = str((tmp_path / "tests/test_dummy.py").resolve())
    n1 = "tests/test_dummy.py::test_old"
    n2 = "tests/test_dummy.py::test_recent"
    now = time.time()
    data = {
        "tests": [tfile],
        "nodeids": [n1, n2],
        "test_counts": {tfile: 1},
        "node_counts": {n1: 1, n2: 1},
        "events": [
            {"nodeid": n1, "file": tfile, "ts": str(now - 10 * 24 * 3600)},
            {"nodeid": n2, "file": tfile, "ts": str(now - 60)},
        ],
    }
    last.write_text(json.dumps(data), encoding="utf-8")
    res = checks.run_quick_tests([], cwd=tmp_path)
    cmd = res.get("cmd")
    assert isinstance(cmd, list)
    # Ensure both nodeids present after the file entry
    assert n1 in cmd and n2 in cmd
    assert cmd.index(n2) < cmd.index(n1)  # recent first


def test_quick_tests_prioritizes_specific_failed_node_id(tmp_path: Path) -> None:
    """
    Tests that if a file has multiple node IDs, the one with a more recent
    failure is prioritized in the pytest command.
    """
    import json
    import time

    last = tmp_path / ".mcp/last_failed_tests.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    tfile = str((tmp_path / "tests/test_multi.py").resolve())

    # test_multi.py has two tests: test_stable and test_flaky
    # test_stable has failed more overall, but not recently.
    # test_flaky has failed less overall, but very recently.
    n_stable = "tests/test_multi.py::test_stable"
    n_flaky = "tests/test_multi.py::test_flaky"
    now = time.time()

    data = {
        "tests": [tfile],
        "nodeids": [n_stable, n_flaky],
        "test_counts": {tfile: 10},
        "node_counts": {n_stable: 9, n_flaky: 1},
        "events": [
            # 9 old failures for stable
            *(
                [{"nodeid": n_stable, "file": tfile, "ts": str(now - 15 * 24 * 3600)}]
                * 9
            ),
            # 1 very recent failure for flaky
            {"nodeid": n_flaky, "file": tfile, "ts": str(now - 60)},
        ],
    }
    last.write_text(json.dumps(data), encoding="utf-8")

    # Create dummy test files so pytest doesn't fail immediately
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests/test_multi.py").write_text(
        "def test_stable(): pass\ndef test_flaky(): pass"
    )

    res = checks.run_quick_tests([], cwd=tmp_path)
    cmd = res.get("cmd")
    assert isinstance(cmd, list)

    # The command should contain the file path, and then the node IDs
    assert tfile in cmd
    assert n_stable in cmd
    assert n_flaky in cmd

    # The flaky (but recent) node ID should appear before the stable (but old) one.
    assert cmd.index(n_flaky) < cmd.index(n_stable)
