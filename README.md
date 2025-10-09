# MCP Rules & Context Assistant

<div align="center">

![CI](https://img.shields.io/github/actions/workflow/status/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/ci.yml?branch=main&label=CI)
![Coverage](https://codecov.io/gh/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/branch/main/graph/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyPI](https://img.shields.io/pypi/v/mcp-rules-assistant?label=pypi)

## Bilingual AI-Assisted Development Toolchain

中英双语 AI 辅助开发工具链

[English](#english) | [中文](#中文)

</div>

---

## 中文

### 项目简介

MCP Rules & Context Assistant 是一款**完全开源（MIT License）**的 AI 辅助开发工具，专为大型项目设计。它通过**规则治理 + 上下文记忆**，帮助团队在多轮 AI 协作中保持代码一致性与高质量交付。

### 核心特性

- **🚀 一键安装** - 跨平台支持（Linux/macOS/Windows），零配置启动
- **📋 智能规则摄取** - 自动从文档提取编码规范，生成可执行门禁
- **🧠 上下文记忆** - 20轮滚动记忆，支持 VS Code/Cursor/Windsurf 等 IDE
- **✅ 质量守门员** - 内置覆盖率策略（核心≥98%，其他≥95%），CI/CD 自动生成
- **🌍 双语支持** - CLI 与 MCP 接口均支持中英文模糊语义
- **🔒 隐私优先** - 无遥测，所有数据本地存储

### 快速开始

#### 方式1：一键安装（推荐）

```bash
# Linux / macOS
git clone https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool.git
cd Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool
bash install.sh
```

```bat
REM Windows
git clone https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool.git
cd Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool
install.bat
```

#### 方式2：PyPI 安装

```bash
pip install mcp-rules-assistant
mcp-rules-assistant init
```

#### 方式3：从源码安装

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
mcp-rules-assistant install-hooks
```

### 基本用法

```bash
# 初始化配置
mcp-rules-assistant init

# 摄取项目规则
mcp-rules-assistant ingest-rules README.md docs/

# 生成 CI 配置
mcp-rules-assistant generate-ci

# 查看覆盖率报告
mcp-rules-assistant coverage-report --json

# 检查项目健康度
mcp-rules-assistant diagnose
```

### 适用场景

- **AI 结对编程** - 在多轮 AI 协作中同步项目规范与上下文
- **质量守门** - 对高准入项目执行严格的覆盖率与安全扫描
- **多 IDE 团队** - VS Code、Cursor、Windsurf、JetBrains 混合团队统一规则
- **合规项目** - 通过结构化仪表盘证明操作留痕与覆盖率达标

### 文档

- [开发指南](DEVELOPMENT.md)
- [贡献指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)
- [架构设计](docs/ARCHITECTURE.md)
- [使用手册](docs/USAGE.md)

### 参与贡献

我们欢迎所有形式的贡献！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交变更 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

### 社区支持

- **GitHub Issues** - 报告 Bug 或提出功能请求
- **GitHub Discussions** - 提问与讨论
- **参与贡献** - 查看 [待办事项](https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/issues)

---

## English

### Overview

MCP Rules & Context Assistant is a **fully open-source (MIT License)** AI-assisted development tool designed for large-scale projects. It maintains code consistency and high-quality delivery through **rule governance + context memory**.

### Key Features

- **🚀 One-Click Install** - Cross-platform (Linux/macOS/Windows), zero-config startup
- **📋 Smart Rule Ingestion** - Auto-extract coding standards from docs, generate enforceable gates
- **🧠 Context Memory** - 20-turn rolling memory, supports VS Code/Cursor/Windsurf IDEs
- **✅ Quality Gatekeeper** - Built-in coverage policy (core≥98%, others≥95%), auto-generate CI/CD
- **🌍 Bilingual** - CLI & MCP interface support English/Chinese fuzzy semantics
- **🔒 Privacy First** - No telemetry, all data stored locally

### Quick Start

#### Option 1: One-Click Install (Recommended)

```bash
# Linux / macOS
git clone https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool.git
cd Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool
bash install.sh
```

```bat
REM Windows
git clone https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool.git
cd Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool
install.bat
```

#### Option 2: PyPI Install

```bash
pip install mcp-rules-assistant
mcp-rules-assistant init
```

#### Option 3: From Source

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
mcp-rules-assistant install-hooks
```

### Basic Usage

```bash
# Initialize configuration
mcp-rules-assistant init

# Ingest project rules
mcp-rules-assistant ingest-rules README.md docs/

# Generate CI configuration
mcp-rules-assistant generate-ci

# View coverage report
mcp-rules-assistant coverage-report --json

# Check project health
mcp-rules-assistant diagnose
```

### Use Cases

- **AI Pair Programming** - Sync project standards & context across multiple AI sessions
- **Quality Gatekeeper** - Enforce strict coverage & security scanning for critical projects
- **Multi-IDE Teams** - Unified rules for VS Code, Cursor, Windsurf, JetBrains teams
- **Compliance Projects** - Prove audit trails & coverage via structured dashboards

### Documentation

- [Development Guide](DEVELOPMENT.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Architecture Design](docs/ARCHITECTURE.md)
- [User Manual](docs/USAGE.md)

### Contributing

We welcome all contributions!

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### Community Support

- **GitHub Issues** - Report bugs or request features
- **GitHub Discussions** - Ask questions & discuss
- **Contribute** - Check [open issues](https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/issues)

---

## 📋 System Requirements

- **Python**: 3.10+ (3.13 recommended)
- **OS**: Linux, macOS, Windows (Git Bash)
- **Git**: 2.x+
- **Node.js**: 18+ (for VS Code extension development)

## 🏗 Architecture

```
mcp-rules-assistant/
├── mcp_rules_assistant/      # Python backend (CLI + MCP Server)
├── extensions/                # IDE extensions
│   ├── vscode/               # VS Code / Cursor / Windsurf
│   └── jetbrains/            # JetBrains IDEs
├── rulesets/                  # Predefined rule templates
├── tests/                     # Comprehensive test suite
└── docs/                      # Documentation
```

## 🧪 Quality Gates

- **Linting**: Ruff, Black, isort
- **Type Checking**: Mypy (strict mode)
- **Testing**: Pytest (≥98% core coverage, ≥95% others)
- **Security**: Bandit, Semgrep, Hadolint
- **Secrets**: detect-secrets

Run all gates:
```bash
make ci
```

## 📦 Release & Versioning

- **Versioning**: Semantic Versioning (SemVer)
- **Changelog**: See [CHANGELOG.md](CHANGELOG.md)
- **Releases**: See [GitHub Releases](https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/releases)

Current Version: **0.3.2** (OSS Edition)

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Model Context Protocol (MCP)](https://github.com/anthropics/mcp)
- Inspired by the AI-assisted development community
- Thanks to all contributors!

## 📞 Contact

- **Project Homepage**: [GitHub Repository](https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool)
- **Issues**: [GitHub Issues](https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/discussions)

---

<div align="center">

Made with ❤️ by the RuleFlow Team

⭐ **Star us on GitHub if you find this helpful!** ⭐

</div>
