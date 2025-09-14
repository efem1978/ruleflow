## Summary

- Purpose: (docs/ci/cleanup/coverage polish)
- Scope: move AI docs to `docs/`, update links, add cleanup notes, CI near/worst export, pre-commit stage, Makefile targets.

## Checklist

- [ ] Plan updated (`.mcp/plan.md`) with current step and status
- [ ] All tests pass locally (`make local-ci-run`), weak=[]
- [ ] VS Code CI near/worst artifact present (job: `vscode`)
- [ ] No generated artifacts committed (dist/build/.mcp/dashboard/**, *.vsix)

## Notes

- PR body can reference `docs/releases/PR_DRAFT.md` for a fuller narrative.
