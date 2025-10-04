<!-- markdownlint-disable MD022 MD032 MD013 -->
# 发布检查清单 / Publishing Checklist (v0.2.6)

（本文档为发布操作清单，保留紧凑格式以便快速执行）

## 0) 预发布校验（必做）
- 刷新状态与生成报告（本仓库已内置脚本）：
  - `make status-update`（或 `sh scripts/status-update.sh`）
  - `make release-draft`（或 `sh scripts/release-draft-gen.sh`）
- 检查：
  - `.mcp/dashboard/status.json`（覆盖率/弱项/近阈值）
  - `.mcp/dashboard/release_body.md`（自动生成的发布正文草案）
  - `.mcp/dashboard/release_notes_v*.md`（人工整理的发布说明草案，可选）
- 确认：
  - Python 测试全绿、覆盖率达标（≥98%）、无 skip/xfail、零告警（`-W error`）
  - VS Code 测试全绿（无头或 CI 环境）、覆盖率达标（≥98%）
  - 所有 lint/type/format 检查通过（`make lint`、`make type`、`make format-check`）

## 1) Git 标签（本地打 Tag 后手动推送）
- 确认 `pyproject.toml` 的版本号与 VS Code `package.json` 的版本号一致（例如 `0.2.6`）
- 本地打标签：`git tag v0.2.6 && git push origin v0.2.6`
- 或推送所有标签：`git push --tags`
- GitHub Actions 会自动触发 CI（测试、打包、上传制品）

## 2) GitHub Release（人工在 Web 上操作）
- 新建 Release（指向标签 v0.2.6）：
  - 标题：`v0.2.6 - [简短摘要，例如：Docs Consolidation & Markdownlint Fixes]`
  - 正文：从 `.mcp/dashboard/release_body.md` 复制或手工整理
  - 附件：从 Actions 制品下载 `dist/*.whl`、`dist/*.tar.gz`、`extensions/vscode/*.vsix`，上传到 Release
- 发布 Release（Publish）

## 3) PyPI 发布（示例指令，需 PyPI 凭据）
- 环境：`python -m pip install --upgrade pip twine`
- 上传：`twine upload dist/*`（需要 PyPI API Token 或用户名密码）
- 验证：`pip install --upgrade mcp-rules-assistant` 可安装最新版

## 4) VS Code Marketplace（示例指令，需 PAT）
- 安装 vsce：`npm i -g @vscode/vsce`
- 发布：`vsce publish`（在 `extensions/vscode` 目录执行；需要 Azure DevOps PAT）
- 验证：在 VS Code Marketplace 搜索 `mcp-rules-assistant` 可见最新版

## 5) 验收与回滚准备
- 下载安装验证：
  - Python：`pip install mcp-rules-assistant==0.2.6`
  - VS Code：在 Marketplace 或本地 VSIX 安装
- 功能烟测：
  - CLI：`mcp-rules-assistant --version`、`mcp-rules-assistant diagnose`
  - VS Code：打开面板、执行"加载覆盖率"、"摄取规则"等核心功能
- 回滚：
  - Git：`git tag -d v0.2.6 && git push origin :refs/tags/v0.2.6`（删除远程标签）
  - PyPI：联系 PyPI 支持或 yank 该版本（不推荐频繁使用）
  - Marketplace：可发布修复版本（patch）
