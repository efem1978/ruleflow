CI 健康检查 / CI Health Check

目的
- 明确 PR/主分支合并前的最小健康检查步骤，快速定位常见失败。

必备检查（按 Job 顺序）
- Lint（ruff/black/isort）：包代码需通过；失败多为格式或导入顺序问题。
- Type Check（core 阻断，其余非阻断）：核心模块（config/progress/tools/memory/mcp_server/cli/server）必须通过。
- Tests + Coverage：
  - Python 测试全绿；生成 coverage.xml。
  - Coverage Policy Gate：弱项 weak=0；若失败，日志中列出文件与差值；同时打印近阈值 TopN 作为补测建议。
  - 构件导出：CI/Nightly 自动运行 `mcp-rules-assistant coverage-export --out-dir .mcp/dashboard`，生成：
    `.mcp/dashboard/coverage_summary.json`、`weak_top.csv`、`near_top.csv`、`groups.csv`（便于下载与审阅）。
- Forbid skip/xfail（包内）：包代码中不允许出现 pytest.skip/xfail 标记。
- Security（bandit 高级别扫描）：无高危问题。
- SAST（semgrep 固定版本）：无阻断问题（策略可调）。
- VS Code 扩展（阶段性策略）：默认仅警告阈值为 ≥80%（非阻断）；可通过设置 `VSCODE_COVERAGE_GATE=1` 启用硬门禁（同阈值）。失败时输出近阈值/最低覆盖文件。
- JetBrains Storyboard（可选）：产出 jb_*.json/md 工件，便于审阅。

常见失败与定位
- 覆盖率 Gate 失败：
  - 查看 `Coverage Policy Gate` 步骤输出的 weak 列表与 `near.txt`/`near.csv`/`near.json` 工件。
  - 按 `coverage.policy` 或 `.mcp/assistant.yaml` 的阈值，优先补测近阈值文件（Top 10）。
- 从构件到行动（Artifacts → Actions）：下载 `coverage-export` 构件，打开 `weak_top.csv` 与 `near_top.csv`：
  - `weak_top.csv`：优先为 delta 最大的前 5–10 个文件补测或提升阈值策略（如核心与非核心分层）。
  - `near_top.csv`：用例微调即可达标的候选，先补齐这些“临门一脚”的文件。
  - `groups.csv`：若某前缀整体偏低，考虑为该前缀集中补测或“分层阈值”策略：
    - 在 `.mcp/assistant.yaml` 的 `coverage.policy` 中为该前缀（目录前缀或文件名后缀）单独设置门槛；
    - 示例：
      ```yaml
      coverage:
        policy:
          "mcp_rules_assistant/dev_agent.py": 0.95  # 非核心维持 95%
          "mcp_rules_assistant/mcp_server.py": 0.98  # 核心提高至 98%
          "mcp_rules_assistant/": 0.95
      ```
    - 先使用 `near_top.csv` 中的“近阈值”文件作为快速修补对象，再整体检查该前缀的 group 覆盖率。
- VS Code lcov 低于阈值：
  - 查看 `near_vscode.txt` 输出；优先为“消息路由/命令处理/核心交互”补测，降低不必要 UI 分支复杂度。
- 类型检查失败：
  - 核心模块为阻断；其余模块的失败先修再合并（建议）。

触发方式
- PR 推送自动触发；若需手动：在 PR 页面使用 `Re-run jobs`。
- Nightly：`nightly.yml`（UTC 03:00）。

通过标准（DoD）
- 所有 Job 成功；Coverage Policy Gate 无 weak；VS Code 覆盖率≥80%（默认仅警告；若启用门禁则需达标）。
