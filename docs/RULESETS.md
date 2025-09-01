规则包 Rule Sets（Python 优先）

维度 Dimensions
- 应用场景：个人 / 专业个人 / 企业 / 机构
- 复杂度：小 / 中 / 大
- 开发模式：TDD / BDD / 文档驱动 / 原型

门槛 Thresholds
- 最低级模块覆盖率 ≥ 90%
- 核心模块覆盖率 ≥ 95%（严格档可更高）
- 禁止 skip/xfail；警告视为错误
- 企业/机构或严格档启用变异测试

选择器 Selector（示意）
- personal+small → 90/95，不启用变异
- pro+medium/large → 92/96，不启用变异
- enterprise/institution + medium/large → 95/97，启用变异

文件组织 Files
- rulesets/general/python_backend_tdd_standard.md
- rulesets/general/python_backend_tdd_strict.md

