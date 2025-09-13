# 项目审计与整改计划（唯一权威）

- 状态: in_progress
- 当前步骤: 发布摘要入库
- 下一步: （下轮计划待定）
- 说明: 本文件为唯一权威任务清单来源。面板/CLI/钩子与 CI 均以此为准。

本轮审计基于真实代码与测试产物（coverage.xml 与 CLI 解析），不依赖任何文档描述。

审计结论（事实口径）
- 覆盖率: `coverage-report --json` 显示 weak=[]；核心模块≥98%，非核心≥95%；近阈值（near）为空，窗口 within=0.8%。
- 测试: Python 端严格 `-W error`、无 skip/xfail；CI/本地均生成 coverage.xml；VS Code 端 CI 设 95% 硬门禁且含 near/worst 导出。
- 目录结构: 包/扩展/脚本/文档分层清晰；`mcp_rules_assistant/`、`extensions/`、`docs/`、`tests/` 分布合理，无错位文件。
- 文档体系: `DEVELOPMENT.md` 与 `README.md` 顶部已声明“.mcp/plan.md 为唯一权威”，docs/* 为专题与索引；未发现需删除的过时/冗余文档。
- 配置与 CI: `.mcp/assistant.yaml` 与生成的 CI 对 hadolint=2.12.0、semgrep=1.91.x 固定版本一致；`ci.vscode_required=true` 与文档一致。

P0 已完成（本轮）
- [x] 覆盖率与测试门禁复核（weak=0、skipped=0、-W error 无警告）
- [x] CI 健康检查复核：`make local-ci-run` 与 `ci-validate` 通过（含 Coverage Policy Gate）
- [x] 文档入口一致性核验：README/DEVELOPMENT/docs/* 已统一指向 `.mcp/plan.md` 为唯一权威

P1 质量与发布（已完成）
- [x] 夜间/本地回归与覆盖率导出：`.mcp/dashboard/coverage_summary.json`、`weak_top.csv`、`near_top.csv`、`groups.csv`
- [x] 规则编译与建议：`ingest-rules README.md docs/` 刷新 `.mcp/rules_compiled.*`
- [x] 发行物料演练：`.mcp/dashboard/release_check.md` 等

记录与门槛
- 覆盖率策略：核心≥0.98，其它≥0.95（项目配置 `min_module=0.96`；核心按文件后缀 0.98 覆盖）；`coverage.policy` 同时支持前缀/后缀匹配。
- 前端阈值：VS Code CI 95% 硬门禁（`check-lcov.sh ... 95 gate`），失败导出 near/worst 清单。

完成定义（DoD）
- `make local-ci-run` 全绿；`coverage-report --json` 的 weak 为空；`.mcp/assistant.yaml` 与 README/docs 的阈值描述一致。

跟进清单（当前 Sprint）
- [x] 临时目录 `tmp_dbg_dir/` 用途确认：如无用则删除；如保留请加入 `.gitignore` 并在 `DEVELOPMENT.md` 备注用途（避免混淆）
- [x] 覆盖率临时工件（`cov*.json`）保持未追踪；在 `make clean` 中已包含清理，已在 DEVELOPMENT.md 补充注释
- [x] 计划冻结约定：当前不启用只读冻结（`execution.readonly=false`），保留指引与演练说明；若需冻结再开启并在本文件标注时段

审计附注
- 未发现需删除的重复/弃用文档；docs/CONTRIBUTING.md 为根文档的本地化补充且已标注权威来源；docs/LICENSE.md 仅为演示说明，法律文本以根 LICENSE 为准。
