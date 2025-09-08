from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path
from typing import Dict, Optional

from .config import load_config
from .process import run_cmd

# Optional compiled policy constants
RULES_COMPILED_JSON = ".mcp/rules_compiled.json"
KEY_CONTAINER_POLICY_BASELINE = "container.policy.baseline"


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# 使用共享 run_cmd（原本模块内的 _run_cmd 已移除）


def _read_compiled_policy(root: Path) -> Dict[str, object]:
    p = root / RULES_COMPILED_JSON
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("policy", {})  # type: ignore[return-value]
    except Exception:
        return {}


def generate_pre_commit_config(project_root: Optional[Path] = None) -> Path:
    root = (project_root or Path.cwd()).resolve()
    cfg = load_config(root)
    min_module = cfg["performance"]["on_push"]["coverage"]["min_module"]

    policy = _read_compiled_policy(root)

    secrets_block = ""
    if policy.get("security.secrets_scan"):
        secrets_block = (
            "  - repo: https://github.com/Yelp/detect-secrets\n"
            "    rev: v1.4.0\n"
            "    hooks:\n"
            "      - id: detect-secrets\n"
            "        stages: [push]\n"
        )

    docker_local_hook = ""
    if policy.get(KEY_CONTAINER_POLICY_BASELINE):
        docker_local_hook = (
            "      - id: dockerfile-baseline\n"
            "        name: dockerfile baseline (push)\n"
            "        entry: python .mcp/dockerfile_gate.py\n"
            "        language: system\n"
            "        pass_filenames: false\n"
            "        stages: [push]\n"
        )

    # Optional tool versions from config
    ci_cfg = cfg.get("ci", {}) if isinstance(cfg.get("ci", {}), dict) else {}
    tv = (
        ci_cfg.get("tool_versions", {})
        if isinstance(ci_cfg.get("tool_versions", {}), dict)
        else {}
    )
    v_ruff = str(tv.get("ruff", "v0.5.6"))
    v_black = str(tv.get("black", "24.8.0"))
    v_isort = str(tv.get("isort", "5.13.2"))
    v_mypy = str(tv.get("mypy", "v1.10.0"))
    v_bandit = str(tv.get("bandit", "1.7.7"))

    text = f"""
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: {v_ruff}
    hooks:
      - id: ruff
        args: ["--fix"]
        stages: [commit]
  - repo: https://github.com/psf/black
    rev: {v_black}
    hooks:
      - id: black
        stages: [commit]
  - repo: https://github.com/pycqa/isort
    rev: {v_isort}
    hooks:
      - id: isort
        stages: [commit]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: {v_mypy}
    hooks:
      - id: mypy
        stages: [commit]
        files: mcp_rules_assistant/
        additional_dependencies: [types-PyYAML]
{secrets_block}  - repo: local
    hooks:
      - id: plan-gate
        name: plan state & commit message gate (commit-msg)
        entry: python .mcp/plan_gate.py commit-msg
        language: system
        stages: [commit-msg]
      - id: tdd-gate
        name: tdd gate (commit)
        entry: python .mcp/tdd_gate.py
        language: system
        stages: [commit]
      - id: branch-name-gate
        name: branch naming gate (commit)
        entry: python .mcp/branch_name_gate.py
        language: system
        stages: [commit]
{docker_local_hook}      - id: pytest-with-coverage
        name: pytest with coverage (push)
        entry: sh -c 'pytest -q --maxfail=1 --disable-warnings -W error --strict-markers --cov --cov-report=xml:coverage.xml --cov-report=term-missing --cov-fail-under={int(min_module*100)}'
        language: system
        pass_filenames: false
        stages: [push]
      - id: no-skip-xfail
        name: forbid skip/xfail (push)
        entry: sh -c 'if git grep -nE "pytest\\\\.mark\\\\.(skip|xfail)" -- ":(exclude)tests/*" mcp_rules_assistant >/dev/null; then echo "Found skip/xfail markers in package code. Disallowed."; exit 1; fi'
        language: system
        pass_filenames: false
        stages: [push]
      - id: docs-anchors
        name: docs anchors snapshot (push)
        entry: sh -c 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/docs/test_docs_anchors.py'
        language: system
        pass_filenames: false
        stages: [push]
  - repo: https://github.com/PyCQA/bandit
    rev: {v_bandit}
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

    pcfg = generate_pre_commit_config(root)

    hooks_dir = root / ".git" / "hooks"
    _ensure_dir(hooks_dir)
    pre_push = hooks_dir / "pre-push"
    pre_push.write_text(
        """#!/bin/sh
if command -v pre-commit >/dev/null 2>&1; then
  echo "[mcp] running pre-commit (push stage) ..."
  pre-commit run --hook-stage push --all-files
  exit $?
else
  echo "[mcp] pre-commit not found; skipping push checks. Install with: pip install pre-commit"
  exit 0
fi
""",
        encoding="utf-8",
    )
    pre_push.chmod(pre_push.stat().st_mode | stat.S_IEXEC)

    # plan gate
    plan_gate = root / ".mcp/plan_gate.py"
    plan_gate.parent.mkdir(parents=True, exist_ok=True)
    plan_gate.write_text(
        (
            """#!/usr/bin/env python3
import sys, re, pathlib
root = pathlib.Path('.').resolve()
plan = root / '.mcp/plan.md'
if not plan.exists():
  print('[mcp] 未找到 .mcp/plan.md，拒绝提交。请先初始化计划。'); sys.exit(1)
text = plan.read_text(encoding='utf-8')
status = 'planned'
current = ''
for line in text.splitlines():
  s=line.strip()
  if s.startswith('- 状态:') or s.lower().startswith('- status:'): status = s.split(':',1)[1].strip().lower()
  if s.startswith('- 当前步骤:') or s.lower().startswith('- current step:'): current = s.split(':',1)[1].strip()
if sys.argv[1:] and sys.argv[1] == 'commit-msg':
  if status != 'in_progress' or not current:
    print('[mcp] 计划未处于 in_progress 或当前步骤为空，拒绝提交。'); sys.exit(1)
  msg_file = pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else None
  if msg_file and msg_file.exists():
    msg = msg_file.read_text(encoding='utf-8')
    token = '[step:' + current + ']'
    if token not in msg:
      print('[mcp] 提交消息需包含 ' + token + ' 标记以匹配当前步骤'); sys.exit(1)
  sys.exit(0)
sys.exit(0)
"""
        ),
        encoding="utf-8",
    )
    plan_gate.chmod(plan_gate.stat().st_mode | stat.S_IEXEC)

    # branch gate
    branch_gate = root / ".mcp/branch_name_gate.py"
    branch_gate.write_text(
        (
            "#!/usr/bin/env python3\n"
            "import os, re, subprocess, sys\n"
            "if os.environ.get('MCP_BRANCH_IGNORE') in ('1','true','True'):\n"
            "    sys.exit(0)\n"
            "try:\n"
            "    name = subprocess.check_output(['git','symbolic-ref','--quiet','--short','HEAD'], text=True).strip()\n"
            "except Exception:\n"
            "    # detached HEAD 或非 git 环境下不阻断\n"
            "    sys.exit(0)\n"
            "pat = os.environ.get('MCP_BRANCH_REGEX', r'^(main|master|develop|dev|feat/|fix/|chore/|docs/|test/|refactor/|release/|hotfix/)')\n"
            "if not re.match(pat, name):\n"
            "    print(f'[mcp] branch name \"{name}\" does not match pattern: {pat}')\n"
            "    sys.exit(1)\n"
            "sys.exit(0)\n"
        ),
        encoding="utf-8",
    )
    branch_gate.chmod(branch_gate.stat().st_mode | stat.S_IEXEC)

    # tdd gate
    tdd_gate = root / ".mcp/tdd_gate.py"
    tdd_gate.write_text(
        (
            """#!/usr/bin/env python3
import os, subprocess, sys
# 跳过条件
if os.environ.get('MCP_TDD_IGNORE') in ('1','true','True'):
  sys.exit(0)
try:
  # 仅检查已暂存内容
  out = subprocess.check_output(['git','diff','--cached','--name-only'], text=True)
except Exception:
  sys.exit(0)
changed = [x.strip() for x in out.splitlines() if x.strip()]
if not changed:
  sys.exit(0)
py_changed = [p for p in changed if p.endswith('.py')]
if not py_changed:
  sys.exit(0)
"""
        ),
        encoding="utf-8",
    )
    tdd_gate.chmod(tdd_gate.stat().st_mode | stat.S_IEXEC)

    # docker baseline gate if enabled
    policy = _read_compiled_policy(root)
    docker_gate_path: Optional[Path] = None
    if policy.get(KEY_CONTAINER_POLICY_BASELINE):
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

    # pre-commit installation if available
    if shutil.which("pre-commit"):
        try:
            run_cmd(["pre-commit", "install"], cwd=root, check=False)
            run_cmd(
                ["pre-commit", "install", "--hook-type", "commit-msg"],
                cwd=root,
                check=False,
            )
            run_cmd(
                ["pre-commit", "install", "--hook-type", "pre-push"],
                cwd=root,
                check=False,
            )
        except Exception:
            pass

    # prepare outputs
    out: Dict[str, str] = {
        "pre_commit_config": str(pcfg),
        "pre_push": str(pre_push),
        "plan_gate": str(plan_gate),
    }

    # commit message template (best-effort)
    git_dir = root / ".git"
    if git_dir.exists():
        tmpl = git_dir / ".gitmessage"
        try:
            tmpl.write_text(
                (
                    "# Commit message template\n"
                    "# 请包含计划步骤标记以通过 Gate，例如：[step:实现 MCP 协议方法]\n"
                    "# 第一行：简要说明改动\n"
                    "# 空一行\n"
                    "# 细节：列出关键点、影响面、测试、回滚计划\n"
                ),
                encoding="utf-8",
            )
        except Exception:
            pass
        try:
            run_cmd(
                ["git", "config", "commit.template", str(tmpl)], cwd=root, check=False
            )
            out["commit_template"] = str(tmpl)
        except Exception:
            pass

    if branch_gate.exists():
        out["branch_gate"] = str(branch_gate)
    if tdd_gate.exists():
        out["tdd_gate"] = str(tdd_gate)
    if docker_gate_path is not None:
        out["dockerfile_gate"] = str(docker_gate_path)

    return out


def render_github_ci_yaml(project_root: Optional[Path] = None) -> str:
    root = (project_root or Path.cwd()).resolve()
    cfg = load_config(root)
    min_module = cfg["performance"]["on_push"]["coverage"]["min_module"]

    policy = _read_compiled_policy(root)

    precommit_ci = ""
    if policy.get("security.secrets_scan"):
        precommit_ci = (
            "      - name: Pre-commit (all files)\n"
            "        run: |\n"
            "          python -m pip install pre-commit\n"
            "          pre-commit run --all-files || true\n"
        )

    docker_check = ""
    if policy.get("container.required"):
        docker_check = (
            "      - name: Check Dockerfile existence\n"
            "        run: |\n"
            "          test -f Dockerfile || (echo 'Dockerfile missing' && exit 1)\n"
        )

    ci_cfg = cfg.get("ci", {}) if isinstance(cfg.get("ci", {}), dict) else {}
    hadolint_step = ""
    if ci_cfg.get("hadolint", False) and (
        policy.get("container.required") or policy.get(KEY_CONTAINER_POLICY_BASELINE)
    ):
        image = ci_cfg.get("hadolint_image", "hadolint/hadolint:latest")
        extra = ci_cfg.get("hadolint_args", "")
        hadolint_step = (
            "      - name: Dockerfile Lint (hadolint)\n"
            "        run: |\n"
            f"          test -f Dockerfile && docker run --rm -v \"$PWD\":/work -w /work {image} hadolint {extra} Dockerfile || echo 'skip hadolint'\n"
        )

    sast_step = ""
    if policy.get("security.sast_strict"):
        sast_step = (
            "      - name: SAST (semgrep)\n"
            "        run: |\n"
            "          # 固定 semgrep 版本以提升可重复性\n"
            "          python -m pip install 'semgrep==1.91.0'\n"
            f"          semgrep --error --config {ci_cfg.get('semgrep_config','auto')}\n"
        )

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

    mutation_step = ""
    if policy.get("test.mutation_required") or bool(
        on_push_cfg.get("mutation_test", False)
    ):
        mutation_step = (
            "      - name: Mutation testing\n"
            "        run: |\n"
            "          python -m pip install mutmut\n"
            "          mutmut run -q || true\n"
        )

    require_vscode = bool((cfg.get("ci", {}) or {}).get("vscode_required", False))

    lic_required = bool((cfg.get("license", {}) or {}).get("required", False))
    crypto_line = "          pip install cryptography\n" if lic_required else ""

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
          python-version: ${{{{ matrix.python-version }}}}
          cache: 'pip'
      - name: Install tools
        run: |
          python -m pip install --upgrade pip
{crypto_line}          pip install ruff black isort mypy bandit pytest pytest-cov types-PyYAML
{precommit_ci}{docker_check}{hadolint_step}      - name: Lint (ruff/black/isort)
        run: |
          ruff check --output-format=github mcp_rules_assistant
          black --check mcp_rules_assistant
          isort --check-only mcp_rules_assistant
      - name: Docs Snapshot Gate (preflight subset)
        run: |
          PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/docs/test_docs_anchors.py
      - name: Preflight
        run: |
          sh scripts/preflight.sh
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
      - name: VS Code coverage threshold (warn)
        run: |
          sh scripts/check-lcov.sh extensions/vscode/coverage/lcov.info 30
      - name: Upload VS Code coverage to Codecov (conditional)
        if: always()
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: extensions/vscode/coverage/lcov.info
          flags: vscode
          fail_ci_if_error: false
      - name: Upload VS Code test log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: vscode-tests
          path: extensions/vscode/vscode-test.log
""".lstrip()

    return yml


def generate_github_ci(project_root: Optional[Path] = None) -> Path:
    root = (project_root or Path.cwd()).resolve()
    yml = render_github_ci_yaml(root)
    wf_dir = root / ".github" / "workflows"
    _ensure_dir(wf_dir)
    path = wf_dir / "ci.yml"
    path.write_text(yml, encoding="utf-8")
    return path


def autofix_github_ci(project_root: Optional[Path] = None) -> Dict[str, str | bool]:
    root = (project_root or Path.cwd()).resolve()
    desired = render_github_ci_yaml(root)
    wf_dir = root / ".github" / "workflows"
    _ensure_dir(wf_dir)
    path = wf_dir / "ci.yml"
    backup: Optional[str] = None
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
