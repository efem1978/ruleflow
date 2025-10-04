# 发布说明索引 / Releases Index

## 说明

- 本目录存放已发布版本的"发布说明（Release Notes）"归档。
- 生成与核验流程请参考：`docs/RELEASE.md` 与 `.mcp/dashboard/release_*.md`（由工具自动生成）。

## 当前版本

- v0.2.6（草案）：`docs/releases/v0.2.6.md`
- v0.2.5：`docs/releases/v0.2.5.md`

## 提示

- 建议在每次发布前运行：`sh scripts/release-harden-verify.sh` 与 `make release-check`；
- 将 `.mcp/dashboard/release_body.md` 作为 GitHub Release 正文基础，必要时同步更新本目录归档。
