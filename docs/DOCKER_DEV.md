基于 Docker 的持续开发与可视化看板

目标
- 在容器内连续运行测试与覆盖率统计，自动生成状态文件与可视化看板，便于无人值守持续开发与远程查看。
- 与本地 IDE 解耦；仍可在 IDE 中与助手交互、查看 `.mcp/plan.md` 或直接打开看板。

快速开始
- 前置：已安装 Docker 与 Docker Compose。
- 启动：`docker compose up --build dev-agent`
  - 首次会安装依赖与工具链，并启动一个本地看板服务。
  - 打开浏览器访问 `http://localhost:8080` 查看看板。

看板内容
- 计划 Plan：读取 `.mcp/plan.md` 并展示 Status/Current/Next。
- 测试 Tests：循环执行 `pytest` + `coverage.xml` 生成，展示最近一次结果与片段日志。
- 覆盖率 Coverage：基于 `coverage.xml` 使用既有逻辑计算并展示 Weak/Groups/Near。
  - 阈值：遵循 `.mcp/assistant.yaml` 的策略（核心≥98%、其余≥95%；默认 min_module≥95%）。

文件与目录
- 开发代理：`mcp_rules_assistant/dev_agent.py`（可独立运行：`python -m mcp_rules_assistant.dev_agent --serve 0.0.0.0:8080`）。
- 看板目录：`.mcp/dashboard/`（写入 `index.html` 与 `status.json`）。
- Compose：`docker-compose.yml`（服务名 `dev-agent`）。

自定义
- 刷新间隔：`--interval <秒>`（默认 60）。
- 仅生成文件不服务 HTTP：去掉 `--serve` 参数，容器中仍会持续更新 `.mcp/dashboard/status.json` 与 `coverage.xml`。

自动提交（可选）
- 通过环境变量启用无人值守的定时版本控制：
  - `DEV_AGENT_AUTOCOMMIT=1`：定时自动执行 `git add -A && git commit`（当 `.mcp/plan.md` 处于 `in_progress` 且存在“当前步骤”时，提交消息自动包含 `[step:当前步骤]` 以通过本地提交门禁）。
  - `DEV_AGENT_AUTOPUSH=1`：在自动提交后执行 `git push`。
  - `DEV_AGENT_COMMIT_INTERVAL=600`：自动提交的间隔（秒），默认 600。
- 在 `docker-compose.yml` 中可按需将上述变量加入 `environment` 数组以启用。

无人值守开发建议
- 配合 Git hooks 与 CI：提交/推送仍由 hooks 与 CI 执行门禁；容器侧看板用于连续反馈。
- Plan 驱动：通过 `mcp-rules-assistant plan-set` 设置计划字段，或直接编辑 `.mcp/plan.md`；容器会自动读取并显示。
- 资源占用：默认每次循环运行全量测试；可在后续将 dev_agent 增强为“改动感知”运行（基于 git diff 或测试索引）。
