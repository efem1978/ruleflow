CI 健康检查 / CI Health Check

目的
- 明确 PR/主分支合并前的最小健康检查步骤，快速定位常见失败。

必备检查（按 Job 顺序）
- Lint（ruff/black/isort）：包代码需通过；失败多为格式或导入顺序问题。
- Type Check（core 阻断，其余非阻断）：核心模块（config/progress/tools/memory/mcp_server/cli/server）必须通过。
- Tests + Coverage：
  - Python 测试全绿；生成 coverage.xml。
  - Coverage Policy Gate：弱项 weak=0；若失败，日志中列出文件与差值；同时打印近阈值 TopN 作为补测建议。
- Forbid skip/xfail（包内）：包代码中不允许出现 pytest.skip/xfail 标记。
- Security（bandit 高级别扫描）：无高危问题。
- SAST（semgrep 固定版本）：无阻断问题（策略可调）。
- VS Code 扩展（如启用）：lcov ≥ 95%（警告+门禁双阶段）；失败时附近阈值报告。
- JetBrains Storyboard（可选）：产出 jb_*.json/md 工件，便于审阅。

常见失败与定位
- 覆盖率 Gate 失败：
  - 查看 `Coverage Policy Gate` 步骤输出的 weak 列表与 `near.txt`/`near.csv`/`near.json` 工件。
  - 按 `coverage.policy` 或 `.mcp/assistant.yaml` 的阈值，优先补测近阈值文件（Top 10）。
- VS Code lcov 失败：
  - 查看 `near_vscode.txt` 输出；适当补测或降低不必要的 UI 分支复杂度。
- 类型检查失败：
  - 核心模块为阻断；其余模块的失败先修再合并（建议）。

触发方式
- PR 推送自动触发；若需手动：在 PR 页面使用 `Re-run jobs`。
- Nightly：`nightly.yml`（UTC 03:00）。

通过标准（DoD）
- 所有 Job 成功；Coverage Policy Gate 无 weak；VS Code（如启用）通过 95% 门槛。
