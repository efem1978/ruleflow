from __future__ import annotations

import json
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, Optional

from .config import load_config


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def generate_pre_commit_config(project_root: Optional[Path] = None) -> Path:
    root = (project_root or Path.cwd()).resolve()
    cfg = load_config(root)
    min_module = cfg["performance"]["on_push"]["coverage"]["min_module"]
    # 从已编译规则读取增强策略
    compiled_policy = {}
    compiled_path = root / ".mcp/rules_compiled.json"
    if compiled_path.exists():
        try:
            compiled_policy = json.loads(compiled_path.read_text(encoding="utf-8")).get(
                "policy", {}
            )
        except Exception:
            compiled_policy = {}
    secrets_block = ""
    if compiled_policy.get("security.secrets_scan"):
        secrets_block = (
            "  - repo: https://github.com/Yelp/detect-secrets\n"
            "    rev: v1.4.0\n"
            "    hooks:\n"
            "      - id: detect-secrets\n"
            "        stages: [push]\n"
        )
    docker_local_hook = ""
    if compiled_policy.get("container.policy.baseline"):
        docker_local_hook = (
            "      - id: dockerfile-baseline\n"
            "        name: dockerfile baseline (push)\n"
            "        entry: python .mcp/dockerfile_gate.py\n"
            "        language: system\n"
            "        pass_filenames: false\n"
            "        stages: [push]\n"
        )
    text = f"""
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.6
    hooks:
      - id: ruff
        args: ["--fix"]
        stages: [commit]
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
        stages: [commit]
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        stages: [commit]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        stages: [commit]
{secrets_block}  - repo: local
    hooks:
      - id: plan-gate
        name: plan state & commit message gate (commit-msg)
        entry: python .mcp/plan_gate.py commit-msg
        language: system
        stages: [commit-msg]
{docker_local_hook}      - id: pytest-with-coverage
        name: pytest with coverage (push)
        entry: sh -c 'pytest -q --maxfail=1 --disable-warnings -W error --strict-markers --cov --cov-report=xml:coverage.xml --cov-report=term-missing --cov-fail-under={int(min_module*100)}'
        language: system
        pass_filenames: false
        stages: [push]
      - id: no-skip-xfail
        name: forbid skip/xfail (push)
        entry: sh -c 'if git grep -nE "pytest\\.mark\\.(skip|xfail)" -- . >/dev/null; then echo "Found skip/xfail markers. Disallowed."; exit 1; fi'
        language: system
        pass_filenames: false
        stages: [push]
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.7
    hooks:
      - id: bandit
        args: ["-q", "-ll", "-x", "tests"]
        stages: [push]
""".lstrip()
    path = root / ".pre-commit-config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def install_git_hooks(project_root: Optional[Path] = None) -> Dict[str, str]:
    root = (project_root or Path.cwd()).resolve()
    # 生成 pre-commit 配置
    pcfg = generate_pre_commit_config(root)

    # 写入 .git/hooks/pre-push（调用 pre-commit 的 push 阶段）
    hooks_dir = root / ".git" / "hooks"
    _ensure_dir(hooks_dir)
    pre_push = hooks_dir / "pre-push"
    script = """#!/bin/sh
if command -v pre-commit >/dev/null 2>&1; then
  echo "[mcp] running pre-commit (push stage) ..."
  pre-commit run --hook-stage push --all-files
  exit $?
else
  echo "[mcp] pre-commit not found; skipping push checks. Install with: pip install pre-commit"
  exit 0
fi
"""
    pre_push.write_text(script, encoding="utf-8")
    pre_push.chmod(pre_push.stat().st_mode | stat.S_IEXEC)

    # 写入计划门禁脚本 .mcp/plan_gate.py
    script_path = root / ".mcp/plan_gate.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        (
            "#!/usr/bin/env python3\n"
            "import sys, re, pathlib\n"
            "root = pathlib.Path('.').resolve()\n"
            "plan = root / '.mcp/plan.md'\n"
            "if not plan.exists():\n"
            "    print('[mcp] 未找到 .mcp/plan.md，拒绝提交。请先初始化计划。'); sys.exit(1)\n"
            "text = plan.read_text(encoding='utf-8')\n"
            "status = 'planned'\n"
            "current = ''\n"
            "for line in text.splitlines():\n"
            "    s=line.strip()\n"
            "    if s.startswith('- 状态:') or s.lower().startswith('- status:'): status = s.split(':',1)[1].strip().lower()\n"
            "    if s.startswith('- 当前步骤:') or s.lower().startswith('- current step:'): current = s.split(':',1)[1].strip()\n"
            "if sys.argv[1:] and sys.argv[1] == 'commit-msg':\n"
            "    if status != 'in_progress' or not current:\n"
            "        print('[mcp] 计划未处于 in_progress 或当前步骤为空，拒绝提交。'); sys.exit(1)\n"
            "    msg_file = pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else None\n"
            "    if msg_file and msg_file.exists():\n"
            "        msg = msg_file.read_text(encoding='utf-8')\n"
            "        token = '[step:' + current + ']'\n"
            "        if token not in msg:\n"
            "            print('[mcp] 提交消息需包含 ' + token + ' 标记以匹配当前步骤'); sys.exit(1)\n"
            "    sys.exit(0)\n"
            "sys.exit(0)\n"
        ),
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    # 按编译规则写入 Dockerfile 基线检查（如启用）
    compiled_policy = {}
    compiled_path = root / ".mcp/rules_compiled.json"
    if compiled_path.exists():
        try:
            compiled_policy = json.loads(compiled_path.read_text(encoding="utf-8")).get(
                "policy", {}
            )
        except Exception:
            compiled_policy = {}
    docker_gate_path = None
    if compiled_policy.get("container.policy.baseline"):
        docker_gate_path = root / ".mcp/dockerfile_gate.py"
        docker_gate_path.write_text(
            (
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import sys\n"
                "df = Path('Dockerfile')\n"
                "if not df.exists():\n"
                "    print('[mcp] Dockerfile missing (baseline check)'); sys.exit(1)\n"
                "text = df.read_text(encoding='utf-8', errors='ignore').lower()\n"
                "issues = []\n"
                "if 'user root' in text:\n"
                "    issues.append('Using USER root is not allowed')\n"
                "if 'from ' in text and ':latest' in text:\n"
                "    issues.append('Avoid using :latest tag')\n"
                "if issues:\n"
                "    print('[mcp] Dockerfile baseline violations:')\n"
                "    for i in issues: print(' -', i)\n"
                "    sys.exit(1)\n"
                "sys.exit(0)\n"
            ),
            encoding="utf-8",
        )
        docker_gate_path.chmod(docker_gate_path.stat().st_mode | stat.S_IEXEC)

    # 可用则安装 pre-commit 钩子
    if shutil.which("pre-commit"):
        try:
            subprocess.run(["pre-commit", "install"], cwd=root, check=False)
            subprocess.run(
                ["pre-commit", "install", "--hook-type", "commit-msg"],
                cwd=root,
                check=False,
            )
            subprocess.run(
                ["pre-commit", "install", "--hook-type", "pre-push"],
                cwd=root,
                check=False,
            )
        except Exception:
            pass

    out = {
        "pre_commit_config": str(pcfg),
        "pre_push": str(pre_push),
        "plan_gate": str(script_path),
    }
    if docker_gate_path:
        out["dockerfile_gate"] = str(docker_gate_path)
    return out


def generate_github_ci(project_root: Optional[Path] = None) -> Path:
    root = (project_root or Path.cwd()).resolve()
    yml = render_github_ci_yaml(root)
    wf_dir = root / ".github" / "workflows"
    _ensure_dir(wf_dir)
    path = wf_dir / "ci.yml"
    path.write_text(yml, encoding="utf-8")
    return path


def render_github_ci_yaml(project_root: Optional[Path] = None) -> str:
    root = (project_root or Path.cwd()).resolve()
    cfg = load_config(root)
    min_module = cfg["performance"]["on_push"]["coverage"]["min_module"]
    # 读取编译规则以决定可选步骤
    compiled_policy = {}
    compiled_path = root / ".mcp/rules_compiled.json"
    if compiled_path.exists():
        try:
            import json as _json

            compiled_policy = _json.loads(
                compiled_path.read_text(encoding="utf-8")
            ).get("policy", {})
        except Exception:
            compiled_policy = {}

    precommit_ci = ""
    if compiled_policy.get("security.secrets_scan"):
        precommit_ci = (
            "      - name: Pre-commit (all files)\n"
            "        run: |\n"
            "          python -m pip install pre-commit\n"
            "          pre-commit run --all-files || true\n"
        )
    docker_check = ""
    if compiled_policy.get("container.required"):
        docker_check = (
            "      - name: Check Dockerfile existence\n"
            "        run: |\n"
            "          test -f Dockerfile || (echo 'Dockerfile missing' && exit 1)\n"
        )
    hadolint_step = ""
    ci_cfg = cfg.get("ci", {}) if isinstance(cfg.get("ci", {}), dict) else {}
    if ci_cfg.get("hadolint", False) and (
        compiled_policy.get("container.required")
        or compiled_policy.get("container.policy.baseline")
    ):
        image = ci_cfg.get("hadolint_image", "hadolint/hadolint:latest")
        extra = ci_cfg.get("hadolint_args", "")
        hadolint_step = (
            "      - name: Dockerfile Lint (hadolint)\n"
            "        run: |\n"
            f"          test -f Dockerfile && docker run --rm -v \"$PWD\":/work -w /work {image} hadolint {extra} Dockerfile || echo 'skip hadolint'\n"
        )
    sast_step = ""
    if compiled_policy.get("security.sast_strict"):
        sast_step = (
            "      - name: SAST (semgrep)\n"
            "        run: |\n"
            "          python -m pip install semgrep\n"
            f"          semgrep --error --config {ci_cfg.get('semgrep_config','auto')}\n"
        )

    # Mutation testing (optional)
    mutation_step = ""
    perf_cfg = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    on_push_cfg = (
        perf_cfg.get("on_push", {})
        if isinstance(perf_cfg.get("on_push", {}), dict)
        else {}
    )
    if compiled_policy.get("test.mutation_required") or bool(
        on_push_cfg.get("mutation_test", False)
    ):
        mutation_step = (
            "      - name: Mutation testing\n"
            "        run: |\n"
            "          python -m pip install mutmut\n"
            "          mutmut run -q || true\n"
        )

    # VS Code 作业是否强制执行（不随文件存在性判断）
    require_vscode = bool((cfg.get("ci", {}) or {}).get("vscode_required", False))

    yml = f"""
name: CI
on:
  push:
  pull_request:
jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - name: Install tools
        run: |
          python -m pip install --upgrade pip
          pip install ruff black isort mypy bandit pytest pytest-cov types-PyYAML
{precommit_ci}{docker_check}{hadolint_step}      - name: Lint (ruff/black/isort)
        run: |
          ruff check --output-format=github mcp_rules_assistant
          black --check mcp_rules_assistant
          isort --check-only mcp_rules_assistant
      - name: Type Check (core, blocking)
        run: |
          mypy \
            mcp_rules_assistant/config.py \
            mcp_rules_assistant/progress.py \
            mcp_rules_assistant/tools.py \
            mcp_rules_assistant/memory.py \
            mcp_rules_assistant/mcp_server.py \
            mcp_rules_assistant/cli.py \
            mcp_rules_assistant/server.py
      - name: Type Check (rest, non-blocking)
        run: |
          mypy mcp_rules_assistant || true
      - name: Tests + Coverage
        env:
          PYTEST_DISABLE_PLUGIN_AUTOLOAD: "1"
        run: |
          pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing --cov-fail-under={int(min_module*100)} --junitxml=pytest-junit.xml
      - name: Coverage Policy Gate (core≥98%, others≥95%)
        run: |
          python -m mcp_rules_assistant.cli coverage-report --json > cov.json
          python - <<'PY'
          import json, sys
          data = json.load(open('cov.json'))
          weak = data.get('weak') or []
          if weak:
              print('[mcp] Coverage policy gate failed. Weak files:')
              for w in weak:
                  print(' -', w.get('file'), 'cov=', w.get('coverage'), '<', w.get('threshold'))
              sys.exit(1)
          print('[mcp] Coverage policy gate passed.')
          PY
      - name: Forbid skip/xfail markers (non-tests)
        run: |
          if grep -R -n --include='*.py' -E "(^|[^\"'])pytest\\.mark\\.(skip|xfail)" mcp_rules_assistant >/dev/null; then echo "Found actual skip/xfail usage in package code. Disallowed."; exit 1; fi
      - name: Coverage Near Summary
        run: |
          python -m mcp_rules_assistant.cli coverage-near --within 3 --top 10 > near.txt || true
          python -m mcp_rules_assistant.cli coverage-near --within 3 --top 10 --format csv --output near.csv || true
          python -m mcp_rules_assistant.cli coverage-near --within 3 --top 10 --format json --output near.json || true
          tar czf tests-artifacts.tar.gz coverage.xml pytest-junit.xml near.txt near.csv near.json || true
      - name: Upload coverage & JUnit
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: python-tests-${{{{ matrix.python-version }}}}
          path: |
            coverage.xml
            pytest-junit.xml
            near.txt
            near.csv
            near.json
            tests-artifacts.tar.gz
      - name: Security (bandit — high only)
        run: |
          bandit -q -lll -x tests -r .
{sast_step}{mutation_step}
  prepare:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - name: Prepare env (mcp_rules_assistant env.prepare)
        run: |
          python - <<'PY'
          from mcp_rules_assistant.mcp_server import JsonRpcServer
          srv = JsonRpcServer()
          out = srv._call_tool("env.prepare", {{"create": True, "install": True}})
          print(out)
          PY
      - name: Tests in env (pytest + coverage)
        env:
          PYTEST_DISABLE_PLUGIN_AUTOLOAD: "1"
        run: |
          . ./.mcp/venv/bin/activate
          pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing --junitxml=pytest-junit.xml
      - name: Upload artifacts (env tests)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: python-tests-prepare
          path: |
            coverage.xml
            pytest-junit.xml
  vscode:
    runs-on: ubuntu-latest
{'' if require_vscode else "    if: ${{{{ hashFiles('extensions/vscode/package.json') != '' }}}}"}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: 'extensions/vscode/package-lock.json'
      - name: Install and compile
        working-directory: extensions/vscode
        run: |
          npm ci || npm install
          npm run compile
      - name: VS Code extension tests
        working-directory: extensions/vscode
        run: |
          MCP_VSCODE_TEST_ARGS="" xvfb-run -a npm test 2>&1 | tee vscode-test.log
      - name: Upload VS Code test log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: vscode-tests
          path: extensions/vscode/vscode-test.log
""".lstrip()
    return yml


def autofix_github_ci(project_root: Optional[Path] = None) -> Dict[str, str | bool]:
    root = (project_root or Path.cwd()).resolve()
    desired = render_github_ci_yaml(root)
    wf_dir = root / ".github" / "workflows"
    _ensure_dir(wf_dir)
    path = wf_dir / "ci.yml"
    backup = None
    changed = True
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == desired:
            changed = False
        else:
            backup_path = wf_dir / "ci.yml.bak"
            backup_path.write_text(current, encoding="utf-8")
            backup = str(backup_path)
    if changed:
        path.write_text(desired, encoding="utf-8")
    return {"path": str(path), "changed": changed, "backup": backup or ""}
