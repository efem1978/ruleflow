VS Code Extension

This extension provides a thin UI for the MCP Rules & Context Assistant and delegates logic to the local Python MCP Server.

Commands
- MCP: Open Panel — open the assistant panel (rules/coverage/CI)
- MCP: Commit (run checks)
- MCP: Push (run gates)
- MCP: Natural Command — fuzzy bilingual NL command palette

Multi-root & Environment
- Multi-root: the panel now shows the current workspace and allows selecting/switching project roots; switching updates the Python server context.
- One-click env: when opening the panel, if `.mcp/venv` or required tools are missing, it prompts to create and install via `env.prepare`.

Install
- Build or download the `.vsix`, then install via VS Code: Extensions → More… → Install from VSIX.
- Requires Python 3 on PATH (or set env `MCP_PYTHON_BIN`).

License & Trial
- Commercial license required. 7‑day free trial available.
- Activate using the CLI: `mcp-rules-assistant` (see repository docs for details).

Notes
- The server runs over stdio (no local HTTP/ports). Status is written to `.mcp/dashboard/*.json` for tooling/CI.
