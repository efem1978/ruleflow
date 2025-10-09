# Contributing to MCP Rules & Context Assistant

Thank you for your interest in contributing! This project is **open source (MIT License)** and we welcome contributions from everyone.

## Quick Start

### 1. Setup Development Environment

```bash
# Clone repository
git clone https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool.git
cd Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool

# One-click setup
bash install.sh

# Or manual setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
mcp-rules-assistant install-hooks
```

### 2. Development Workflow

```bash
# Run quality gates
make ci                          # Full CI checks (recommended before push)
make test                        # Run tests
make lint                        # Linting only

# Or individual tools
ruff check .                     # Linting
mypy mcp_rules_assistant/        # Type checking
pytest -q                        # Tests
```

### 3. Make Changes

1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Make your changes
3. Add tests for new functionality
4. Ensure all quality gates pass: `make ci`
5. Commit with conventional commits format

### 4. Commit Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: <type>(<scope>): <description>
git commit -m "feat(cli): add new command for rule export"
git commit -m "fix(server): resolve memory leak in context manager"
git commit -m "docs: update installation guide"
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Quality Requirements

- **Coverage**: Core modules ≥98%, others ≥95%
- **Type Safety**: Mypy strict mode, zero warnings
- **Linting**: Ruff + Black, all checks pass
- **Tests**: All tests pass, no skipped tests in package code
- **Security**: Bandit + Semgrep, no high-severity issues

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_cli.py

# Run with coverage
pytest --cov=mcp_rules_assistant --cov-report=html
```

## Documentation

- Update relevant docs when changing functionality
- Add docstrings for public APIs
- Update CHANGELOG.md for notable changes

## Reporting Bugs

Include:
1. OS and Python version
2. Steps to reproduce
3. Expected vs actual behavior
4. Error messages / logs

## Feature Requests

1. Check existing issues first
2. Describe the problem clearly
3. Propose your solution
4. Provide use cases

## Security Issues

Report security vulnerabilities to **support@ruleflow.app**. See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You

Your contributions make this project better for everyone!

---

For more details, see:
- [README.md](README.md) - Project overview
- [DEVELOPMENT.md](DEVELOPMENT.md) - Detailed development guide
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) - Community guidelines
