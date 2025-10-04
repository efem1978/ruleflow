# Rust 后端（TDD 标准）规则包

## 目标

- TDD 驱动核心路径与并发安全。
- 覆盖率≥90%，核心模块≥95%。
- 性能优先、类型安全、可回滚、可观测。

## 最低门槛（建议）

- 覆盖率：整体≥0.90，核心≥0.95（以 tarpaulin/nextest 统计为准）。
- 工具链：rustfmt + clippy + cargo-nextest/cargo-tarpaulin；
- 错误处理：thiserror/anyhow 规范化，避免 unwrap。

## 测试与用例

- 单元/集成/属性测试（proptest）分层；固定随机种子；
- 避免 Flaky；本地与 CI 一致；
- 禁止跳过（skip/x{fail}/only/focus）。

## CI 门禁（建议）

- Lint/Type → 测试 → 覆盖率门禁 → 安全扫描 → 构建；
- 构建产物可追溯与可回滚。

## 回滚与观测

- 提供回滚脚本；
- 指标/日志/追踪按需；严重错误留痕。
