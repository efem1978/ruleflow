PYTHON ?= python3
NPM ?= npm

.PHONY: setup test lint type format ci vscode-test ingest coverage package release-check clean-dist help

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
