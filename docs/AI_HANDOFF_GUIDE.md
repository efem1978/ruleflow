# AI 协作交接指南 / AI Handoff Guide

权威声明
- 唯一权威任务清单：`.mcp/plan.md`。任何任务推进、门禁校验与面板/CLI 状态均以此为准。
- 本指南仅为交接与协作规范，请勿在此维护任务清单。

最小工作流（每次接手都做）
1) 打开权威计划：`mcp-rules-assistant plan-open`（或 IDE 面板“Open Plan/打开计划”）。
2) 同步规则：`mcp-rules-assistant ingest-rules README.md docs/`（生成/刷新 `.mcp/rules_compiled.*`）。
3) 运行测试+覆盖率：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml`。
4) 刷新状态：`mcp-rules-assistant status-update`（写入 `.mcp/dashboard/status.json`）。
5) 在 `.mcp/plan.md` 更新当前步骤与下一步；提交信息包含 `[step:当前步骤]`。

交接清单（模板）
- 计划：状态=in_progress；当前=…；下一步=…（路径：`.mcp/plan.md`）
- 覆盖率：weak=0；near 清单（若非空）；阈值以 `.mcp/assistant.yaml`/policy 为准（路径：`coverage.xml` / `.mcp/dashboard/coverage_summary.json`）
- 规则：是否已刷新；是否存在冲突（路径：`.mcp/rules_compiled.{json,md}`）
- 近期风险/阻断项：…（含复现指令）

AI 编程约束（Do/Don't）
- 仅按计划改动；改动最小化；提交信息带 `[step:…]`。
- 伴随测试与文档；不得降低覆盖率门槛；禁止 skip/xfail；`-W error`。
- 受控写入优先：使用 MCP `fs.apply_patch`（必要时 strict/dry‑run）。

常用入口
- 计划与状态：`.mcp/plan.md`、`.mcp/dashboard/status.json`
- 文档入口：`DEVELOPMENT.md`（开发入口） / `README.md`（产品入口）
- 故障排查：`docs/TROUBLESHOOTING.md`

安全与隔离（团队共识）
- 严格隔离（默认）：扩展以 `MCP_STRICT_ISOLATION=1` 启动后端。此模式下：
  - 仅当 `.mcp/assistant.yaml` 中 `memory.allow_write: true` 才允许写记忆；`RULEFLOW_ALLOW_MEMORY_APPEND` 无效。
  - `project.switch` 默认拒绝（避免跨项目写入）。需切换时显式 `project.allow_switch: true` 或仅当次 `MCP_ALLOW_PROJECT_SWITCH=1`。
  - 记忆写入路径强校验：只允许 `<project_root>/.mcp`。
- 项目分级策略：
  - 允许写入的项目：`memory.allow_write: true`，`project.allow_switch: false`。
  - 禁止写入的项目：`memory.hard_disable: true`（最高优先级，任何来源都不可写入）。
- 批量加固与验证：
  - 运行 `python3 scripts/harden_projects.py --verify <proj1> <proj2> ...`，脚本会写入安全配置并生成 `./.mcp/dashboard/security_verify.json` 验证日志。

备注
- VS Code 扩展无头测试在本机若受 Electron 启动参数影响，可用容器运行：`make docker-vscode-test` 或 `docker compose run --rm vscode-test`；详见 `docs/VS_CODE_TEST.md`。
