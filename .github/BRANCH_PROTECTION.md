Branch Protection – Quick Setup

1) Open branch protection rules for this repo
- URL: https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/settings/branches

2) Add rule
- Branch name pattern: main
- Checks to require (enable after CI has run at least once):
  - GitHub Actions
    - build (3.10)
    - build (3.11)
    - build (3.12)
    - prepare
  - Codecov (after installing Codecov App)
    - codecov/project
    - codecov/patch
- Options
  - [x] Require status checks to pass before merging
  - [x] Require branches to be up to date before merging
  - [optional] Require conversation resolution

3) Verify
- Push or re-run CI: https://github.com/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/actions
- Coverage dashboard (Codecov): https://app.codecov.io/gh/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool

Notes
- The CI enforces coverage ≥95% (pytest-cov). Codecov statuses are informational by default (codecov.yml) to avoid blocking; you can make them required after validating.
