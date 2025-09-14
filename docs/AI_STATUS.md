# AI 状态索引 / AI Status Index

权威声明
- 任务与状态均以 `.mcp/plan.md` 与 `.mcp/dashboard/status.json` 为准。本页仅提供“去哪看”的索引。

核心位置
- 任务计划（唯一权威）：`.mcp/plan.md`
- 状态仪表：`.mcp/dashboard/status.json`（聚合 weak/near/plan/memory 等）
- 覆盖率原始文件：`coverage.xml`
- 覆盖率摘要：`.mcp/dashboard/coverage_summary.json`、`weak_top.csv`、`near_top.csv`、`groups.csv`
- 规则编译：`.mcp/rules_compiled.md` / `.json`

如何刷新
- 运行：`mcp-rules-assistant status-update`
- 覆盖率：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml`
- 一次性摘要：`mcp-rules-assistant coverage-report --json`

前端覆盖率（VS Code）
- 优先在容器内运行：`make docker-vscode-test` 或 `docker compose run --rm vscode-test`
- 本机失败（Electron 参数不兼容）时，参考 `docs/VS_CODE_TEST.md` 的“快速失败排查（macOS/无头）”段落。

健康检查（CI）
- 工作流：`.github/workflows/ci.yml`
- 通过标准：Python weak=[]、核心≥98%、非核心≥95%；VS Code lcov ≥98%（本仓库标准）。
