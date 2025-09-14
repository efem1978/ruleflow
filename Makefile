PYTHON ?= python3
# Prefer project venv python if present
ifneq (,$(wildcard .mcp/venv/bin/python))
  PYTHON := .mcp/venv/bin/python
endif
NPM ?= npm

.PHONY: setup test lint type format ci vscode-test ingest coverage package release-check clean-dist clean help local-ci-run hooks hooks-sh ci-autofix preflight nightly-local maintenance-all verify jb-storyboard

help:
	@echo "Targets: setup test lint type format ci vscode-test ingest coverage"

setup:
	$(PYTHON) -m mcp_rules_assistant.cli prepare-env --install || true

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff --format=github . || true
	$(PYTHON) -m black --check . || true
	$(PYTHON) -m isort --check-only . || true

type:
	$(PYTHON) -m mypy . || true

format:
	$(PYTHON) -m black . || true
	$(PYTHON) -m isort . || true

ci:
	$(PYTHON) -m mcp_rules_assistant.cli generate-ci
	$(PYTHON) -m mcp_rules_assistant.cli ci-validate

local-ci-run:
	@echo "[local-ci] Lint"
	$(PYTHON) -m ruff check --output-format=github mcp_rules_assistant
	$(PYTHON) -m black --check mcp_rules_assistant
	$(PYTHON) -m isort --check-only mcp_rules_assistant
	@echo "[local-ci] Type (core blocking)"
	$(PYTHON) -m mypy \
	  mcp_rules_assistant/config.py \
	  mcp_rules_assistant/progress.py \
	  mcp_rules_assistant/tools.py \
	  mcp_rules_assistant/memory.py \
	  mcp_rules_assistant/mcp_server.py \
	  mcp_rules_assistant/cli.py \
	  mcp_rules_assistant/server.py
	@echo "[local-ci] Type (rest non-blocking)"
	$(PYTHON) -m mypy mcp_rules_assistant || true
	@echo "[local-ci] Tests + Coverage"
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing --junitxml=pytest-junit.xml
	@echo "[local-ci] Coverage Policy Gate"
	$(PYTHON) -m mcp_rules_assistant.cli coverage-report --json > cov.json
	$(PYTHON) -c "import json,sys; d=json.load(open('cov.json')); w=d.get('weak') or []; print('[mcp] Coverage policy gate failed. Weak files:') or [print(' -',x.get('file'),'cov=',x.get('coverage'),'<',x.get('threshold')) for x in w] or sys.exit(1) if w else print('[mcp] Coverage policy gate passed.')"

hooks:
	$(PYTHON) -m mcp_rules_assistant.cli install-hooks

hooks-sh:
	sh scripts/install-hooks.sh

ci-autofix:
	$(PYTHON) -m mcp_rules_assistant.cli ci-autofix

preflight:
	sh scripts/preflight.sh

nightly-local:
	$(MAKE) preflight
	$(MAKE) local-ci-run
	$(NPM) --prefix extensions/vscode run compile || true
	MCP_VSCODE_TEST_ARGS="" xvfb-run -a $(NPM) --prefix extensions/vscode test || true

maintenance-all:
	sh scripts/maintenance-all.sh

verify:
	bash scripts/verify-all.sh

.PHONY: release-harden-verify
release-harden-verify:
	sh scripts/release-harden-verify.sh

.PHONY: release-simulate
release-simulate:
	sh scripts/release-simulate.sh

.PHONY: release-note
release-note:
	python3 scripts/release-note-from-report.py --report .mcp/dashboard/release_check.md --out .mcp/dashboard/release_note_snippet.md

.PHONY: release-note-full pre-release market-release
release-note-full:
	python3 scripts/release-note-from-report.py --report .mcp/dashboard/release_check.md --out .mcp/dashboard/release_note_snippet.md
	python3 scripts/release-changes-from-git.py

pre-release:
	sh scripts/pre-release-check.sh

market-release:
	sh scripts/release-compose-marketplace.sh

.PHONY: git-upstream-check
git-upstream-check:
	sh scripts/git-upstream-check.sh

# 发布/开发许可门禁快捷开关（不推远端）
release-harden-on:
	$(PYTHON) -m mcp_rules_assistant.cli license-require-on
	@echo "license.required=true 已写入 .mcp/assistant.yaml；CI 将附加 cryptography 依赖。"

release-harden-off:
	$(PYTHON) -m mcp_rules_assistant.cli license-require-off
	@echo "license.required=false 已写入 .mcp/assistant.yaml（开发模式）。"

# 已移除前端看板相关目标（dashboard-*）

vscode-test:
	$(NPM) --prefix extensions/vscode run compile
	$(NPM) --prefix extensions/vscode test

ingest:
	$(PYTHON) -m mcp_rules_assistant.cli ingest-rules README.md docs/

coverage:
	$(PYTHON) -m mcp_rules_assistant.cli coverage
	$(PYTHON) -m mcp_rules_assistant.cli coverage-groups
	$(PYTHON) -m mcp_rules_assistant.cli coverage-near --within 3 --top 20

package:
	$(PYTHON) -m pip install --upgrade build twine || true
	$(PYTHON) -m build
	@echo "Artifacts in dist/. Upload with: twine upload dist/*"

distcheck:
	$(PYTHON) -m pip install --upgrade build twine || true
	$(PYTHON) -m build
	$(PYTHON) -m twine check dist/*
	@echo "[distcheck] wheel/sdist build + twine check passed"

release-check:
	$(PYTHON) -m pip install --upgrade twine || true
	$(PYTHON) -m twine check dist/*

clean-dist:
	rm -rf dist build *.egg-info || true
clean:
	rm -f coverage.xml cov*.json pytest-junit.xml || true
	rm -rf extensions/vscode/coverage extensions/vscode/out || true
	rm -f extensions/vscode/*.vsix || true
	# 清理本地样例/临时工件（未追踪但建议移除）
	rm -f bad.py ok2.py ok.txt docs/b.txt docs/link.py || true
	# 清理误留的样例包目录
	rm -rf pkg_x || true
jb-storyboard:
	sh scripts/jb-storyboard.sh
ide-compat:
	sh scripts/ide-compat-check.sh || true
	@echo "See extensions/compat_report.json"
preflight-quick:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -q tests/docs/test_docs_anchors.py
	$(PYTHON) -c "from pathlib import Path; text=Path('README.md').read_text(encoding='utf-8'); print('[quick] README length =', len(text))"

# ---------------- Docker helpers ----------------
.PHONY: docker-verify docker-dev-agent-once docker-jb build-vscode-test docker-vscode-test docker-batch

docker-verify:
	docker compose run --rm verify

docker-dev-agent-once:
	docker compose run --rm dev-agent-once

docker-jb:
	docker compose run --rm jb-package || true
	docker compose run --rm jb-ui-smoke || true

build-vscode-test:
	docker compose build vscode-test

docker-vscode-test:
	sh scripts/vscode-test-once.sh || true

.PHONY: jb-verify vscode-test-smoke
jb-verify:
	bash scripts/jb-ui-verify.sh

vscode-test-smoke:
	$(MAKE) docker-vscode-test

docker-batch:
	@echo "[docker-batch] verify"
	$(MAKE) docker-verify || true
	@echo "[docker-batch] dev-agent-once"
	$(MAKE) docker-dev-agent-once || true
	@echo "[docker-batch] jetbrains"
	$(MAKE) docker-jb || true
	@echo "[docker-batch] vscode-test"
	$(MAKE) build-vscode-test docker-vscode-test || true
	@echo "[docker-batch] done"
