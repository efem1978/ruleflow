Contributing Guide (Local)

Thanks for contributing! This repository favors a fast inner dev loop with strict push/CI gates. Follow the steps below to get productive quickly.

Quick Start
- Python: Use the project venv. Run: `make setup` or `python3 -m mcp_rules_assistant.cli prepare-env --install`
- Install package (editable): `python3 -m pip install -e .`
- Initialize config: `python3 -m mcp_rules_assistant.cli init`
- VS Code extension: install `extensions/vscode/mcp-rules-assistant.vsix` (optional)

Everyday Workflow
- Run all local checks: `make local-ci-run`
  - Lint: ruff/black/isort
  - Type (blocking core): mypy on core modules
  - Tests + Coverage: pytest (+ coverage gate via policy)
- Fast rule ingestion (optional):
  - `python3 -m mcp_rules_assistant.cli ingest-rules README.md docs/`
  - `python3 -m mcp_rules_assistant.cli rules-explain --json`

Do not commit generated artifacts
- Coverage/test artifacts: `coverage.xml`, `.coverage*`, `cov*.json`, `pytest-junit.xml`
- VS Code extension outputs: `extensions/vscode/out/`, `extensions/vscode/coverage/`, `*.vsix`
- Build outputs: `dist/`, `build/`, `*.egg-info/`
(The repo `.gitignore` and `scripts/preflight.sh` help prevent accidental commits.)

Commit & Push Gates
- Pre-commit hooks are installed via: `python3 -m mcp_rules_assistant.cli install-hooks`
- Commit requirements:
  - Ensure `.mcp/plan.md` status is `in_progress` and commit message contains `[step:<current-step>]`
  - TDD gate: commits changing `.py` sources must include corresponding `tests/` changes
- Push runs coverage/test/sast gates; keep coverage above the configured thresholds in `.mcp/assistant.yaml`.

MCP Server & VS Code
- Start server (stdio JSON-RPC): `python3 -m mcp_rules_assistant.cli start`
- Copilot MCP integration is preconfigured in `.vscode/settings.json` (tool id: `ruleflow`).

CI Notes
- GitHub Actions workflow: `.github/workflows/ci.yml`
  - Python matrix 3.10/3.11/3.12, parallelized with `pytest-xdist`
  - Caching: `actions/setup-python` pip cache and venv cache for the `prepare` job
  - Coverage artifacts uploaded; Codecov upload is enabled if `CODECOV_TOKEN` is set

Style & Conventions
- Keep code minimal and focused; follow existing patterns.
- Formatting: black; Import order: isort; Lint: ruff
- Type hints: prefer precise types on public boundaries; core modules are type-checked strictly

Troubleshooting
- Missing tools? Run `make setup` again to (re)install into `.mcp/venv`.
- Coverage gate failed? Improve tests near threshold files (see `python3 -m mcp_rules_assistant.cli coverage-near --within 3 --top 20`).

Local install & revert (no publish)
- Editable install: `pip install -e .`; verify with `mcp-rules-assistant version`
- Build + wheel install:
  - `python -m build && pip install dist/mcp_rules_assistant-<ver>-py3-none-any.whl`
  - Verify: `mcp-rules-assistant status-update --json`
  - Revert: `pip uninstall -y mcp-rules-assistant`

More docs in `docs/CONTRIBUTING.md`, `README.md`, and `DEVELOPMENT.md`.
