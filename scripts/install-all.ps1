#!/usr/bin/env pwsh
set-strictmode -version latest
$ErrorActionPreference = 'Stop'

function Exec($cmd, $args) {
  Write-Host "[install] $cmd $($args -join ' ')"
  & $cmd @args
}

Push-Location (Join-Path $PSScriptRoot '..')

Write-Host "[install] create venv"
Exec python -m venv .mcp/venv

$py = if ($IsWindows) { ".mcp/venv/Scripts/python.exe" } else { ".mcp/venv/bin/python" }

Write-Host "[install] upgrade pip"
& $py -m pip install -U pip | Out-Null

Write-Host "[install] toolchain"
& $py -m pip install ruff black isort mypy bandit pytest pytest-cov pre-commit types-PyYAML cryptography | Out-Null

Write-Host "[install] project (editable)"
& $py -m pip install -e . | Out-Null

Write-Host "[install] init + ingest rules"
& $py -m mcp_rules_assistant.cli init | Out-Null
& $py -m mcp_rules_assistant.cli ingest-rules README.md docs/ | Out-Null

Write-Host "[install] tests + coverage"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& $py -m pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml | Out-Null
& $py -m mcp_rules_assistant.cli status-update --json | Out-Null

Write-Host "[install] VS Code extension build + install"
if (Get-Command npm -ErrorAction SilentlyContinue) {
  Exec npm --prefix extensions/vscode run compile
  Exec npm --prefix extensions/vscode run package
  $vsix = "extensions/vscode/mcp-rules-assistant-0.2.5.vsix"
  if (Test-Path $vsix) {
    if (Get-Command code -ErrorAction SilentlyContinue) {
      Exec code --install-extension $vsix --force
      Write-Host "[install] VS Code extension installed: $vsix"
    } else {
      Write-Host "[install] vscode 'code' CLI not found; skipped install"
    }
  } else {
    Write-Host "[install] VSIX not found; skipped"
  }
} else {
  Write-Host "[install] npm not available; skipped VS Code packaging"
}

# Validation summary
Write-Host "[install] validating..."
$okCli = (& $py -m mcp_rules_assistant.cli version) -ne $null
$okStatus = Test-Path ".mcp/dashboard/status.json"
$okVsix = $(if (Get-Command code -ErrorAction SilentlyContinue) { (code --list-extensions) -match 'ruleflow.mcp-rules-assistant' } else { $false })
Write-Host "- CLI: $okCli"
Write-Host "- Status: $okStatus"
Write-Host "- VSIX installed: $okVsix"

Write-Host "[install] done"
Pop-Location

