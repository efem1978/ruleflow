# 文档维护映射 / Docs Ownership Map

目的：标记关键文档的“所有者/维护者（角色而非个人）”与触发更新的条件，便于 AI 与人类在无人值守模式下保持文档与实现的一致性。

- DEVELOPMENT.md（主入口）
  - 角色：Tech Lead / Maintainers / AI 协作者
  - 触发：
    - 任何影响开发流程/门禁/TDD 计划/无人值守配置的变更
    - CI/Hooks/Compose 结构调整；容器运行模式变化

- docs/DEV_PLAN_TDD.md（分层推进计划）
  - 角色：Test Lead / Maintainers
  - 触发：新增/重构模块、覆盖率门槛或测试策略调整

- docs/ARCHITECTURE.md（架构）
  - 角色：Tech Lead
  - 触发：模块边界/接口变更；依赖拓扑重大调整

- docs/CONFIG.md / docs/PERFORMANCE.md（配置与性能）
  - 角色：Maintainers
  - 触发：新增/修改配置键；阈值策略来源调整

- docs/HOOKS.md（Git Hooks 与 CI）
  - 角色：CI/CD Owner
  - 触发：CI 工作流/本地钩子生成逻辑、门禁策略变更；VS Code 测试纳入 CI 的开关变更（`.mcp/assistant.yaml: ci.vscode_required`）

- docs/DOCKER_DEV.md（容器开发）
  - 角色：Infra Owner
  - 触发：Compose/镜像/运行命令变化；前端/UI 能力变更（当前为无前端，仅落盘状态文件）

- docs/USAGE.md / docs/AI_DEVELOPER_GUIDE.md（使用与深入）
  - 角色：Maintainers
  - 触发：CLI 子命令/行为变更；AI 约束或协作模式调整

维护实践（建议）
- 变更伴随 PR：改动代码需同步更新相应文档；PR 描述中链接到受影响文档段落
- 快照检查：为生成类文档（如 CI）保留最小 diff 快照，必要时在测试中校验关键行
- 自检命令：详见 `DEVELOPMENT.md` 的“文档维护与自检”段

