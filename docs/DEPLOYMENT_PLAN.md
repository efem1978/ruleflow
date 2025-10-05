# 部署与发布任务计划 / Deployment & Release Plan

本计划用于交付“可本机使用”的安装包，随后推进 PyPI 与 VS Code 扩展发布，并为商业化（离线许可）做准备。实时状态与当前步骤请在 `.mcp/plan.md` 查看/维护。

参考入口：
- 实时计划（可更新）：`.mcp/plan.md`
- 使用与示例：`docs/USAGE.md`
- 配置：`docs/CONFIG.md`
- 发布指南：`docs/RELEASE.md`
- 容器无人值守：`docs/DOCKER_DEV.md`

里程碑（按你的最新要求调整）
- M0 内测：本地安装与自用评估（不对外发布；仓库可设为私有）
- M1 可用：稳定后再开启发布（PyPI/VS Code 可选，仍不启用收费）
- M2 商业准备：EULA/许可强校验/定价上线（含促销期）

任务清单（概要）
1) M0 内测（当前阶段）
- [x] 构建 Python 包（`dist/*.whl`, `*.tar.gz`）
- [x] 构建 VS Code 扩展（`extensions/vscode/*.vsix`）
- [x] 本机安装验证（CLI + 面板）
  - 步骤（参考）：
    1) 安装：`pip install -e .`
    2) 生成配置与钩子：`mcp-rules-assistant init && mcp-rules-assistant install-hooks`
    3) 运行测试与覆盖率：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml`
    4) VS Code：`npm --prefix extensions/vscode run compile`，F5 启动“扩展开发主机”，执行 `RuleFlow: Open Panel`
    5) 面板验证：
       - “摄取规则”：输入 `README.md, docs/`
       - “加载覆盖率”：展示弱项/分组/近阈值/目录树
       - “安装钩子/生成 CI”：按钮可用，CI 预览成功
    6) 退出并记录：如需脚本化，执行 `make verify`（预检+测试+覆盖率 gate）
- [ ] 仓库可设为私有或保留公开但标注“内测，不对外发布”
- [ ] 暂不配置 Secrets/不打标签发布（保留后续能力）

2) M1 稳定可用（不收费）
- [x] 补 README 的双语引导与两大支柱截图
- [x] 运行 `make verify`（绿）并完成结构自检
- [ ] 选择是否公开 PyPI/VS Code（仍不启用收费与许可强校验）

3) M2 商业化准备（开启收费）
- [x] 许可命令与强校验开关（已支持 HS256/RS256/Ed25519；包含到期校验与签名校验）
- [ ] 定价上线（含促销期）与 MoR 集成（Lemon Squeezy/Paddle）
- [ ] 发布自动化（PyPI/VS Code）与商店素材（图标/GIF/描述）

备注
- 许可能力：提供 HS256/RS256/Ed25519 许可生成/校验与开关（CLI：license-generate/verify/require-on/off）。

许可证门禁 E2E 验证（最小流程）
- 开启发布硬门禁：`mcp-rules-assistant license-require-on`
- 未激活调用 gated 工具示例：`tools/call ci.validate` → 应返回 `license required or invalid`
- 生成并激活许可证（hs256 示例）：
  - 生成：`mcp-rules-assistant license-generate --issued-to you@example.com --expires 2030-01-01 --alg hs256 --out .mcp/lic.json`
  - 激活：`mcp-rules-assistant license-activate --file .mcp/lic.json`
- 再次调用 gated 工具：`tools/call ci.validate` → 通过并返回 `ok: true`
- 关闭发布硬门禁（回到开发模式）：`mcp-rules-assistant license-require-off`

里程碑完成标准（DoD）
- M0：本机安装通过；面板功能可用；不对外发布
- M1：`make verify` 绿；结构自检通过；可选择性公开分发（仍不收费）
- M2：定价与许可强校验就绪；开启促销期；自动发布链路稳定
