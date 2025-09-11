商业化与授权边界 / Commercial Packaging & Licensing

目的
- 说明开源与闭源边界、授权模型与最小合规约束，支撑后续商店上架与企业发行。

边界（示例）
- 开源部分（源码可见）：Python 端 MCP 服务与 CLI、VS Code 扩展源码与测试、文档与脚本（本仓库内）。
- 闭源部分（可选）：
  - 许可校验与签名密钥管理（仅公钥下发）；
  - 高级规则包（付费包）与内建策略模板；
  - 扩展 IDE 功能（企业版 UI/报告模板）。

授权与门禁
- 演示/开发：`license.required=false`（默认）；
- 商业/企业：`license.required=true`，关键工具（rules.enforce/ci.* 等）读取并校验 `~/.mcp/license.json`；
- 支持 `hs256/rs256/ed25519`，建议生产使用非对称签名（仅分发公钥）。

构建与发行建议
- 版本控制：打标签发布，生成 sdist/wheel 与 VSIX；
- 物料清单：包含 `coverage-export` 构件、变更摘要、许可条款摘要；
- CI：对工具链使用 constraints（见 constraints-ci.txt）提升可复现性。

支持矩阵（示例）

| 版本 | 能力 | 门禁/策略 | IDE | 支持 |
|---|---|---|---|---|
| 社区版 | 核心 CLI/MCP、规则摄取/覆盖率、面板（VS Code） | 覆盖率分层策略、软拦截、可选 nearTop 导出 | VS Code（完整）、JB（最小） | Issue/PR |
| 专业版 | 高级规则包、扩展报表模板、近阈值导航 | 可选变异门禁、fs.apply_patch 可选硬门禁 | VS Code（完整）、JB（增强） | 邮件支持 |
| 企业版 | 多项目记忆跨链接报表、附加安全与合规模板、审计构件 | 许可硬门禁、定制策略、离线激活 | 多 IDE（按需适配） | 专属支持 |

说明：
- 许可：`license.required=true` 用于专业/企业；演示可使用 `hs256`，生产建议 `rs256/ed25519`（仅分发公钥）。
- 构件：CI/Nightly 上传 `coverage-export`（CSV/JSON）与 `jb-verify`（JSON），便于审阅。
