# 条件化规则标签（Conditional Rule Tags)

本文档说明如何在项目规则文本中使用“条件化标签”，使某些规则仅在特定环境/IDE/操作系统下生效。

- 支持的标签（可组合，区分大小写与否：不区分）：
  - `[env:container]` 或 `[env:docker]`
    - 本机存在 `docker` CLI 或仓库根存在 `Dockerfile` 时生效
  - `[ide:vscode]`
    - 本机存在 `code` 或 `code-insiders` CLI 时生效
  - `[os:windows|linux|darwin]`
    - 按操作系统生效，可多个值，用 `|` 或 `,` 分隔

- 示例：
  - `- [env:container] 覆盖率 95%`
    - 在容器化场景将被解析为 `coverage.min_module: 0.95`
  - `- [ide:vscode] 检查 VS Code 前端 lcov ≥ 90%`
    - 仅在本机存在 VS Code CLI 时编译为相关策略/建议
  - `- [os:windows|darwin] 禁止 skip/xfail`
    - 仅在 Windows 或 macOS 下编译为 `test.no_skip_xfail: true`

- 注意：
  - 未带任何标签的行对所有环境生效（保持向后兼容）。
  - YAML/JSON 规则不支持标签；如需条件化，建议以文本形式给出并使用标签。
  - 条件解析在 `rules_ingest.py` 的编译阶段完成；若标签无法解析或环境探测失败，将“宽松处理”（不因为标签异常而中断摄取）。

- 相关命令：
  - 规则摄取：`mcp-rules-assistant ingest-rules <文件或目录>`
  - 规则说明：`mcp-rules-assistant rules-explain --json`
  - 环境自适应：`python -m mcp_rules_assistant.cli env-autotune [--apply]`

如需示例或模板，请参考 `docs/RULES_INGEST.md` 与本文件中的示例片段，或在 `docs/` 中创建你的团队规则文档并打上标签。
