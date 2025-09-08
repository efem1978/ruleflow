# AI 开发者指南 / AI Developer Guide

提示：本仓库的“编程指南主入口”为根目录 `DEVELOPMENT.md`，请优先阅读并遵循其中的约束、TDD 计划与文档索引；本文件补充设计理念与深入策略细节。

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
- Python ≥3.10，Node ≥18（CI 使用 20）
- 安装：`pip install -e .`
- 工具链（可选）：`mcp-rules-assistant prepare-env --install`
- 快捷：`make setup|test|lint|type|ci|coverage|vscode-test`

## 性能与门禁策略
- Fast（默认）：保存仅格式化+改动文件 lint；提交增量类型；推送/CI 全量测试+覆盖率+安全
- 阈值来源：`.mcp/assistant.yaml`（`performance.on_push.coverage.min_module`）与 `coverage.policy`
- 建议：用生成器覆盖 `.pre-commit-config.yaml` 和 `.github/workflows/ci.yml`，保持与配置对齐
- 可选写入后检查：在配置中设置 `execution.fs_guard_post_checks: true` 可开启 FSGuard 的写入后轻量检查（lint/type/受影响测试）。严格阻断仍建议通过 fs.apply_patch 的 `strict` 模式与 CI/Hooks 实现。
 - 严格阻断（FSGuard）：当 `execution.fs_guard_post_checks: true` 且 `execution.fs_guard_strict: true` 时，如果写入后检查失败，将直接抛错阻断写入（与 `fs.apply_patch --strict` 语义一致，便于统一行为）。
 - 密钥扫描：启用 `security.secrets_scan` 后，pre-commit 将添加 `detect-secrets`（commit/push 阶段），CI 的“Pre-commit (all files)”步骤也会执行该扫描。

## 规则摄取与编译
- 摄取：`mcp-rules-assistant ingest-rules README.md docs/`
- 产物：`.mcp/rules_raw.json`、`.mcp/rules_compiled.json/.md`、`.mcp/rules_suggestions.md`
- 冲突：>5% 数值分歧标记；保留更严格值并生成建议
- 与 CI/Hooks：`rules.enforce` 将阈值/策略回写配置；CI/Hooks 据此生成

## 覆盖率与报告
- 运行：`pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml`
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

注意：coverage.policy 键应与 coverage.xml 中的 <class filename> 一致；本项目中 filename 为“basename”，因此建议使用 `cli.py`、`mcp_server.py` 等作为前缀，以确保策略命中。

## CI 与 Hooks
- 生成：`mcp-rules-assistant generate-ci` 与 `install-hooks`
- 自修复：`mcp-rules-assistant ci-autofix`
- 条件化步骤：
  - hadolint：当开启容器策略或 `ci.hadolint=true`
  - semgrep：当开启 `security.sast_strict` 或 `ci.semgrep_config`
- 计划门禁：提交信息需包含 `[step:当前步骤]`，且 `.mcp/plan.md` 处于 `in_progress`

## 统一子进程封装 / Unified Process Runner

- 入口：`mcp_rules_assistant/process.py` 提供 `run_cmd`，所有外部命令统一经该封装调用（dev_agent/hooks/mcp_server 已委托）。
- 默认策略：
  - 默认超时 300 秒，可通过 `timeout` 覆盖。
  - 当 `capture_stdout=True` 时，同时捕获 `stderr`，并对 `stdout/stderr` 做末尾截断（最大 8000 字符），避免日志爆量。
  - 兼容测试桩：当不捕获输出且未显式传 `env/timeout` 时，仅传递 `cmd/cwd/check` 基础参数，确保 `subprocess.run` 的简易替身不被额外关键字干扰。
  - 可选重试：`retries` 与 `backoff`（指数退避，默认不重试）；如仅希望对超时重试，可在模块中开启“仅超时重试”策略（见实现）。
- 测试约定：
  - 建议对 `mcp_rules_assistant.process.run_cmd` 打桩；若需要模块级替身（如 `dev_agent.run_cmd`），亦可对 re-export 的符号打桩。
  - 用例应避免直接 patch `subprocess.run`，除非明确需要覆盖更底层行为。
  - 运行时临时日志：设置 `MCP_RUN_CMD_LOG=1` 可在 CI/本地输出 run_cmd 的 start/end/error 事件摘要（仅调试使用）。

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
- [x] 统一门槛来源与生成物（生成器覆盖 hooks/CI；取值自配置）
- [x] 版本号对齐（pyproject vs __init__）
- [x] FSGuard 写入后置挂钩（checks.run_checks，按性能档）
- [x] 覆盖率“核心≥98%”操作指南与 coverage.policy 示例
- [x] CI 安全步骤条件化（hadolint/semgrep）
- [x] 清理小问题（样例文件迁移至 tests/fixtures；README 标注生成型工件；移除/忽略多余样例文件如 cov.json/cjson.json）
- [x] 覆盖率 near 报告稳定性回归；mypy 告警压降（非核心）
 - [x] VS Code Webview 行为修复：近阈值按钮通过 postMessage → 扩展侧调用 MCP，再回传结果
- [x] MCP initialize.capabilities 中 prompts 对齐：提供 prompts/list 与 prompts/get 最小内置端点
 - [x] Codecov 上传策略与 README 对齐：公共仓库默认上传（无需 token）/私有仓库用 CODECOV_TOKEN 条件化
 - [x] pre-commit 本地脚本（.mcp/plan_gate.py/.mcp/dockerfile_gate.py）首次运行前引导 install-hooks 或条件生成，避免缺文件失败
 - [x] 依赖精简：移除未使用依赖（已无 pydantic）

> 注：详见 `docs/DEV_PLAN_TDD.md` 的 “近期待办”。本指南将随计划推进而更新。
