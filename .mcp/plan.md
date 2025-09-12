# 项目审计与整改计划（权威唯一）

- 状态: in_progress
- 当前步骤: P0 收尾与文档整理
- 下一步: P1 质量与集成增强
- 说明: 本文件为唯一权威任务清单来源。面板/CLI/钩子与任何自动化均以此为准。

审计结论（基于代码与构建产物，非文档口径）
- 覆盖率: 核心模块≥98%，非核心≥95% 已达标（coverage.xml 实测；weak=0；near 窗口=0.8%）。
- 质量门禁: pre-commit/commit-msg/pre-push/CI 全链路有效；包内禁止 skip/xfail；安全扫描与 VS Code lcov 门槛已接入。
- 目录结构: 包结构清晰（mcp_rules_assistant/*），扩展与脚本分区合理；未发现错误归置。
- 文档体系: README/DEVELOPMENT 与 docs/* 完整，且已将 `.mcp/plan.md` 标注为唯一权威来源。

P0 必做（当前迭代）
- [x] 清理工作区未跟踪/生成物（保持仓库干净）
  - 执行: `make clean` 或 `sh scripts/workspace-clean.sh`
  - 目标: 移除 `bad.py/ok*.py/ok.txt/near_vscode.txt/coverage*.xml/.coverage*` 等本地样例与产物
- [x] Python 测试“零跳过”稳定性复核（CI Linux/macOS 均为 0 skipped）
  - 关注文件（仅在平台不支持 symlink 时会触发 skip — CI/Linux 下不跳过）:
    - `tests/unit/test_mcp_server_security_limits.py`
    - `tests/unit/test_mcp_server_more_margins.py`
    - `tests/unit/test_mcp_server_coverage_boost2.py`
    - `tests/unit/test_mcp_server_edges_batch2.py`
  - 如在非 Linux 环境需要“零跳过”，方案: 用 monkeypatch 模拟 symlink 行为或以临时文件替代，移除 pytest.skip 分支
- [x] 一键导出覆盖率追踪构件到 `.mcp/dashboard/`（便于审阅与留档）
  - 执行: `mcp-rules-assistant coverage-export --out-dir .mcp/dashboard`
  - DoD: 产出 `coverage_summary.json/weak_top.csv/near_top.csv/groups.csv`
- [x] 入口指南复核（已就绪）
  - README 与 DEVELOPMENT.md 顶部“Authority Notice”与“plan-open”指引一致且可用
  - 若新贡献者首次进入：在 README“快速开始”小节增补“打开计划”的一句提示（非功能性）

P1 改进（下一迭代）
- [ ] checks 统一委托 process.run_cmd（便于观察/重试/日志统一）
  - 打开: 在 `.mcp/assistant.yaml` 设置 `execution.checks_delegate_run_cmd: true`
  - 用例: 保持现有桩兼容；必要时对 `process.run_cmd` 打桩
- [ ] JetBrains 插件增强（从 smoke 到可交互写入）
  - 受控写入入口与“写入后检查”开关映射到 MCP（strict + post_checks）
  - 提交 Storyboard + UI smoke 到 CI 工件（已有基础，补充断言与日志）
- [ ] VS Code 覆盖率长期阈值 95% 保持（near/worst 导出脚本已接入）

P2 发布与合规（按需）
- [ ] 发布脚本与素材完善：PyPI/VSIX、发行说明模板、商店截图/图标
- [ ] 许可硬门禁演练自动化：`make release-harden-verify` 结果入库至 `.mcp/dashboard/release_check.md`

记录与状态
- 近阈值策略: within=0.8%（0.008），用于清理 near 列表，聚焦真正弱项
- 覆盖率政策: 核心≥0.98；非核心≥0.95；`dev_agent.py ≥0.95`、`license_utils.py ≥0.95`

执行小贴士
- 打开本计划: `mcp-rules-assistant plan-open`
- 标记当前步骤: `mcp-rules-assistant plan-set --status in_progress --current "P0 清理与复核" --next-step "P1 统一执行器与 IDE 增强"`
