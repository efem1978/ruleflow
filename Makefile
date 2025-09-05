PYTHON ?= python3
NPM ?= npm

.PHONY: setup test lint type format ci vscode-test ingest coverage package release-check clean-dist help local-ci-run hooks hooks-sh ci-autofix preflight

help:
	@echo "Targets: setup test lint type format ci vscode-test ingest coverage"

setup:
	$(PYTHON) -m mcp_rules_assistant.cli prepare-env --install || true

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -q

lint:
	ruff --format=github . || true
	black --check . || true
	isort --check-only . || true

type:
	mypy . || true

format:
	black . || true
	isort . || true

ci:
	$(PYTHON) -m mcp_rules_assistant.cli generate-ci
	$(PYTHON) -m mcp_rules_assistant.cli ci-validate

local-ci-run:
	@echo "[local-ci] Lint"
	ruff check --output-format=github mcp_rules_assistant || true
	black --check mcp_rules_assistant || true
	isort --check-only mcp_rules_assistant || true
	@echo "[local-ci] Type (core blocking)"
	mypy \
	  mcp_rules_assistant/config.py \
	  mcp_rules_assistant/progress.py \
	  mcp_rules_assistant/tools.py \
	  mcp_rules_assistant/memory.py \
	  mcp_rules_assistant/mcp_server.py \
	  mcp_rules_assistant/cli.py \
	  mcp_rules_assistant/server.py
	@echo "[local-ci] Type (rest non-blocking)"
	mypy mcp_rules_assistant || true
	@echo "[local-ci] Tests + Coverage"
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing --junitxml=pytest-junit.xml
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

release-check:
	$(PYTHON) -m pip install --upgrade twine || true
	$(PYTHON) -m twine check dist/*

clean-dist:
	rm -rf dist build *.egg-info || true
