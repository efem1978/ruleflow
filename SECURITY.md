# Security Policy

## Supported Versions

Security updates are provided on the `main` branch. If you discover a vulnerability, please report it following the instructions below.

## Reporting a Vulnerability

- Create a private disclosure by emailing the maintainer or opening a security advisory in the GitHub repository (Security tab → Report a vulnerability).
- Include:
  - Steps to reproduce and an impact assessment
  - Affected files / versions and suggested remediation
- We will acknowledge receipt within 3 business days and aim to provide a fix or mitigation within 14 days depending on severity.

## Scope

- This project ships a Python CLI + MCP server skeleton and a VS Code extension skeleton. Security issues may include:
  - Command injection, unsafe subprocess calls, or insecure file handling
  - Insecure defaults in CI/hook generation (e.g., allowing secrets to leak)
  - Vulnerabilities in example Dockerfile or security tool configurations

## Disclosure

- Please do not open public issues for security findings until a coordinated disclosure window is agreed and a fix is available.

