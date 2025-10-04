# Python 库开发（严格档，TDD）/ Python Library (Strict, TDD)

- 风格与静态：ruff + black + isort + mypy strict 全绿
- 测试：pytest；公开 API≥98%覆盖率；私有≥95%
- 类型：py.typed 标记；全部公开 API 完整类型注解
- 文档：docstring（Google/NumPy 风格）；Sphinx 自动生成
- 兼容性：支持 Python 3.10+；向后兼容策略明确
- 依赖：最小化；版本范围宽松但下界明确
- 安全：无已知高危依赖；密钥/凭证不硬编码
- 打包：pyproject.toml；wheel + sdist；PyPI 发布
- 语义版本：SemVer 严格；CHANGELOG.md 维护
- 提交：Conventional Commits；自动生成版本号
- 推送：全量测试（多 Python 版本矩阵）+ 覆盖率≥98% + 类型检查 + 文档构建验证
- 破坏性变更：主版本号升级；弃用警告至少一个小版本
- 示例代码：examples/ 目录；可运行且有测试
