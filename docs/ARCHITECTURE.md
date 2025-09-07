架构 Architecture

目标：性能优先 + 强约束，采用“插件 + MCP Server”解耦 UI 与能力，复用到 CLI/CI。

组件 Components
- Python MCP Server：tools/resources/prompts 协议端点（骨架）。
- 存储 Storage：`.mcp/`（项目）与 `~/.mcp/`（全局），JSON/后续可换 SQLite。
- 规则 Rules：通用规则包 + 项目级摄取与冲突检测（骨架接口）。
- 记忆 Memory：20 轮滚动 + 轻量摘要；跨项目隔离与关系边。
- 执行 Execution：包裹式写入与门禁（占位挂钩），git hooks/CI 兜底。
- VS Code 插件：轻薄拦截与展示，调用 MCP 工具。

性能模式 Performance Modes
- Fast：保存仅格式化+改动文件 lint；提交增量；推送全套；CI 完整。
- Standard：保存加增量类型检查；其余同 Fast。
- Strict：企业/机构档，引入变异测试与更高覆盖率门槛。

商业化与授权
- 预留本地许可校验点（Server 侧），插件保持薄。
- 支持离线激活与企业私有部署。

子进程封装 Process Runner

- 统一封装：`mcp_rules_assistant/process.py` 提供 `run_cmd`，各模块（dev_agent/hooks/mcp_server）统一委托，避免散落的 `subprocess.run`。
- 默认策略：
  - 默认超时 300 秒（可覆盖）。
  - `capture_stdout=True` 时，同时捕获 stderr，并对 stdout/stderr 进行末尾截断（最大 8000 字符）。
  - 兼容测试桩：在不捕获且未传 env/timeout 时，仅传基础参数（cmd/cwd/check）。
  - 可选重试：`retries/backoff`（默认不重试，仅在抛出异常时重试）。
  - 测试建议对 `process.run_cmd` 打桩；若需模块级替身，模块会 re‑export `run_cmd` 以便定向替换。
