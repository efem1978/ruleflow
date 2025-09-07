# 项目计划 / Project Plan（进行中）

- 状态: in_progress
- 当前步骤: 提升 memory.py/mcp_server.py 覆盖率并修正 coverage.policy 应用
- 下一步: 完成 license_utils 与 fs_wrapper 覆盖收尾，验证 CI 覆盖率 Gate
- 风险与阻塞: （待补充）

## 任务清单（可勾选）

- [x] 构建 Python 包（dist/*.whl, *.tar.gz）
- [x] 构建 VS Code 扩展（extensions/vscode/*.vsix）
- [ ] 提升 fs_wrapper 至 ≥95%
- [x] 提升 atomics 至 100%
- [x] 提升 dev_agent 至 ≥95%
- [x] 提升 cli 至 ≥98%
- [x] Docker 内跑通测试（含 RS256）
- [ ] 提升 mcp_server 至 ≥98%
- [ ] 提升 license_utils 至 ≥90%
- [x] 运行 `make verify`（绿）与结构自检（无冗余/过时）
