MCP 协议骨架（JSON-RPC/stdio）

说明
- 本骨架实现了最小可用的 JSON-RPC/stdio 服务器，方法名与返回格式参考 MCP 生态。
- 目标是便于 VS Code 插件/CLI 调用，并逐步替换为完整的 MCP 协议栈。

端点 Methods（示例）
- initialize → { server, version, capabilities }
- ping → { ok }
- tools/list → { tools: [{ name, description }] }
- tools/call { name, arguments } → 各工具的返回（见下）
- resources/list → { resources: [{ uri, name }] }
 - resources/read { uri } → { mimeType, text }

示例工具 Tools
- project.detect → 检测项目语言/框架（基于文件探测）
- memory.toggle_auto { on } → 开关滚动记忆（占位）
- memory.snapshot → 返回 `.mcp/memory.json` 的 20 轮与摘要
- rules.init { scenario, complexity, devMode } → 返回门槛说明（最低模块≥90% 等）
- rules.ingest { paths[] } → 摄取文档，生成 `.mcp/rules_compiled.*` 与建议
- rules.validate → 基于已摄取原始数据重新编译与校验
- env.prepare → 占位返回（未来创建虚拟环境等）
- fs.apply_patch { files: [{path, content}], runChecks, strict, dryRun, maxFiles } → 包裹式写入（可启用轻量严格检查）；dryRun 仅返回将写入的文件清单，不落盘；maxFiles 超限拒绝
- git.install_hooks → 占位返回（后续生成 hooks）
- nl.command { text } → 自然语言解析占位
- config.get { section? } → 获取项目配置（或子节）
- config.update { data } → 更新配置中的 `ci` 字段
- ci.generate → 生成 GitHub Actions 工作流
- ci.validate → 校验 CI 工作流是否包含关键步骤（pre-commit/hadolint/semgrep/pytest/bandit）
- ci.autofix → 一键修复：按规则/配置覆盖生成标准 CI（如已有则备份为 ci.yml.bak）
- plan.update { text } → 更新 `.mcp/plan.md` 项目计划

资源 Resources
- memory://<projectId>/rollup
- rules://project/<projectId>/compiled（编译规则 Markdown）
- rules://project/<projectId>/compiled.json（编译规则 JSON，含冲突来源）
- rules://project/<projectId>/suggestions（冲突与建议 Markdown）
- rules://project/<projectId>/maxima（覆盖率上限 JSON：{ maxima: {...} }）
- coverage://project/<projectId>/summary（读取 coverage.xml 生成的覆盖率薄弱项摘要 JSON）
- coverage://project/<projectId>/groups（按 coverage.policy 分组的覆盖率聚合 JSON）
- coverage://project/<projectId>/tree（按目录构建的薄弱文件目录树 JSON，前3层）
 - coverage://project/<projectId>/near（距阈值≤3%但未低于阈值的文件 JSON）
- coverage://project/<projectId>/report（一次性输出 weak/groups/near 的汇总 JSON）
- progress://<projectId>/plan（项目计划 Markdown）
- config://project/<projectId>/assistant.yaml（项目配置 YAML）
- ci://project/<projectId>/workflow（CI YAML 内容）

覆盖率策略 Coverage Policy
- 配置中支持模块级阈值（前缀匹配）：
  coverage.policy: { "src/core/": 0.95, "src/": 0.90 }
  服务器在读取 coverage:// 资源时会应用该策略计算薄弱文件。

文件位置
- 服务器实现：`mcp_rules_assistant/mcp_server.py: serve_stdio()`
- VS Code 客户端调用：`extensions/vscode/src/extension.ts`
