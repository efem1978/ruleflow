#!/usr/bin/env bash

# Universal MCP Rules Assistant Installer
# Supports: VSCode, JetBrains, Cursor, Windsurf, Neovim, Sublime Text, Visual Studio
# Cross-platform: macOS, Linux, Windows (WSL/Git Bash)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Environment detection
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos" ;;
        Linux*) echo "linux" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

detect_python() {
    for py in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$py" >/dev/null 2>&1; then
            local version=$($py --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            if [[ $(echo "$version >= 3.10" | bc -l 2>/dev/null || echo "0") == "1" ]]; then
                echo "$py"
                return 0
            fi
        fi
    done
    return 1
}

# Smart venv creation with PEP 668 handling
create_venv() {
    local python_cmd
    if ! python_cmd=$(detect_python); then
        log_error "Python 3.10+ not found. Please install Python 3.10 or higher."
        exit 1
    fi
    
    log_info "Using Python: $python_cmd ($(${python_cmd} --version))"
    
    # Try direct venv creation first
    if $python_cmd -m venv .mcp/venv 2>/dev/null; then
        log_success "Virtual environment created successfully"
        return 0
    fi
    
    # Handle PEP 668 restrictions
    log_warn "System-managed Python detected (PEP 668). Trying alternative methods..."
    
    # Try with --system-site-packages
    if $python_cmd -m venv --system-site-packages .mcp/venv 2>/dev/null; then
        log_success "Virtual environment created with system packages"
        return 0
    fi
    
    # Suggest pipx installation
    log_error "Cannot create virtual environment due to system restrictions."
    log_info "Please try one of these alternatives:"
    log_info "1. Install via pipx: pipx install -e ."
    log_info "2. Use conda: conda create -n mcp-rules python=3.11 && conda activate mcp-rules && pip install -e ."
    log_info "3. Use pyenv: pyenv install 3.11.0 && pyenv virtualenv 3.11.0 mcp-rules && pyenv activate mcp-rules"
    exit 1
}

# Install Python package with proper error handling
install_python_package() {
    log_info "Installing Python package..."
    
    if ! .mcp/venv/bin/python -m pip install -U pip; then
        log_error "Failed to upgrade pip"
        return 1
    fi
    
    # Install toolchain
    if ! .mcp/venv/bin/python -m pip install ruff black isort mypy bandit pytest pytest-cov pre-commit types-PyYAML cryptography; then
        log_warn "Some development tools failed to install, continuing..."
    fi
    
    # Install main package
    if ! .mcp/venv/bin/python -m pip install -e .; then
        log_error "Failed to install MCP Rules Assistant package"
        return 1
    fi
    
    log_success "Python package installed successfully"
    return 0
}

OS=$(detect_os)
log_info "Detected OS: $OS"

log_info "Creating virtual environment..."
create_venv

log_info "Installing Python package..."
if ! install_python_package; then
    log_error "Python package installation failed"
    exit 1
fi

# Initialize MCP configuration
initialize_mcp() {
    log_info "Initializing MCP configuration..."
    
    if ! .mcp/venv/bin/python -m mcp_rules_assistant.cli init; then
        log_error "Failed to initialize MCP configuration"
        return 1
    fi
    
    if ! .mcp/venv/bin/python -m mcp_rules_assistant.cli ingest-rules README.md docs/; then
        log_warn "Failed to ingest rules, continuing..."
    fi
    
    log_success "MCP configuration initialized"
    return 0
}

# Run tests and generate coverage
run_tests() {
    log_info "Running tests and generating coverage..."
    
    if PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .mcp/venv/bin/python -m pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml; then
        log_success "Tests passed and coverage generated"
    else
        log_warn "Some tests failed, continuing with installation..."
    fi
    
    .mcp/venv/bin/python -m mcp_rules_assistant.cli status-update --json >/dev/null 2>&1 || true
}

# Detect available IDEs
detect_ides() {
    local ides=()
    
    # VSCode variants
    if command -v code >/dev/null 2>&1; then
        ides+=("vscode")
    fi
    if command -v cursor >/dev/null 2>&1; then
        ides+=("cursor")
    fi
    if command -v windsurf >/dev/null 2>&1; then
        ides+=("windsurf")
    fi
    
    # JetBrains IDEs
    for ide in idea pycharm webstorm phpstorm goland clion rider; do
        if command -v "$ide" >/dev/null 2>&1; then
            ides+=("jetbrains-$ide")
        fi
    done
    
    # Other IDEs
    if command -v nvim >/dev/null 2>&1 || command -v vim >/dev/null 2>&1; then
        ides+=("neovim")
    fi
    if command -v subl >/dev/null 2>&1; then
        ides+=("sublime")
    fi
    
    printf '%s\n' "${ides[@]}"
}

# Install Neovim plugin
install_neovim_plugin() {
    log_info "Installing Neovim plugin..."
    
    # Create Neovim plugin directory
    mkdir -p ~/.config/nvim/lua/mcp-rules-assistant
    
    # Create basic Neovim plugin
    cat > ~/.config/nvim/lua/mcp-rules-assistant/init.lua << 'EOF'
local M = {}

function M.setup(opts)
    opts = opts or {}
    
    -- Create user commands
    vim.api.nvim_create_user_command('MCPStatus', function()
        vim.fn.system('source ' .. vim.fn.getcwd() .. '/.mcp/venv/bin/activate && mcp-rules-assistant status')
    end, {})
    
    vim.api.nvim_create_user_command('MCPRules', function()
        vim.fn.system('source ' .. vim.fn.getcwd() .. '/.mcp/venv/bin/activate && mcp-rules-assistant rules-ingest')
    end, {})
    
    vim.api.nvim_create_user_command('MCPCoverage', function()
        vim.fn.system('source ' .. vim.fn.getcwd() .. '/.mcp/venv/bin/activate && mcp-rules-assistant coverage-update')
    end, {})
    
    print("MCP Rules Assistant loaded")
end

return M
EOF
    
    # Add to init.lua if it exists
    if [ -f ~/.config/nvim/init.lua ]; then
        if ! grep -q "mcp-rules-assistant" ~/.config/nvim/init.lua; then
            echo "require('mcp-rules-assistant').setup()" >> ~/.config/nvim/init.lua
        fi
    fi
    
    log_success "Neovim plugin installed"
}

# Install VSCode extension
install_vscode_extension() {
    log_info "Building and installing VSCode extension..."
    
    if ! npm --prefix extensions/vscode run compile; then
        log_error "Failed to compile VSCode extension"
        return 1
    fi
    
    if ! npm --prefix extensions/vscode run package; then
        log_error "Failed to package VSCode extension"
        return 1
    fi
    
    local vsix_file="extensions/vscode/mcp-rules-assistant-0.2.6.vsix"
    if [[ ! -f "$vsix_file" ]]; then
        log_error "VSIX file not found: $vsix_file"
        return 1
    fi
    
    # Install for VSCode
    if command -v code >/dev/null 2>&1; then
        if code --install-extension "$vsix_file" --force; then
            log_success "VSCode extension installed"
        else
            log_error "Failed to install VSCode extension"
            return 1
        fi
    fi
    
    # Install for Cursor (uses same VSIX)
    if command -v cursor >/dev/null 2>&1; then
        if cursor --install-extension "$vsix_file" --force; then
            log_success "Cursor extension installed"
        else
            log_warn "Failed to install Cursor extension"
        fi
    fi
    
    # Install for Windsurf (uses same VSIX)
    if command -v windsurf >/dev/null 2>&1; then
        if windsurf --install-extension "$vsix_file" --force; then
            log_success "Windsurf extension installed"
        else
            log_warn "Failed to install Windsurf extension"
        fi
    fi
    
    return 0
}

log_info "Initializing MCP configuration..."
initialize_mcp

log_info "Running tests..."
run_tests

log_info "Detecting available IDEs..."
available_ides=($(detect_ides))
if [[ ${#available_ides[@]} -eq 0 ]]; then
    log_warn "No supported IDEs detected"
else
    log_info "Detected IDEs: ${available_ides[*]}"
fi

# Install IDE extensions
for ide in "${available_ides[@]}"; do
    case "$ide" in
        vscode|cursor|windsurf)
            install_vscode_extension
            ;;
        jetbrains-*)
            install_jetbrains_plugin "${ide#jetbrains-}"
            ;;
        neovim)
            install_neovim_plugin
            ;;
        sublime)
            install_sublime_plugin
            ;;
    esac
done

# Install JetBrains plugin
install_jetbrains_plugin() {
    local ide_name="$1"
    log_info "Installing JetBrains plugin for $ide_name..."
    
    # Try to build with Gradle first
    if command -v gradle >/dev/null 2>&1; then
        cd extensions/jetbrains
        
        # Use compatible Gradle version
        if ! [[ -f gradlew ]]; then
            gradle wrapper --gradle-version 7.6
        fi
        
        # Build the plugin
        if ./gradlew buildPlugin 2>/dev/null; then
            local plugin_zip=$(find build/distributions -name "*.zip" 2>/dev/null | head -1)
            if [[ -n "$plugin_zip" ]]; then
                log_success "JetBrains plugin built: $plugin_zip"
                
                # Try to auto-install for IntelliJ IDEA
                local idea_config_dir=""
                if [[ "$OS" == "macos" ]]; then
                    idea_config_dir="$HOME/Library/Application Support/JetBrains"
                elif [[ "$OS" == "linux" ]]; then
                    idea_config_dir="$HOME/.config/JetBrains"
                elif [[ "$OS" == "windows" ]]; then
                    idea_config_dir="$HOME/AppData/Roaming/JetBrains"
                fi
                
                if [[ -n "$idea_config_dir" && -d "$idea_config_dir" ]]; then
                    # Find the latest IntelliJ config directory
                    local latest_idea=$(find "$idea_config_dir" -maxdepth 1 -name "IntelliJIdea*" -type d | sort -V | tail -1)
                    if [[ -n "$latest_idea" ]]; then
                        local plugins_dir="$latest_idea/plugins"
                        mkdir -p "$plugins_dir"
                        
                        # Extract plugin to plugins directory
                        local plugin_name=$(basename "$plugin_zip" .zip)
                        if unzip -q "$plugin_zip" -d "$plugins_dir/$plugin_name"; then
                            log_success "JetBrains plugin auto-installed to $plugins_dir"
                        else
                            log_warn "Auto-installation failed, manual install required: $plugin_zip"
                        fi
                    else
                        log_warn "IntelliJ IDEA config not found, manual install required: $plugin_zip"
                    fi
                else
                    log_warn "JetBrains config directory not found, manual install required: $plugin_zip"
                fi
            else
                log_warn "JetBrains plugin build succeeded but no distribution found"
            fi
        else
            log_warn "JetBrains plugin build failed, trying simple installation..."
            # Create a simple plugin structure
            create_simple_jetbrains_plugin
        fi
        cd - >/dev/null
    else
        log_warn "Gradle not available, creating simple JetBrains integration..."
        create_simple_jetbrains_plugin
    fi
}

# Create simple JetBrains plugin without Gradle
create_simple_jetbrains_plugin() {
    log_info "Creating simple JetBrains integration..."
    
    local idea_config_dir=""
    if [[ "$OS" == "macos" ]]; then
        idea_config_dir="$HOME/Library/Application Support/JetBrains"
    elif [[ "$OS" == "linux" ]]; then
        idea_config_dir="$HOME/.config/JetBrains"
    elif [[ "$OS" == "windows" ]]; then
        idea_config_dir="$HOME/AppData/Roaming/JetBrains"
    fi
    
    if [[ -n "$idea_config_dir" ]]; then
        # Create external tools configuration
        local tools_dir="$idea_config_dir/tools"
        mkdir -p "$tools_dir"
        
        cat > "$tools_dir/MCP_Rules_Assistant.xml" << 'EOF'
<toolSet name="MCP Rules Assistant">
  <tool name="MCP Status" description="Check MCP Rules Assistant status" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="true" showConsoleOnStdErr="true" synchronizeAfterRun="true">
    <exec>
      <option name="COMMAND" value="$ProjectFileDir$/.mcp/venv/bin/python" />
      <option name="PARAMETERS" value="-m mcp_rules_assistant.cli status" />
      <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
    </exec>
  </tool>
  <tool name="MCP Rules Ingest" description="Ingest project rules" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="true" showConsoleOnStdErr="true" synchronizeAfterRun="true">
    <exec>
      <option name="COMMAND" value="$ProjectFileDir$/.mcp/venv/bin/python" />
      <option name="PARAMETERS" value="-m mcp_rules_assistant.cli rules-ingest" />
      <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
    </exec>
  </tool>
  <tool name="MCP Coverage Update" description="Update coverage analysis" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="true" showConsoleOnStdErr="true" synchronizeAfterRun="true">
    <exec>
      <option name="COMMAND" value="$ProjectFileDir$/.mcp/venv/bin/python" />
      <option name="PARAMETERS" value="-m mcp_rules_assistant.cli coverage-update" />
      <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
    </exec>
  </tool>
</toolSet>
EOF
        
        log_success "JetBrains external tools configured"
        log_info "Access via Tools -> External Tools -> MCP Rules Assistant"
    else
        log_warn "Could not configure JetBrains integration"
    fi
}

# Install Neovim plugin
install_neovim_plugin() {
    log_info "Setting up Neovim integration..."
    
    local nvim_config_dir
    if [[ "$OS" == "windows" ]]; then
        nvim_config_dir="$HOME/AppData/Local/nvim"
    else
        nvim_config_dir="$HOME/.config/nvim"
    fi
    
    mkdir -p "$nvim_config_dir/lua/mcp-rules"
    
    cat > "$nvim_config_dir/lua/mcp-rules/init.lua" << 'EOF'
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
    
    local python_bin = root .. "/.mcp/venv/bin/python"
    if vim.fn.executable(python_bin) == 0 then
        vim.notify("MCP not installed (run install-all.sh)", vim.log.levels.ERROR)
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
EOF
    
    log_success "Neovim plugin installed"
    log_info "Add to your init.lua: require('mcp-rules').setup()"
    log_info "Available commands: :MCPStatus, :MCPCoverage, :MCPIngest, :MCPGenerateCI"
}

# Install Sublime Text plugin
install_sublime_plugin() {
    log_info "Setting up Sublime Text integration..."
    
    local sublime_packages_dir
    case "$OS" in
        macos)
            sublime_packages_dir="$HOME/Library/Application Support/Sublime Text/Packages"
            ;;
        linux)
            sublime_packages_dir="$HOME/.config/sublime-text/Packages"
            ;;
        windows)
            sublime_packages_dir="$HOME/AppData/Roaming/Sublime Text/Packages"
            ;;
    esac
    
    if [[ ! -d "$sublime_packages_dir" ]]; then
        log_warn "Sublime Text packages directory not found: $sublime_packages_dir"
        return 1
    fi
    
    local plugin_dir="$sublime_packages_dir/MCP Rules Assistant"
    mkdir -p "$plugin_dir"
    
    cat > "$plugin_dir/mcp_rules.py" << 'EOF'
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
        
        # Get project folder
        folders = window.folders()
        if not folders:
            sublime.error_message("No project folder found")
            return
        
        project_dir = folders[0]
        venv_python = os.path.join(project_dir, ".mcp", "venv", "bin", "python")
        
        if not os.path.exists(venv_python):
            sublime.error_message("MCP virtual environment not found")
            return
        
        try:
            # Run MCP command
            result = subprocess.run([
                venv_python, "-m", "mcp_rules_assistant.cli"
            ] + cmd.split(), 
            cwd=project_dir, 
            capture_output=True, 
            text=True, 
            timeout=30
            )
            
            if result.returncode == 0:
                sublime.message_dialog(f"MCP Command Success:\n{result.stdout}")
            else:
                sublime.error_message(f"MCP Command Failed:\n{result.stderr}")
                
        except subprocess.TimeoutExpired:
            sublime.error_message("MCP command timed out")
        except Exception as e:
            sublime.error_message(f"Error running MCP command: {str(e)}")
EOF
    
    # Create menu configuration
    cat > "$plugin_dir/Main.sublime-menu" << 'EOF'
[
    {
        "caption": "Tools",
        "mnemonic": "T",
        "id": "tools",
        "children":
        [
            {
                "caption": "MCP Rules Assistant",
                "id": "mcp_rules",
                "children":
                [
                    {
                        "caption": "Status Update",
                        "command": "mcp_status"
                    },
                    {
                        "caption": "Coverage Analysis", 
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
EOF

    # Create command palette entries
    cat > "$plugin_dir/Default.sublime-commands" << 'EOF'
[
    {
        "caption": "MCP: Status Update",
        "command": "mcp_status"
    },
    {
        "caption": "MCP: Coverage Analysis",
        "command": "mcp_coverage"
    },
    {
        "caption": "MCP: Ingest Rules", 
        "command": "mcp_ingest"
    },
    {
        "caption": "MCP: Generate CI",
        "command": "mcp_generate_ci"
    }
]
EOF
    
    log_success "Sublime Text plugin installed"
    log_info "Access via Tools -> MCP Rules Assistant or Command Palette (Ctrl+Shift+P)"
}
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
EOF
    
    log_success "Sublime Text plugin installed"
    log_info "Available in Tools -> MCP Rules Assistant menu"
}

# Comprehensive validation
validate_installation() {
    log_info "Validating installation..."
    
    local validation_passed=true
    
    # Check CLI
    if .mcp/venv/bin/python -m mcp_rules_assistant.cli version >/dev/null 2>&1; then
        log_success "✓ CLI working"
    else
        log_error "✗ CLI not working"
        validation_passed=false
    fi
    
    # Check configuration
    if [[ -f ".mcp/assistant.yaml" ]]; then
        log_success "✓ Configuration file exists"
    else
        log_error "✗ Configuration file missing"
        validation_passed=false
    fi
    
    # Check IDE extensions
    local installed_extensions=()
    
    if command -v code >/dev/null 2>&1; then
        if code --list-extensions | grep -qi 'ruleflow.mcp-rules-assistant'; then
            installed_extensions+=("VSCode")
        fi
    fi
    
    if command -v cursor >/dev/null 2>&1; then
        if cursor --list-extensions | grep -qi 'ruleflow.mcp-rules-assistant'; then
            installed_extensions+=("Cursor")
        fi
    fi
    
    if [[ -f "$HOME/.config/nvim/lua/mcp-rules/init.lua" ]] || [[ -f "$HOME/AppData/Local/nvim/lua/mcp-rules/init.lua" ]]; then
        installed_extensions+=("Neovim")
    fi
    
    if [[ ${#installed_extensions[@]} -gt 0 ]]; then
        log_success "✓ IDE extensions: ${installed_extensions[*]}"
    else
        log_warn "⚠ No IDE extensions installed"
    fi
    
    # Test basic functionality
    if .mcp/venv/bin/python -m mcp_rules_assistant.cli status-update --json >/dev/null 2>&1; then
        log_success "✓ Basic functionality working"
    else
        log_error "✗ Basic functionality failed"
        validation_passed=false
    fi
    
    if $validation_passed; then
        log_success "🎉 Installation completed successfully!"
        log_info "Next steps:"
        log_info "1. Open your IDE and look for MCP Rules Assistant commands"
        log_info "2. VSCode: Command Palette -> 'RuleFlow: Open Panel'"
        log_info "3. Neovim: :MCPStatus, :MCPCoverage, etc."
        log_info "4. Sublime: Tools -> MCP Rules Assistant"
    else
        log_error "❌ Installation validation failed"
        exit 1
    fi
}

validate_installation
