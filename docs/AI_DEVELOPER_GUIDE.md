# AI 开发者指南 / AI Developer Guide

本指南面向贡献者与 AI 助手，统一工程约定、性能策略、门禁与提交流程，帮助在本仓库中高效、安全地落地改动。

## 一览
- 架构与模块：MCP Server（Python）+ VS Code 扩展（TypeScript）+ CLI/CI/Hooks
- 性能模式：Fast（默认）/Standard/Strict，保存轻、推送与 CI 重
- 规则与门禁：规则摄取/编译→配置/CI/Hooks 同步→覆盖率与安全门禁
- 测试与覆盖率：核心模块≥98%，其余≥95%，严禁警告/跳过（CI）
- 开发流程：TDD→实现→重构；提交与推送进入分层门禁

## 仓库结构（关键路径）
- `mcp_rules_assistant/`：核心包
  - `mcp_server.py`：JSON-RPC/stdio 服务（MCP 风格 methods/resources）
  - `cli.py`：Typer CLI；规则/覆盖率/CI/Hooks/计划等子命令
  - `rules_ingest.py`：规则摄取/短语解析/冲突检测/建议与编译产物
  - `coverage_summary.py`：coverage.xml 解析、弱项/分组/目录树/近阈值
  - `hooks.py`：pre-commit 与 GitHub Actions 生成/自修复
  - `checks.py`：受影响测试与失败历史缓存；lint/type/tests 统一执行
  - `config.py`：配置合并与默认值；人类可读摘要
  - `fs_wrapper.py`：受控写入（预留挂钩）
  - 其余：记忆、规则基线、服务器入口
- `extensions/vscode/`：VS Code 扩展（面板与命令）
- `docs/`：架构/配置/性能/用法/TDD 计划等
- `.github/workflows/ci.yml`：CI（建议由生成器产出，遵循配置）

## 本地环境
- Python ≥3.10，Node ≥18
- 安装：`pip install -e .`
- 工具链（可选）：`mcp-rules-assistant prepare-env --install`
- 快捷：`make setup|test|lint|type|ci|coverage|vscode-test`

## 性能与门禁策略
- Fast（默认）：保存仅格式化+改动文件 lint；提交增量类型；推送/CI 全量测试+覆盖率+安全
- 阈值来源：`.mcp/assistant.yaml`（`performance.on_push.coverage.min_module`）与 `coverage.policy`
- 建议：用生成器覆盖 `.pre-commit-config.yaml` 和 `.github/workflows/ci.yml`，保持与配置对齐
- 可选写入后检查：在配置中设置 `execution.fs_guard_post_checks: true` 可开启 FSGuard 的写入后轻量检查（lint/type/受影响测试）。严格阻断仍建议通过 fs.apply_patch 的 `strict` 模式与 CI/Hooks 实现。

## 规则摄取与编译
- 摄取：`mcp-rules-assistant ingest-rules README.md docs/`
- 产物：`.mcp/rules_raw.json`、`.mcp/rules_compiled.json/.md`、`.mcp/rules_suggestions.md`
- 冲突：>5% 数值分歧标记；保留更严格值并生成建议
- 与 CI/Hooks：`rules.enforce` 将阈值/策略回写配置；CI/Hooks 据此生成

## 覆盖率与报告
- 运行：`pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov --cov-report=xml:coverage.xml`
- 汇总：`mcp-rules-assistant coverage-report --json`
- 近阈值：`coverage-near --within 3 --top 20`（可用 `coverage.near-set` 调整窗口/Top）
- 核心模块（≥98%）示例策略（已写入 `.mcp/assistant.yaml`）：
  - `mcp_rules_assistant/config.py`
  - `mcp_rules_assistant/progress.py`
  - `mcp_rules_assistant/tools.py`
  - `mcp_rules_assistant/memory.py`
  - `mcp_rules_assistant/mcp_server.py`
  - `mcp_rules_assistant/cli.py`
  - `mcp_rules_assistant/server.py`

## CI 与 Hooks
- 生成：`mcp-rules-assistant generate-ci` 与 `install-hooks`
- 自修复：`mcp-rules-assistant ci-autofix`
- 条件化步骤：
  - hadolint：当开启容器策略或 `ci.hadolint=true`
  - semgrep：当开启 `security.sast_strict` 或 `ci.semgrep_config`
- 计划门禁：提交信息需包含 `[step:当前步骤]`，且 `.mcp/plan.md` 处于 `in_progress`

## VS Code 扩展
- 启动面板：命令 “MCP: Open Panel”；支持规则摄取/建议/覆盖率（弱项/分组/目录树/近阈值）与 CI 配置保存
- Python 解释器可通过 `MCP_PYTHON_BIN` 指定

## 贡献与提交
- 建议 TDD：先红后绿再重构
- 代码风格：ruff/black/isort/mypy/bandit；CI 中阻断或非阻断分层
- 提交规范：conventional commits；在 commit-msg Gate 下包含 `[step:...]`

## 发布
- Python：更新 `mcp_rules_assistant/__init__.__version__` → `make package` → twine 上传
- VS Code（可选）：`npm --prefix extensions/vscode run compile` → `vsce package`

## 任务清单（面向近期）
- [ ] 统一门槛来源与生成物（生成器覆盖 hooks/CI；取值自配置）
- [ ] 版本号对齐（pyproject vs __init__）
- [ ] FSGuard 写入后置挂钩（checks.run_checks，按性能档）
- [ ] 覆盖率“核心≥98%”操作指南与 coverage.policy 示例
- [ ] CI 安全步骤条件化（hadolint/semgrep）
- [ ] 清理小问题（死代码/注释更新；样例文件用途说明或迁移 fixtures）
- [ ] 覆盖率与 near 报告稳定性回归；mypy 告警压降
 - [ ] VS Code Webview 行为修复：近阈值按钮通过 postMessage → 扩展侧调用 MCP，再回传结果（移除 webview 中对 vscode.window/client 的直接调用）
 - [ ] MCP initialize.capabilities 中 prompts 对齐：移除声明或添加最小 prompts 端点占位
 - [ ] Codecov 上传策略与 README 对齐：公共仓库默认上传（无需 token）、私有仓库使用 CODECOV_TOKEN 条件化
 - [ ] pre-commit 中本地脚本（.mcp/plan_gate.py/.mcp/dockerfile_gate.py）条件生成或在第一次运行前引导执行 install-hooks，避免缺文件失败
 - [ ] 依赖精简：若未使用 pydantic 则移除依赖

> 注：详见 `docs/DEV_PLAN_TDD.md` 的 “近期待办”。本指南将随计划推进而更新。
