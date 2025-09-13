# AI 合规承诺 / AI Compliance Commitment

- 严格遵循 TDD：先红后绿再重构；禁止跳过或投机（no skip/xfail）。
- 警告视为错误（-W error），覆盖率达标（核心≥98%，其余≥95%）；不得以拆分测试等方式规避整体质量。
- 变更伴随测试与文档；不得降低门槛；遵守计划顺序（禁止跳跃）。
- 不引入未经批准的依赖；不暴露端口/遥测；仅落盘状态文件。
- 发现冲突/冗余/不一致，先最小化、再统一，遵循奥卡姆剃刀原则。

English summary:
- TDD strictly; no skip/xfail; warnings-as-errors; coverage thresholds enforced.
- Changes include tests and docs; follow plan order; no scope jumping.
- No unapproved deps; no ports/telemetry; local file artifacts only.
- Resolve conflicts and duplication with minimal and consistent outcome (Occam's razor).