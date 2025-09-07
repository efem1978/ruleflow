性能与触发点 Performance & Triggers

设计原则 Principles
- 轻内环：保存 < 1s；仅做增量与缓存检查。
- 重外环：提交/推送/CI 承担完整质量关口。
- 分层门槛：覆盖率门槛以配置为准（核心更高）；严格档启用变异测试。

模式 Modes（最佳默认 Best Default: Fast）
1) Fast（默认，最佳内环体验）
   - On Save: 格式化+改动文件 lint，禁增量类型检查（可开）
   - On Commit: lint + 增量类型 + 受影响测试
   - On Push: 全量测试 + 覆盖率门槛（以配置为准）+ 安全扫描
   - CI: 全套报告；可启用多 Python 版本矩阵

2) Standard（专业）
   - On Save: + 增量类型检查
   - 其余同 Fast

3) Strict（企业/机构）
   - On Push/CI: 变异测试（按改动模块），核心覆盖率≥95%
   - 规则更严：禁止 skip/xfail，警告视为错误

优化技巧 Optimizations
- `dmypy` 增量类型检查；`pytest -k`/testmon 选择性测试；`ruff --fix` 改动文件
- `pytest -n auto` 并行；覆盖率与安全扫描集中在 pre-push/CI
- 按模块阈值清单，增量覆盖率专盯改动模块
- 重型任务夜间/PR 标签触发

覆盖率解析缓存 Coverage XML Caching
- 本地读取 `coverage.xml` 时会使用 `.mcp/coverage_cache.json` 进行缓存，加速大文件解析。
- 缓存根据 `coverage.xml` 的修改时间与大小签名自动失效并刷新。

受影响测试 Heuristics（轻量实现）
- 规则：优先运行改动的测试文件、按文件名映射（tests/test_<stem>.py）与导入引用匹配（import/from 模块路径）
- 失败缓存：`.mcp/last_failed_tests.json` 记录上次失败的测试文件与用例 nodeid，下一次按历史失败频次优先运行（自动合并）
- 边界：不做昂贵的全量依赖分析，保持快速与稳定；仅在受控写入的“quick tests”中使用
