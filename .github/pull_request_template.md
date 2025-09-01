## 变更摘要 / Summary

- [ ] 说明本 PR 的目的、范围和风险。

## 检查清单 / Checklist

- [ ] CI 全部通过（build × Python 版本、prepare）
- [ ] 覆盖率 ≥ 95%（本地 `pytest -q -W error --cov --cov-fail-under=95`）
- [ ] patch 覆盖率合理，未出现大面积未测代码
- [ ] 无 `skip/xfail`，无 `warnings`（CI 强转为 error）
- [ ] 如涉及 CI/安全策略，更新文档（README/CONTRIBUTING）

## 验收说明 / Notes for Reviewers

- 运行指令：`make test` 或 `pytest -q -W error --cov --cov-fail-under=95`
- 覆盖率报告：CI 会上传至 Codecov（徽章与 PR 检查）
