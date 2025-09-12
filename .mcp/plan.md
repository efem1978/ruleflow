# 项目审计与整改计划（权威唯一）

- 状态: in_progress
- 当前步骤: P1 质量与集成增强
- 下一步: P2 发布与合规（按需）
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

P1 改进（当前）
- [x] checks 统一委托 process.run_cmd（便于观察/重试/日志统一）
  - 已开启：`.mcp/assistant.yaml` → `execution.checks_delegate_run_cmd: true`
  - 回归：容器内全量用例通过；历史测试桩兼容
- [x] JetBrains：CI 工件验证（Storyboard + UI smoke）
  - 已在 Docker 中运行 `jb-package` 与 `jb-ui-smoke`，产出并校验 `jb_verify.json`
  - 后续增强：细化断言，补充更全面 UI smoke 路径（可选）
  - 已增强：`scripts/jb-ui-verify.sh` 追加 assistant.yaml 的 execution/ci 摘要（fs_guard/委托开关、hadolint/semgrep/mutation/vscode_required）
- [x] JetBrains：受控写入入口与严格/后置检查 UI 映射
  - 工具窗口新增复选框与“应用受控写入配置”按钮，映射到 MCP `config.update`（execution.fs_guard_post_checks / fs_guard_strict）
  - 需在真实 IDE 内验证交互（容器 smoke 已覆盖读取 plan/coverage）
- [x] VS Code 95% 硬门禁脚本与阈值保持（CI）
  - 脚本：`scripts/check-lcov.sh` / `scripts/lcov-near.sh` 已接入
  - CI 变量：`VSCODE_COVERAGE_GATE=1`、`VSCODE_COVERAGE_THRESHOLD_WARN=95` 已在工作流配置
  - 说明：已引入 Webview ready + idle 等待（`_test_waitReady`/`_test_waitIdle`）与 `fake_mode` 哨兵，统一夹具工作区（`.test-fixture`）。容器本地已稳定通过；CI 维持 95% 门禁。
 - [x] VS Code 截图 PNG 化与素材完善
   - `images/icon-128.png` 作为 icon；`screenshot1.png/screenshot2.png` 作为商店截图；提供 `svg2png`/`svgshots` 脚本（失败时回退复制，保障打包）

P2 发布与合规（按需）
- [x] 许可硬门禁演练自动化：`scripts/release-harden-verify.sh` 已在容器内跑通，结果入库 `.mcp/dashboard/release_check.md`
- [x] Python 包本地构建与校验：`python -m build && twine check` 通过，产物位于 `dist/`
- [x] VS Code VSIX 本地打包：`npm --prefix extensions/vscode run package` 产物 `extensions/vscode/*.vsix`
- [x] 发布脚本与素材完善：发行说明模板（已有）、商店截图/图标（已补：`extensions/vscode/images/*`，`package.json` 已配置）

记录与状态
- 近阈值策略: within=0.8%（0.008），用于清理 near 列表，聚焦真正弱项
- 覆盖率政策: 核心≥0.98；非核心≥0.95；`dev_agent.py ≥0.95`、`license_utils.py ≥0.95`

执行小贴士
- 打开本计划: `mcp-rules-assistant plan-open`
- 标记当前步骤: `mcp-rules-assistant plan-set --status in_progress --current "P0 清理与复核" --next-step "P1 统一执行器与 IDE 增强"`
