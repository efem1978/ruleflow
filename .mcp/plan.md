# 项目审计与整改计划（唯一权威）

- 状态: in_progress
- 当前步骤: 评估并（如需）启用 CI 的 hadolint/semgrep 步骤
- 下一步: 夜间本地回归（make nightly-local）并审阅 .mcp/dashboard 产物
- 说明: 本文件为唯一权威任务清单来源。面板/CLI/钩子与 CI 均以此为准。

本轮审计基于真实代码与测试执行（pytest+coverage），不依赖任何文档描述。

审计结论（事实口径）
- 覆盖率: coverage.xml 实测，核心模块≥98%，非核心≥95%，弱项为 0；近阈值窗口按配置 within=0.8%。
- 测试: Python 与 VS Code 测试在本地均可跑通；Python 端严格 `-W error`、无 skip/xfail；VS Code 端 CI 设 95% 硬门禁。
- 目录结构: 包/扩展/脚本/文档分层清晰；无明显错位文件。
- 文档体系: DEVELOPMENT.md / README.md 已明确 `.mcp/plan.md` 为唯一权威，docs/* 具备索引与专题说明，无需去重删除。
- 配置小差异: `.mcp/assistant.yaml` 的 `ci.hadolint_image` 为 2.11.0，而文档统一为 2.12.0（需对齐）。

P0 必做（本轮）
- [x] 对齐 hadolint 镜像版本：将 `.mcp/assistant.yaml` 的 `ci.hadolint_image` 设为 `hadolint/hadolint:2.12.0`（已执行）
- [x] 清理本地未跟踪/生成物（保持仓库干净）
  - 命令: `make clean` 或 `sh scripts/workspace-clean.sh`
  - 范围: `coverage*.xml/.coverage*`, `near*.{txt,csv,json}`, `extensions/vscode/coverage/` 等
- [x] 复核 CI 健康检查：本地执行 `make local-ci-run` 与 `mcp-rules-assistant ci-validate`，固化 near/weak 导出与门禁日志

P1 质量与发布（建议）
- [ ] 将 `.mcp/assistant.yaml` 的 near 窗口参数与实际期望一致（当前 within=0.008 可保留）
- [ ] 确认是否启用 `ci.semgrep_config`（当前文档为 1.91.x 固定版本；如需实际启用，建议在 CI 追加安装与执行步骤）
- [ ] 周期性运行 `make nightly-local` 生成并审阅 `.mcp/dashboard/*`（覆盖率/near/weak/计划快照）

记录与门槛
- 覆盖率策略：核心≥0.98，其它≥0.96；`coverage.policy` 已按文件后缀/前缀双向匹配。
- VS Code：CI 设置 95% 硬门禁（`check-lcov.sh ... 95 gate`）。

完成定义（DoD）
- `make local-ci-run` 全绿；`coverage-report --json` 的 weak 为空；`.mcp/assistant.yaml` 与文档中的镜像/版本声明一致。

附注
- 若未来需要推送远端：在 CI 全绿后，将构件链接附加在本页末尾，无需修改已完成项。
