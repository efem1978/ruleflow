# Universal MCP Rules Assistant Installer for Windows
# Supports: VSCode, JetBrains, Cursor, Windsurf, Neovim, Sublime Text, Visual Studio
# PowerShell 5.1+ compatible

param(
    [switch]$Verbose,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

# Color output functions
function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Blue }
function Write-Success { param($Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

# Detect Python
function Find-Python {
    $pythonCandidates = @("python3.12", "python3.11", "python3.10", "python3", "python", "py")
    
    foreach ($py in $pythonCandidates) {
        try {
            $version = & $py --version 2>&1
            if ($version -match "Python (\d+)\.(\d+)") {
                $major = [int]$matches[1]
                $minor = [int]$matches[2]
                if ($major -eq 3 -and $minor -ge 10) {
                    return $py
                }
            }
        } catch {
            continue
        }
    }
    return $null
}

# Smart venv creation with error handling
function New-VirtualEnvironment {
    $pythonCmd = Find-Python
    if (-not $pythonCmd) {
        Write-Error "Python 3.10+ not found. Please install Python 3.10 or higher."
        exit 1
    }
    
    $pythonVersion = & $pythonCmd --version
    Write-Info "Using Python: $pythonCmd ($pythonVersion)"
    
    # Try direct venv creation first
    try {
        & $pythonCmd -m venv .mcp/venv 2>$null
        Write-Success "Virtual environment created successfully"
        return $pythonCmd
    } catch {
        Write-Warn "Standard venv creation failed. Trying alternative methods..."
    }
    
    # Try with --system-site-packages
    try {
        & $pythonCmd -m venv --system-site-packages .mcp/venv 2>$null
        Write-Success "Virtual environment created with system packages"
        return $pythonCmd
    } catch {
        Write-Error "Cannot create virtual environment. Please try:"
        Write-Info "1. Install via pipx: pipx install -e ."
        Write-Info "2. Use conda: conda create -n mcp-rules python=3.11"
        Write-Info "3. Run as administrator"
        exit 1
    }
}

# Install Python package with proper error handling
function Install-PythonPackage {
    Write-Info "Installing Python package..."
    
    $pythonBin = ".mcp/venv/Scripts/python.exe"
    
    try {
        & $pythonBin -m pip install -U pip
        Write-Success "Pip upgraded successfully"
    } catch {
        Write-Error "Failed to upgrade pip"
        return $false
    }
    
    # Install toolchain
    try {
        & $pythonBin -m pip install ruff black isort mypy bandit pytest pytest-cov pre-commit types-PyYAML cryptography
    } catch {
        Write-Warn "Some development tools failed to install, continuing..."
    }
    
    # Install main package
    try {
        & $pythonBin -m pip install -e .
        Write-Success "Python package installed successfully"
        return $true
    } catch {
        Write-Error "Failed to install MCP Rules Assistant package"
        return $false
    }
}

# Initialize MCP configuration
function Initialize-MCP {
    Write-Info "Initializing MCP configuration..."
    
    $pythonBin = ".mcp/venv/Scripts/python.exe"
    
    try {
        & $pythonBin -m mcp_rules_assistant.cli init
        Write-Success "MCP configuration initialized"
    } catch {
        Write-Error "Failed to initialize MCP configuration"
        return $false
    }
    
    try {
        & $pythonBin -m mcp_rules_assistant.cli ingest-rules README.md docs/
    } catch {
        Write-Warn "Failed to ingest rules, continuing..."
    }
    
    return $true
}

# Run tests and generate coverage
function Invoke-Tests {
    if ($SkipTests) {
        Write-Info "Skipping tests as requested"
        return
    }
    
    Write-Info "Running tests and generating coverage..."
    
    $pythonBin = ".mcp/venv/Scripts/python.exe"
    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
    
    try {
        & $pythonBin -m pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml
        Write-Success "Tests passed and coverage generated"
    } catch {
        Write-Warn "Some tests failed, continuing with installation..."
    }
    
    try {
        & $pythonBin -m mcp_rules_assistant.cli status-update --json | Out-Null
    } catch {
        Write-Warn "Status update failed"
    }
}

# Detect available IDEs
function Get-AvailableIDEs {
    $ides = @()
    
    # VSCode variants
    if (Get-Command "code" -ErrorAction SilentlyContinue) { $ides += "vscode" }
    if (Get-Command "cursor" -ErrorAction SilentlyContinue) { $ides += "cursor" }
    if (Get-Command "windsurf" -ErrorAction SilentlyContinue) { $ides += "windsurf" }
    
    # JetBrains IDEs
    $jetbrainsIdes = @("idea64", "pycharm64", "webstorm64", "phpstorm64", "goland64", "clion64", "rider64")
    foreach ($ide in $jetbrainsIdes) {
        if (Get-Command $ide -ErrorAction SilentlyContinue) {
            $ides += "jetbrains-$ide"
        }
    }
    
    # Other IDEs
    if (Get-Command "nvim" -ErrorAction SilentlyContinue) { $ides += "neovim" }
    if (Get-Command "subl" -ErrorAction SilentlyContinue) { $ides += "sublime" }
    if (Get-Command "devenv" -ErrorAction SilentlyContinue) { $ides += "visualstudio" }
    
    return $ides
}

# Install VSCode extension
function Install-VSCodeExtension {
    Write-Info "Building and installing VSCode extension..."
    
    if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
        Write-Warn "npm not found, skipping VSCode extension build"
        return $false
    }
    
    try {
        & npm --prefix extensions/vscode run compile
        & npm --prefix extensions/vscode run package
    } catch {
        Write-Error "Failed to build VSCode extension"
        return $false
    }
    
    $vsixFile = "extensions/vscode/mcp-rules-assistant-0.2.6.vsix"
    if (-not (Test-Path $vsixFile)) {
        Write-Error "VSIX file not found: $vsixFile"
        return $false
    }
    
    # Install for VSCode
    if (Get-Command "code" -ErrorAction SilentlyContinue) {
        try {
            & code --install-extension $vsixFile --force
            Write-Success "VSCode extension installed"
        } catch {
            Write-Error "Failed to install VSCode extension"
            return $false
        }
    }
    
    # Install for Cursor
    if (Get-Command "cursor" -ErrorAction SilentlyContinue) {
        try {
            & cursor --install-extension $vsixFile --force
            Write-Success "Cursor extension installed"
        } catch {
            Write-Warn "Failed to install Cursor extension"
        }
    }
    
    # Install for Windsurf
    if (Get-Command "windsurf" -ErrorAction SilentlyContinue) {
        try {
            & windsurf --install-extension $vsixFile --force
            Write-Success "Windsurf extension installed"
        } catch {
            Write-Warn "Failed to install Windsurf extension"
        }
    }
    
    return $true
}

# Install Neovim plugin
function Install-NeovimPlugin {
    Write-Info "Setting up Neovim integration..."
    
    $nvimConfigDir = "$env:LOCALAPPDATA/nvim"
    if (-not (Test-Path $nvimConfigDir)) {
        $nvimConfigDir = "$env:USERPROFILE/.config/nvim"
    }
    
    $pluginDir = "$nvimConfigDir/lua/mcp-rules"
    New-Item -ItemType Directory -Path $pluginDir -Force | Out-Null
    
    $luaContent = @'
-- MCP Rules Assistant for Neovim
local M = {}

-- Get project root
local function get_project_root()
    local cwd = vim.fn.getcwd()
    local mcp_dir = cwd .. "/.mcp"
    if vim.fn.isdirectory(mcp_dir) == 1 then
        return cwd
    end
    return nil
end

-- Execute MCP command
local function exec_mcp_cmd(cmd)
    local root = get_project_root()
    if not root then
        vim.notify("MCP project not found (.mcp directory missing)", vim.log.levels.ERROR)
        return
    end
    
    local python_bin = root .. "/.mcp/venv/Scripts/python.exe"
    if vim.fn.executable(python_bin) == 0 then
        vim.notify("MCP not installed (run install-all-windows.ps1)", vim.log.levels.ERROR)
        return
    end
    
    local full_cmd = python_bin .. " -m mcp_rules_assistant.cli " .. cmd
    vim.fn.system(full_cmd)
end

-- Commands
M.status_update = function() exec_mcp_cmd("status-update") end
M.coverage = function() exec_mcp_cmd("coverage") end
M.ingest_rules = function() exec_mcp_cmd("ingest-rules README.md docs/") end
M.generate_ci = function() exec_mcp_cmd("generate-ci") end

-- Setup function
M.setup = function()
    vim.api.nvim_create_user_command('MCPStatus', M.status_update, {})
    vim.api.nvim_create_user_command('MCPCoverage', M.coverage, {})
    vim.api.nvim_create_user_command('MCPIngest', M.ingest_rules, {})
    vim.api.nvim_create_user_command('MCPGenerateCI', M.generate_ci, {})
end

return M
'@
    
    Set-Content -Path "$pluginDir/init.lua" -Value $luaContent -Encoding UTF8
    Write-Success "Neovim plugin installed"
    Write-Info "Add to your init.lua: require('mcp-rules').setup()"
    Write-Info "Available commands: :MCPStatus, :MCPCoverage, :MCPIngest, :MCPGenerateCI"
}

# Install Sublime Text plugin
function Install-SublimePlugin {
    Write-Info "Setting up Sublime Text integration..."
    
    $sublimePackagesDir = "$env:APPDATA/Sublime Text/Packages"
    if (-not (Test-Path $sublimePackagesDir)) {
        Write-Warn "Sublime Text packages directory not found: $sublimePackagesDir"
        return $false
    }
    
    $pluginDir = "$sublimePackagesDir/MCP Rules Assistant"
    New-Item -ItemType Directory -Path $pluginDir -Force | Out-Null
    
    $pythonContent = @'
import sublime
import sublime_plugin
import subprocess
import os

class McpStatusCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.run_mcp_command("status-update")

class McpCoverageCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.run_mcp_command("coverage")

class McpIngestCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.run_mcp_command("ingest-rules README.md docs/")

class McpGenerateCiCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.run_mcp_command("generate-ci")

def run_mcp_command(self, cmd):
    window = self.view.window()
    if not window:
        return
    
    folders = window.folders()
    if not folders:
        sublime.error_message("No project folder open")
        return
    
    project_root = folders[0]
    mcp_dir = os.path.join(project_root, ".mcp")
    
    if not os.path.isdir(mcp_dir):
        sublime.error_message("MCP project not found (.mcp directory missing)")
        return
    
    python_bin = os.path.join(mcp_dir, "venv", "Scripts", "python.exe")
    if not os.path.isfile(python_bin):
        sublime.error_message("MCP not installed (run install-all-windows.ps1)")
        return
    
    full_cmd = [python_bin, "-m", "mcp_rules_assistant.cli"] + cmd.split()
    
    try:
        result = subprocess.run(full_cmd, cwd=project_root, capture_output=True, text=True)
        if result.returncode == 0:
            sublime.message_dialog(f"MCP command completed:\n{result.stdout}")
        else:
            sublime.error_message(f"MCP command failed:\n{result.stderr}")
    except Exception as e:
        sublime.error_message(f"Failed to run MCP command: {str(e)}")
'@
    
    Set-Content -Path "$pluginDir/mcp_rules.py" -Value $pythonContent -Encoding UTF8
    
    $menuContent = @'
[
    {
        "caption": "Tools",
        "mnemonic": "T",
        "id": "tools",
        "children":
        [
            {
                "caption": "MCP Rules Assistant",
                "children":
                [
                    {
                        "caption": "Status Update",
                        "command": "mcp_status"
                    },
                    {
                        "caption": "Coverage Report",
                        "command": "mcp_coverage"
                    },
                    {
                        "caption": "Ingest Rules",
                        "command": "mcp_ingest"
                    },
                    {
                        "caption": "Generate CI",
                        "command": "mcp_generate_ci"
                    }
                ]
            }
        ]
    }
]
'@
    
    Set-Content -Path "$pluginDir/Main.sublime-menu" -Value $menuContent -Encoding UTF8
    Write-Success "Sublime Text plugin installed"
    Write-Info "Available in Tools -> MCP Rules Assistant menu"
}

# Comprehensive validation
function Test-Installation {
    Write-Info "Validating installation..."
    
    $validationPassed = $true
    $pythonBin = ".mcp/venv/Scripts/python.exe"
    
    # Check CLI
    try {
        & $pythonBin -m mcp_rules_assistant.cli version | Out-Null
        Write-Success "✓ CLI working"
    } catch {
        Write-Error "✗ CLI not working"
        $validationPassed = $false
    }
    
    # Check configuration
    if (Test-Path ".mcp/assistant.yaml") {
        Write-Success "✓ Configuration file exists"
    } else {
        Write-Error "✗ Configuration file missing"
        $validationPassed = $false
    }
    
    # Check IDE extensions
    $installedExtensions = @()
    
    if (Get-Command "code" -ErrorAction SilentlyContinue) {
        $extensions = & code --list-extensions 2>$null
        if ($extensions -match 'ruleflow.mcp-rules-assistant') {
            $installedExtensions += "VSCode"
        }
    }
    
    if (Get-Command "cursor" -ErrorAction SilentlyContinue) {
        $extensions = & cursor --list-extensions 2>$null
        if ($extensions -match 'ruleflow.mcp-rules-assistant') {
            $installedExtensions += "Cursor"
        }
    }
    
    if (Test-Path "$env:LOCALAPPDATA/nvim/lua/mcp-rules/init.lua") {
        $installedExtensions += "Neovim"
    }
    
    if ($installedExtensions.Count -gt 0) {
        Write-Success "✓ IDE extensions: $($installedExtensions -join ', ')"
    } else {
        Write-Warn "⚠ No IDE extensions installed"
    }
    
    # Test basic functionality
    try {
        & $pythonBin -m mcp_rules_assistant.cli status-update --json | Out-Null
        Write-Success "✓ Basic functionality working"
    } catch {
        Write-Error "✗ Basic functionality failed"
        $validationPassed = $false
    }
    
    if ($validationPassed) {
        Write-Success "🎉 Installation completed successfully!"
        Write-Info "Next steps:"
        Write-Info "1. Open your IDE and look for MCP Rules Assistant commands"
        Write-Info "2. VSCode: Command Palette -> 'RuleFlow: Open Panel'"
        Write-Info "3. Neovim: :MCPStatus, :MCPCoverage, etc."
        Write-Info "4. Sublime: Tools -> MCP Rules Assistant"
    } else {
        Write-Error "❌ Installation validation failed"
        exit 1
    }
}

# Main execution
Write-Info "Detected OS: Windows"

Write-Info "Creating virtual environment..."
$pythonCmd = New-VirtualEnvironment

Write-Info "Installing Python package..."
if (-not (Install-PythonPackage)) {
    Write-Error "Python package installation failed"
    exit 1
}

Write-Info "Initializing MCP configuration..."
if (-not (Initialize-MCP)) {
    Write-Error "MCP initialization failed"
    exit 1
}

Write-Info "Running tests..."
Invoke-Tests

Write-Info "Detecting available IDEs..."
$availableIDEs = Get-AvailableIDEs
if ($availableIDEs.Count -eq 0) {
    Write-Warn "No supported IDEs detected"
} else {
    Write-Info "Detected IDEs: $($availableIDEs -join ', ')"
}

# Install IDE extensions
foreach ($ide in $availableIDEs) {
    switch -Regex ($ide) {
        "vscode|cursor|windsurf" {
            Install-VSCodeExtension
            break
        }
        "jetbrains-.*" {
            Write-Info "JetBrains plugin requires manual installation"
            Write-Info "Build plugin with: docker compose run --rm jb-package"
            break
        }
        "neovim" {
            Install-NeovimPlugin
            break
        }
        "sublime" {
            Install-SublimePlugin
            break
        }
    }
}

Test-Installation
