# 规则包 / Rule Sets（Python 优先）

## 维度 / Dimensions

- 应用场景：个人 / 专业个人 / 企业 / 机构
- 复杂度：小 / 中 / 大
- 开发模式：TDD / BDD / 文档驱动 / 原型

## 门槛 / Thresholds

> 以 `.mcp/assistant.yaml` 为准；下列数值仅为示意起点。

- 最低级模块覆盖率：以项目配置为准
- 核心模块覆盖率：以项目配置为准（严格档可更高）
- 禁止 skip/xfail；警告视为错误
- 企业/机构或严格档启用变异测试

## 选择器 / Selector（示意）

- personal+small → 90/95，不启用变异
- pro+medium/large → 92/96，不启用变异
- enterprise/institution + medium/large → 95/97，启用变异

## 示例矩阵

> 建议起点，可按项目调整；最终以 `.mcp/assistant.yaml` 为准。

场景 x 复杂度（基于后端 Python 服务）：

- 个人+小型：min_module=0.90，min_core=0.95，no skip/xfail，-W error
- 专业+中型：min_module=0.92，min_core=0.96，no skip/xfail，-W error
- 企业/机构+大型：min_module=0.95，min_core=0.97，no skip/xfail，-W error，变异测试（非阻断→严格时门禁）

## 扩展键示例（与 config.update / rules.enforce 对齐）

- ci.hadolint: true|false（容器项目建议开启）
- ci.semgrep_config: auto|p/ci|p/security-audit（固定版本）
- ci.vscode_required: true|false（是否将前端测试纳入 CI 必跑）
- ci.mutation_gate_strict: true|false（严格时开启变异门禁）

## 文件组织 / Files

- rulesets/general/python_backend_tdd_standard.md
- rulesets/general/python_backend_tdd_strict.md
