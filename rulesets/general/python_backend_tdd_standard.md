Python 后端（标准档，TDD）/ Python Backend (Standard, TDD)

- 风格与静态：ruff + black + isort + mypy（增量）全绿
- 测试：pytest 受影响子集，本地并行；覆盖率：最低级模块≥90%，核心≥95%
- 警告：`-W error`；禁止 `skip/xfail`
- 安全：bandit 低于中危；密钥扫描
- 提交：conventional commits；pre-commit 必开
- 推送：全量测试 + 覆盖率阈值 + 安全扫描

