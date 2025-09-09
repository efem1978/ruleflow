# Release vX.Y.Z — YYYY-MM-DD

Highlights
- Short bullets of key improvements (2–5 items)

Changes
- Feature: ...
- Fix: ...
- Docs: ...
- CI: ...

Quality & Gates
- Python coverage (core≥98%, others≥95%): Passed; weak files: 0
- VS Code coverage gate: ≥80% (LCOV)
- SAST: semgrep 1.91.x; Dockerfile lint: hadolint 2.12.0
- Mutation (optional): non-blocking unless strict

Compatibility
- Breaking changes: None/Describe
- Deprecations: None/Describe

How to Upgrade
- pip install -U mcp-rules-assistant
- VS Code: install updated VSIX (if distributed)

IDE & MCP
- MCP tools/resources stable; JSON-RPC error codes: -32601/-32602/-32603/-32000/-32001
- VS Code: panel improvements; NL commands; lcov gate in CI
- JetBrains: ToolWindow MVP; storyboard available for environments without IDE

Security & Licensing
- No telemetry; local artifacts only (.mcp)
- License: 7-day trial; offline activation supported; release harden gate available

Artifacts
- Python: wheels/tar.gz in GitHub Releases
- VS Code: mcp-rules-assistant.vsix (optional)

Known Issues
- List any known limitations

