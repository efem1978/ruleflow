#!/usr/bin/env pwsh
set-strictmode -version latest
$ErrorActionPreference = 'Stop'

Push-Location (Join-Path $PSScriptRoot '..')

Write-Host "[uninstall] removing venv and build artifacts"
Remove-Item -Recurse -Force .mcp/venv -ErrorAction SilentlyContinue
Remove-Item -Force coverage.xml, cov*.json, pytest-junit.xml -ErrorAction SilentlyContinue

if (Get-Command code -ErrorAction SilentlyContinue) {
  Write-Host "[uninstall] uninstalling VS Code extension ruleflow.mcp-rules-assistant (best-effort)"
  code --uninstall-extension ruleflow.mcp-rules-assistant --force | Out-Null
}

Write-Host "[uninstall] done"
Pop-Location

