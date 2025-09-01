Python 后端（严格档，TDD）/ Python Backend (Strict, TDD)

- 风格与静态：ruff + black + isort + mypy 必过
- 测试：pytest 全量并行；覆盖率：最低级≥90%，核心≥95%（可调更高）
- 变异测试：mutmut/mutatest 对改动模块必须达标（杀死率门槛）
- 警告：`-W error`；禁止 `skip/xfail`
- 安全：bandit 高危为阻断；密钥扫描必过
- 推送/CI：报告与门禁作为合并条件

