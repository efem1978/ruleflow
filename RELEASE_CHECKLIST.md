# Open-Source Release Checklist · 开源发布清单

Use this checklist when preparing an official public release.
准备对外发布时，可按此清单逐项核对。

## 1. Legal & Licensing · 法务与许可
- [ ] Confirm `LICENSE` is MIT and up-to-date
- [ ] Add or update `NOTICE` if third-party licenses require attribution
- [ ] Verify dependency licenses via `pip-licenses --format=json > licenses.json`

## 2. Documentation · 文档
- [ ] README bilingual overview verified
- [ ] Changelog (`CHANGELOG.md`) updated with latest version
- [ ] Release notes drafted under `docs/releases/`
- [ ] Usage & security docs (`docs/USAGE.md`, `SECURITY.md`) reviewed

## 3. Quality Gates · 质量门禁
- [ ] Run `pip install -r constraints-ci.txt`
- [ ] Run `make local-ci-run` (lint/type/test/coverage/security)
- [ ] Ensure `python -m mcp_rules_assistant.cli coverage-report --json` yields `"weak": []`
- [ ] Verify `cryptography` dependency installed in CI

## 4. Build Artifacts · 构建产物
- [ ] Clean previous builds (`rm -rf dist/ build/`)
- [ ] Build Python package `python -m build`
- [ ] Verify package metadata `twine check dist/*`
- [ ] Build VS Code extension `npm --prefix extensions/vscode run package`
- [ ] (Optional) Assemble release bundle `bash scripts/release-compose-body.sh`

## 5. CI & Automation · 持续集成
- [ ] Confirm `.github/workflows/ci.yml` passes on `main`
- [ ] Run `gh workflow run CI --ref main` for final validation (optional)
- [ ] Check Codecov badge / coverage report accessible

## 6. Security & Compliance · 安全合规
- [ ] Run `detect-secrets scan` with latest baseline
- [ ] Run `bandit -q -r mcp_rules_assistant`
- [ ] Run `semgrep --config .semgrep.yml`
- [ ] Document results in `.mcp/dashboard/security_audit.jsonl` (optional)

## 7. Publish · 发布
- [ ] Tag release `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Push tags `git push origin vX.Y.Z`
- [ ] Create GitHub release `gh release create vX.Y.Z --generate-notes`
- [ ] Upload artifacts (VSIX, wheels, tarballs)
- [ ] Publish PyPI package `twine upload dist/*`

## 8. Post-Release · 发布后
- [ ] Update roadmap `docs/IDE_PLUGIN_ROADMAP.md`
- [ ] Announce release (blog/social/newsletter)
- [ ] Monitor GitHub issues & discussions

