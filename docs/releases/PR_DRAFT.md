# PR Draft — Docs/CI Consistency + Coverage Polish

Scope
- Add AI handoff/status docs and wire into README/DEVELOPMENT
- Unify VS Code coverage gate wording to “as configured in CI/.mcp/assistant.yaml” across docs/CI
- Polish dev_agent coverage to ≥96.5% (now ~97.46%) via defensive/edge path tests
- CI: export VS Code near/worst list as artifact; Makefile: macOS routes vscode-test via container

Highlights
- AI docs: `AI_HANDOFF_GUIDE.md` (handoff checklist) / `AI_STATUS.md` (status index)
- CI health check doc now aligned with README to reference configured VS Code threshold (no hard-coded number)
- New tests cover freeze recovery, prev coverage read failures, auto-append memory edge cases, event logging errors, main env parse, plan-only progress

Quality Gates
- Python: 665 passed; weak=[]; thresholds per `.mcp/assistant.yaml`/policy; -W error; no skip/xfail
- VS Code: CI gate per configured threshold (fake backend); near/worst exported to artifact `vscode-near`

Artifacts
- Python dist: `dist/*.whl`, `dist/*.tar.gz` (twine check passed)
- VSIX: `extensions/vscode/*.vsix`
- Coverage/near: `coverage.xml` / `near_vscode.txt`

Notes
- macOS local VS Code tests can produce empty lcov due to Electron/DBus; container path recommended (`docker compose run --rm vscode-test`).

