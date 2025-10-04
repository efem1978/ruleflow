# Java 后端（TDD 标准档）/ Java Backend (TDD Standard)

- 风格与静态：Checkstyle + PMD + SpotBugs 全绿
- 代码规范：Google Java Style Guide；SonarQube 质量门禁
- 测试：JUnit 5 + Mockito；核心业务逻辑≥95%覆盖率
- 构建：Maven/Gradle；依赖锁定（dependencyManagement）
- 安全：OWASP Dependency-Check；无高危漏洞
- API 规范：RESTful；OpenAPI 3.0；版本化
- 数据库：Flyway/Liquibase 迁移；可回滚脚本
- 日志：SLF4J + Logback；结构化日志（JSON）
- 异常处理：自定义异常层次；全局异常处理器
- 提交：Conventional Commits；Git hooks（Husky-like）
- 推送：全量测试 + 覆盖率≥95% + 安全扫描 + 代码质量门禁
- JVM 配置：堆大小合理；GC 日志启用
- 容器化：多阶段 Docker 构建；JRE 镜像<200MB
- 监控：Micrometer + Prometheus；健康检查端点
- Spring Boot：遵循最佳实践；配置外部化；Profile 隔离
