贡献指南（简版 / Root Stub）

本仓库采用“快速内环 + 严格 Push/CI 门禁”的开发模式。完整贡献流程已迁移至：`docs/CONTRIBUTING.md`。

快速上手（摘要）
- 环境准备：`make setup` 或 `python3 -m mcp_rules_assistant.cli prepare-env --install`
- 可编辑安装：`pip install -e .`，初始化：`mcp-rules-assistant init`
- 本地校验：`make local-ci-run`（lint/type/tests+coverage/policy）
- 规则摄取（可选）：`mcp-rules-assistant ingest-rules README.md docs/`
- 安装钩子：`mcp-rules-assistant install-hooks`

提交与门禁（摘要）
- 唯一权威任务清单：`.mcp/plan.md`；提交信息需包含 `[step:<当前步骤>]`
- 更改 `.py` 源码应配套 `tests/`；Push 触发覆盖率与安全门禁

更多细节：请阅读 `docs/CONTRIBUTING.md`、`README.md` 与 `DEVELOPMENT.md`。
