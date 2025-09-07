PR Title: <scope>: <summary>

Summary
- What does this change do? Keep it concise.

Checklist
- [ ] Tests added/updated to cover changes
- [ ] `make local-ci-run` passes locally (lint/type/tests/coverage gate)
- [ ] No skip/xfail introduced (policy forbids in push/CI)
- [ ] `.mcp/plan.md` is `in_progress` and commit message contains `[step:<current-step>]`
- [ ] CI workflow unchanged or updated accordingly

Notes
- If rules were updated, run:
  - `python3 -m mcp_rules_assistant.cli ingest-rules README.md docs/`
  - `python3 -m mcp_rules_assistant.cli enforce && python3 -m mcp_rules_assistant.cli generate-ci`

