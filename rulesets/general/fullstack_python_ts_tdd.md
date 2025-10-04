# 全栈 Python + TypeScript（TDD 专业档）/ Fullstack Python + TypeScript (TDD Professional)

## 后端（Python）

- 风格与静态：ruff + black + isort + mypy 全绿
- 测试：pytest 并行；核心 API≥95%覆盖率
- API 规范：OpenAPI/Swagger；版本化（v1/v2）；向后兼容
- 安全：bandit + pip-audit；密钥管理（环境变量/Vault）
- 数据库：迁移脚本可回滚；种子数据隔离

## 前端（TypeScript + React）

- 风格与静态：ESLint + Prettier + tsc strict
- 测试：Jest/Vitest + RTL；核心页面≥90%覆盖率
- E2E：Playwright 关键流程
- Bundle：打包大小<500KB（初始）；懒加载路由

## 集成与部署

- 契约测试：Pact/Postman；前后端 API 契约一致
- Docker：多阶段构建；生产镜像<500MB
- CI/CD：矩阵测试（Python 3.10-3.12, Node 18-20）
- 监控：后端日志结构化；前端错误追踪（Sentry）
- 提交：Monorepo 统一 hooks；Conventional Commits
- 推送：全量测试 + 契约验证 + 安全扫描 + 打包验证

## 性能基准

- API 响应时间：P95 < 200ms
- 前端首屏加载：LCP < 2.5s
- 数据库查询：N+1 禁止；索引覆盖率>90%
