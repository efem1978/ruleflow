基于 Docker 的持续开发（无前端界面）

目标
- 在容器内连续运行测试与覆盖率统计，生成机器可读的状态文件，便于无人值守持续开发与远程查看（无前端界面）。
- 与本地 IDE 解耦；仍可在 IDE 中与助手交互、查看 `.mcp/plan.md` 或直接读取状态文件。

快速开始
- 前置：已安装 Docker 与 Docker Compose。
- 启动开发代理：`docker compose up --build dev-agent`
  - 首次会安装依赖与工具链，并开始周期性更新状态文件（不再提供本地浏览界面）。
- VS Code 扩展无头测试（可选）：`docker compose run --rm vscode-test`
  - 基于 `node:20`，自动安装最小依赖并通过 `xvfb-run` 运行 `npm test`
- JetBrains 构建环境占位（可选）：`docker compose run --rm jb-build`
  - 基于 `gradle:8.7-jdk17`，用于后续 P2/P3 任务（当前命令仅校验环境 `gradle -v`）

状态文件
- `.mcp/dashboard/status.json`：最近一次循环的聚合状态（计划、测试、覆盖率、任务等）。
- `.mcp/dashboard/history.json`：历史摘要队列（最多 50 条）。
- `.mcp/dashboard/fail_counters.json`：失败计数与冻结状态。
  - 简要：`.mcp/dashboard/status_brief.json`（overall/weak_count/timestamp），便于轻量查看。
  - 覆盖率阈值遵循 `.mcp/assistant.yaml`（核心≥98%、其余≥95%；默认 min_module≥95%）。

文件与目录
- 开发代理：`mcp_rules_assistant/dev_agent.py`（可独立运行：`python -m mcp_rules_assistant.dev_agent --interval 60`）。
- 状态目录：`.mcp/dashboard/`（写入 `status.json`、`history.json`、`fail_counters.json`）。
- Compose：`compose.yml`（服务名 `dev-agent`）。

自定义
- 刷新间隔：`--interval <秒>`（默认 60）。
- 测试模式：设置环境变量 `DEV_AGENT_MAX_CYCLES=1` 可只运行 1 个循环并退出（用于 CI/本地验证）。

自动提交（可选）
- 通过环境变量启用无人值守的定时版本控制（默认均为 0，处于禁用状态）：
  - `DEV_AGENT_AUTOCOMMIT=1`：定时自动执行 `git add -A && git commit`（当 `.mcp/plan.md` 处于 `in_progress` 且存在“当前步骤”时，提交消息自动包含 `[step:当前步骤]` 以通过本地提交门禁）。
  - `DEV_AGENT_AUTOPUSH=1`：在自动提交后执行 `git push`。
  - `DEV_AGENT_COMMIT_INTERVAL=180`：自动提交的间隔（秒），默认 180。
- 在 `compose.yml` 中可将上述变量设为 1 以启用；默认 compose 文件已将其设为 0 以避免误操作。

自动里程碑 Tag（可选）
- `DEV_AGENT_AUTOTAG=1`：每日在“全量测试通过且覆盖率 Gate 通过”后自动创建本地标签 `v<版本>-devYYYYMMDD`（不推送）。
- 便于形成稳定里程碑快照，后续如需对外发布可人工选择推送标签。

无人值守开发建议
- 配合 Git hooks 与 CI：提交/推送仍由 hooks 与 CI 执行门禁；状态文件用于连续反馈与审计。
- Plan 驱动：通过 `mcp-rules-assistant plan-set` 设置计划字段，或直接编辑 `.mcp/plan.md`；容器会自动读取并显示。
- 资源占用：默认每次循环运行全量测试；可在后续将 dev_agent 增强为“改动感知”运行（基于 git diff 或测试索引）。
 - 若长时间无进度变化：通常是“计划复选框未更新/代码未变更/覆盖率 Gate 未通过（如 dev_agent.py 未被测试）/未启用自动提交/推送”。确认：
   - `.mcp/plan.md` 有 [x]/[ ] 勾选项，且 `当前步骤` 随进度变化；
   - 如需无人值守提交，请在 Compose 中显式启用：`DEV_AGENT_AUTOCOMMIT=1`（可选）与 `DEV_AGENT_AUTOPUSH=1`（可选）；默认已禁用。
   - 覆盖率弱项清零（面板 Weak 为空）。
常见工具参数（hadolint）
- 忽略特定规则示例：`--ignore DL3008 --ignore DL3013`

历史清理
- `.mcp/dashboard/history.json` 默认保留最近 50 条；如需手动清理，可安全删除该文件，dev_agent 会在下一轮重建。

诊断打包
- 在容器内或主机执行：`python -m mcp_rules_assistant.cli diagnose-bundle`（或 `mcp-rules-assistant diagnose-bundle`）
- 将收集 coverage.xml、pytest-junit.xml、near.{txt,csv,json}、cov.json、.mcp 关键文件（assistant.yaml/plan.md/memory.json/rules_compiled.* 等）打包为 `diagnostics-<ts>.tar.gz`

一键验证（容器内）
- 通过 compose 运行完整预检 + 测试 + 覆盖率门禁 + dev-agent smoke：
  - `docker compose run --rm verify`
  - 该命令内部等价于执行 `make verify`，输出 near/weak 摘要与 dev-agent 快照结果（status.json）。

可选：过滤 coverage 非阻断提示
- 某些路径映射场景下，coverage 在终端报告中可能打印“Couldn't parse '/work/…'”警告（不影响统计与门禁）。
- 可选通过脚本过滤该提示（不改变退出码与门禁）：
  - `... --cov-report=term-missing 2> >(scripts/coverage-warn-filter.sh 1>&2)`
