规则摄取与校验（首版）

目标
- 从选定的文档/文件夹中提取项目级规则，去重并合成“编译版规则”，识别冲突并给出解决建议。
- 结果写入：`.mcp/rules_raw.json`（原始提取）、`.mcp/rules_compiled.json/.md`（编译与冲突）。

支持的输入
- 文本：`.md/.txt/.rst`（提取条目行，例如以 “- ”、“* ”、“1.” 开头，或较短的规则语句）
- YAML/JSON：直接扁平化为 key-value

识别的规则键（示例；注意：实际门槛与策略以 `.mcp/assistant.yaml` 为准，本文示例不构成最终阈值）
- coverage.min_module（最低级模块覆盖率）
- coverage.min_core（核心模块覆盖率）
- test.no_skip_xfail（禁止 skip/xfail）
- test.warnings_as_errors（警告视为错误）
- test.mutation_required（变异测试要求）
- dev.tdd（测试先行）
- process.strict_order（严格按顺序开发）
- security.secrets_scan（密钥扫描）
- security.sast_strict（严格安全扫描）
- container.required（要求容器化/Dockerfile/devcontainer）
- container.policy.baseline（镜像基线/非 root 等）
- perf.budget_ms（性能预算，提取 “xxxms” 数值）
- ci.required（CI 必须通过作为合并条件）
- vcs.conventional_commits（约定式提交）
- vcs.branch_policy（分支策略存在约束）

严格度与冲突
- 布尔：True 比 False 更严格；数值：更大更严格（覆盖率更高）
- 当不同来源对同一键给出差异较大的值（>5%）时，标记为冲突并记录来源；系统保留更严格值。

命令行
- 摄取：`mcp-rules-assistant ingest-rules <文件或目录> [更多路径]`
- 仅校验/重新编译：调用 MCP 的 `rules.validate` 或重新运行摄取命令

MCP 调用
- tools/call name="rules.ingest" arguments={ paths: ["rules.md", "docs/" ] }
- tools/call name="rules.validate"
- 读取编译版规则：resources/read uri="rules://project/<id>/compiled"

注意
- 本首版解析为启发式规则，适合快速落地；后续可引入结构化 schema 与更高级别的冲突语义。
- 当存在 `security.secrets_scan` 或 `container.required` 等策略时：
  - `install-hooks` 会自动在 pre-commit 配置中添加 detect-secrets 或等价检查（push 阶段），保持保存零负担
  - `generate-ci` 会自动加入 `pre-commit --all-files` 与 Dockerfile 存在性检查等轻量步骤
  - 若存在 `container.policy.baseline`：会添加 Dockerfile 基线检查脚本（push 阶段），例如禁止 `USER root`、避免 `:latest`
  - 若存在 `security.sast_strict`：建议在 CI 中追加 `semgrep`（可自定义规则集），默认不在保存/提交阶段执行

短语对照（示例；用于演示解析，不作为最终门槛，请以 `.mcp/assistant.yaml` 为准）
（快速索引见：docs/RULES_PHRASES_INDEX.md）
- 覆盖率（模块）
  - "覆盖率 90%" / "at least 90% (coverage)" → `coverage.min_module: 0.90`
  - "覆盖率 九成"（口语） → `coverage.min_module: 0.90`
  - "覆盖率 九成五"（口语） → `coverage.min_module: 0.95`
  - "覆盖率 95.5%"（小数百分比） → `coverage.min_module: 0.955`
- 覆盖率（核心）
  - "核心 ≥96" / "core >= 96%" / "核心 不少于 96" → `coverage.min_core: 0.96`
  - "核心 覆盖率 十成"（口语） → `coverage.min_core: 1.00`
  - "核心 八成三 覆盖率"（口语） → `coverage.min_core: 0.83`
  - "核心 不少于 96.2%"（小数百分比） → `coverage.min_core: 0.962`
- 禁止跳过
  - "禁止 skip/xfail" / "no skip or xfail" → `test.no_skip_xfail: true`
- 警告视为错误
  - "警告视为错误" / "warnings as errors" / `-W error` → `test.warnings_as_errors: true`
- 变异测试
  - "变异测试" / "mutation test" / "mutmut" → `test.mutation_required: true`
 
上限与区间（记录为提示，不作门禁；示例中的数值仅为说明）
- 上限：
  - "覆盖率 不超过 95%" / "at most 95% (coverage)" → 记录 `coverage.max_module: 0.95`（作为建议 monitor）
  - "core at most 97 percent" → 记录 `coverage.max_core: 0.97`（作为建议 monitor）
- 区间：
  - "≥ 90% 且 < 95%" → 最小值按 90% 落入 `coverage.min_*`；上限按上述“上限”方式作为建议记录
  - "between 90% and 95% (coverage)" → 下限 90% 进入 `coverage.min_*`；上限 95% 作为 `coverage.max_*`（建议 monitor）
  - "覆盖率 介于 96% 和 99% 之间" → 下限 96%；上限 99%（建议 monitor）
- 安全与容器
  - "密钥/凭据/secret(detect-secrets)" → `security.secrets_scan: true`
  - "SAST 严格/semgrep" → `security.sast_strict: true`
  - "Docker/容器化/devcontainer" → `container.required: true`
  - "镜像基线/rootless" → `container.policy.baseline: true`

冲突阈值（可配置）
- `.mcp/assistant.yaml` 可设置：
```yaml
rules:
  conflict_delta: 0.05  # 数值分歧 > 该阈值（默认 0.05=5%）判定为冲突
```

条件化规则标签（可选）
- 支持在文本规则中使用条件标签，仅当条件匹配当前环境时才参与编译：
  - `[env:container]` 或 `[env:docker]`：本机有 docker CLI 或仓库存在 `Dockerfile` 时生效
  - `[ide:vscode]`：本机存在 `code`/`code-insiders` CLI 时生效
  - `[os:windows|linux|darwin]`：按操作系统生效（可多选，`|` 或 `,` 分隔）
- 示例：
  - `- [env:container] 覆盖率 95%` → 仅在容器化场景编译为 `coverage.min_module: 0.95`
  - `- [os:windows] 禁止 skip/xfail` → 仅在 Windows 环境编译为 `test.no_skip_xfail: true`
- 详见：`docs/RULES_CONDITIONAL_TAGS.md`
