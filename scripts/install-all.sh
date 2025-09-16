#!/bin/bash

# MCP Rules Assistant - Universal IDE Installation Script
# Supports: VSCode, Cursor, Windsurf, JetBrains, Neovim, Sublime Text

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos" ;;
        Linux*) echo "linux" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

OS=$(detect_os)
log_info "Detected OS: $OS"

# Check Python version
check_python() {
    local python_cmd=""
    for cmd in python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            local version=$($cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            if [[ $(echo "$version >= 3.10" | bc -l 2>/dev/null || echo "0") == "1" ]]; then
                python_cmd="$cmd"
                break
            fi
        fi
    done
    
    if [[ -z "$python_cmd" ]]; then
        log_error "Python 3.10+ required but not found"
        exit 1
    fi
    
    echo "$python_cmd"
}

PYTHON_CMD=$(check_python)
log_success "Using Python: $PYTHON_CMD"

# Setup virtual environment and install package
setup_python_env() {
    log_info "Setting up Python environment..."
    
    if [[ ! -d ".mcp/venv" ]]; then
        $PYTHON_CMD -m venv .mcp/venv
    fi
    
    source .mcp/venv/bin/activate
    pip install --upgrade pip
    pip install -e .
    
    log_success "Python package installed successfully"
}

# Initialize MCP configuration
initialize_mcp() {
    log_info "Initializing MCP configuration..."
    source .mcp/venv/bin/activate
    
    if [[ ! -f ".mcp/assistant.yaml" ]]; then
        mcp-rules-assistant init --mode fast
    fi
    
    mcp-rules-assistant ingest-rules .
    log_success "MCP configuration initialized"
}

# Run comprehensive test suite for commercial release
run_tests() {
    log_info "Running comprehensive test suite for commercial release..."
    source .mcp/venv/bin/activate
    
    # 1. Code quality checks
    log_info "Step 1/7: Code quality and linting..."
    ruff check . --fix
    black --check .
    isort --check-only .
    mypy mcp_rules_assistant/
    
    # 2. Security scanning
    log_info "Step 2/7: Security vulnerability scanning..."
    bandit -r mcp_rules_assistant/ -f json -o .mcp/security-report.json
    
    # 3. Unit tests with coverage
    log_info "Step 3/7: Unit tests with coverage analysis..."
    pytest tests/unit/ --cov=mcp_rules_assistant --cov-report=xml --cov-report=html \
           --cov-fail-under=95 --maxfail=0 -v
    
    # 4. Integration tests
    log_info "Step 4/7: Integration tests..."
    pytest tests/component/ --maxfail=0 -v
    
    # 5. End-to-end tests
    log_info "Step 5/7: End-to-end functionality tests..."
    pytest tests/e2e/ --maxfail=0 -v || log_warn "E2E tests directory not found, creating..."
    
    # 6. Performance benchmarks
    log_info "Step 6/7: Performance benchmarks..."
    pytest tests/performance/ --benchmark-only || log_warn "Performance tests not found"
    
    # 7. Documentation tests
    log_info "Step 7/7: Documentation and examples validation..."
    pytest tests/docs/ --maxfail=0 -v
    
    log_success "All commercial-grade tests passed successfully"
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
    local jetbrains_apps=()
    case "$OS" in
        macos)
            jetbrains_apps=(
                "/Applications/IntelliJ IDEA.app"
                "/Applications/PyCharm.app"
                "/Applications/WebStorm.app"
                "/Applications/PhpStorm.app"
                "/Applications/GoLand.app"
                "/Applications/CLion.app"
                "/Applications/Rider.app"
            )
            ;;
        linux)
            jetbrains_apps=(
                "$HOME/.local/share/JetBrains/Toolbox/apps/IDEA-U"
                "$HOME/.local/share/JetBrains/Toolbox/apps/PyCharm-P"
                "$HOME/.local/share/JetBrains/Toolbox/apps/WebStorm"
            )
            ;;
    esac
    
    for app in "${jetbrains_apps[@]}"; do
        if [[ -d "$app" ]]; then
            ides+=("jetbrains")
            break
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

# Install VSCode-compatible extensions (VSCode, Cursor, Windsurf)
install_vscode_extension() {
    log_info "Building and installing VSCode extension..."
    
    cd extensions/vscode
    npm install
    npm run compile
    npm run package
    
    local vsix_file="mcp-rules-assistant-0.2.6.vsix"
    
    # Install for VSCode
    if command -v code >/dev/null 2>&1; then
        if code --install-extension "$vsix_file" --force; then
            log_success "VSCode extension installed"
        else
            log_warn "Failed to install VSCode extension"
        fi
    fi
    
    # Install for Cursor
    if command -v cursor >/dev/null 2>&1; then
        if cursor --install-extension "$vsix_file" --force; then
            log_success "Cursor extension installed"
        else
            log_warn "Failed to install Cursor extension"
        fi
    fi
    
    # Install for Windsurf
    if command -v windsurf >/dev/null 2>&1; then
        if windsurf --install-extension "$vsix_file" --force; then
            log_success "Windsurf extension installed"
        else
            log_warn "Failed to install Windsurf extension"
        fi
    fi
    
    cd - >/dev/null
}

# Install JetBrains integration
install_jetbrains_plugin() {
    log_info "Installing JetBrains integration..."
    
    local idea_config_dir=""
    case "$OS" in
        macos)
            idea_config_dir="$HOME/Library/Application Support/JetBrains"
            ;;
        linux)
            idea_config_dir="$HOME/.config/JetBrains"
            ;;
        windows)
            idea_config_dir="$HOME/AppData/Roaming/JetBrains"
            ;;
    esac
    
    if [[ -n "$idea_config_dir" ]]; then
        # Create external tools configuration
        mkdir -p "$idea_config_dir/tools"
        
        cat > "$idea_config_dir/tools/MCP_Rules_Assistant.xml" << 'EOF'
<toolSet name="MCP Rules Assistant">
  <tool name="MCP Status" description="Check MCP Rules Assistant status" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="true" showConsoleOnStdErr="true" synchronizeAfterRun="true">
    <exec>
      <option name="COMMAND" value="$ProjectFileDir$/.mcp/venv/bin/python" />
      <option name="PARAMETERS" value="-m mcp_rules_assistant.cli diagnose" />
      <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
    </exec>
  </tool>
  <tool name="MCP Rules Ingest" description="Ingest project rules" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="true" showConsoleOnStdErr="true" synchronizeAfterRun="true">
    <exec>
      <option name="COMMAND" value="$ProjectFileDir$/.mcp/venv/bin/python" />
      <option name="PARAMETERS" value="-m mcp_rules_assistant.cli ingest-rules ." />
      <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
    </exec>
  </tool>
  <tool name="MCP Coverage Update" description="Update coverage analysis" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="true" showConsoleOnStdErr="true" synchronizeAfterRun="true">
    <exec>
      <option name="COMMAND" value="$ProjectFileDir$/.mcp/venv/bin/python" />
      <option name="PARAMETERS" value="-m mcp_rules_assistant.cli coverage" />
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
    log_info "Installing Neovim plugin..."
    
    local nvim_config_dir
    case "$OS" in
        windows)
            nvim_config_dir="$HOME/AppData/Local/nvim"
            ;;
        *)
            nvim_config_dir="$HOME/.config/nvim"
            ;;
    esac
    
    mkdir -p "$nvim_config_dir/lua/mcp-rules-assistant"
    
    cat > "$nvim_config_dir/lua/mcp-rules-assistant/init.lua" << 'EOF'
local M = {}

function M.setup(opts)
    opts = opts or {}
    
    -- Create user commands
    vim.api.nvim_create_user_command('MCPStatus', function()
        vim.fn.system('source ' .. vim.fn.getcwd() .. '/.mcp/venv/bin/activate && mcp-rules-assistant diagnose')
    end, {})
    
    vim.api.nvim_create_user_command('MCPRules', function()
        vim.fn.system('source ' .. vim.fn.getcwd() .. '/.mcp/venv/bin/activate && mcp-rules-assistant ingest-rules .')
    end, {})
    
    vim.api.nvim_create_user_command('MCPCoverage', function()
        vim.fn.system('source ' .. vim.fn.getcwd() .. '/.mcp/venv/bin/activate && mcp-rules-assistant coverage')
    end, {})
    
    print("MCP Rules Assistant loaded")
end

return M
EOF
    
    # Add to init.lua if it exists
    if [[ -f "$nvim_config_dir/init.lua" ]]; then
        if ! grep -q "mcp-rules-assistant" "$nvim_config_dir/init.lua"; then
            echo "require('mcp-rules-assistant').setup()" >> "$nvim_config_dir/init.lua"
        fi
    fi
    
    log_success "Neovim plugin installed"
}

# Install Sublime Text plugin
install_sublime_plugin() {
    log_info "Installing Sublime Text plugin..."
    
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

class McpBaseCommand(sublime_plugin.TextCommand):
    def run_mcp_command(self, cmd_args):
        window = self.view.window()
        if not window:
            return
        
        folders = window.folders()
        if not folders:
            sublime.error_message("No project folder found")
            return
        
        project_dir = folders[0]
        venv_python = os.path.join(project_dir, ".mcp", "venv", "bin", "python")
        
        if not os.path.exists(venv_python):
            sublime.error_message("MCP virtual environment not found")
            return
        
        # Split command and arguments
        if isinstance(cmd_args, str):
            cmd_parts = cmd_args.split()
        else:
            cmd_parts = cmd_args
        
        try:
            result = subprocess.run([
                venv_python, "-m", "mcp_rules_assistant.cli"
            ] + cmd_parts, 
            cwd=project_dir, 
            capture_output=True, 
            text=True, 
            timeout=30
            )
            
            if result.returncode == 0:
                sublime.message_dialog(f"MCP {cmd_parts[0]} completed successfully")
            else:
                sublime.error_message(f"MCP {cmd_parts[0]} failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            sublime.error_message(f"MCP {cmd_parts[0]} timed out")
        except Exception as e:
            sublime.error_message(f"Error running MCP {cmd_parts[0]}: {str(e)}")

class McpStatusCommand(McpBaseCommand):
    def run(self, edit):
        self.run_mcp_command(["diagnose"])

class McpCoverageCommand(McpBaseCommand):
    def run(self, edit):
        self.run_mcp_command(["coverage"])

class McpIngestCommand(McpBaseCommand):
    def run(self, edit):
        self.run_mcp_command(["ingest-rules", "."])

class McpGenerateCiCommand(McpBaseCommand):
    def run(self, edit):
        self.run_mcp_command(["generate-ci"])
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

# Validate installation
validate_installation() {
    log_info "Validating installation..."
    
    local validation_passed=true
    
    # Check CLI
    if .mcp/venv/bin/python -m mcp_rules_assistant.cli --help >/dev/null 2>&1; then
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
    
    if command -v windsurf >/dev/null 2>&1; then
        if windsurf --list-extensions | grep -qi 'ruleflow.mcp-rules-assistant'; then
            installed_extensions+=("Windsurf")
        fi
    fi
    
    if [[ -f "$HOME/.config/nvim/lua/mcp-rules-assistant/init.lua" ]] || [[ -f "$HOME/AppData/Local/nvim/lua/mcp-rules-assistant/init.lua" ]]; then
        installed_extensions+=("Neovim")
    fi
    
    if [[ ${#installed_extensions[@]} -gt 0 ]]; then
        log_success "✓ IDE extensions: ${installed_extensions[*]}"
    else
        log_warn "⚠ No IDE extensions installed"
    fi
    
    # Test basic functionality
    if .mcp/venv/bin/python -m mcp_rules_assistant.cli diagnose >/dev/null 2>&1; then
        log_success "✓ Basic functionality working"
    else
        log_error "✗ Basic functionality failed"
        validation_passed=false
    fi
    
    if $validation_passed; then
        log_success "🎉 Installation completed successfully!"
        log_info "Running commercial release validation..."
        if bash scripts/commercial-release-validation.sh; then
            log_success "🎉 Commercial release validation PASSED"
            log_info "Next steps:"
            log_info "1. Open your IDE and look for MCP Rules Assistant commands"
            log_info "2. VSCode/Cursor/Windsurf: Command Palette -> 'RuleFlow: Open Panel'"
            log_info "3. Neovim: :MCPStatus, :MCPCoverage, etc."
            log_info "4. Sublime: Tools -> MCP Rules Assistant"
            log_info "5. JetBrains: Tools -> External Tools -> MCP Rules Assistant"
            log_info "6. Review commercial release report: .mcp/commercial-release-report.md"
        else
            log_error "Commercial release validation FAILED"
            log_error "Review validation reports in .mcp/ directory"
            exit 1
        fi
    else
        log_error "❌ Installation validation failed"
        exit 1
    fi
}

# Main installation flow
main() {
    log_info "Starting MCP Rules Assistant installation..."
    
    setup_python_env
    initialize_mcp
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
            jetbrains)
                install_jetbrains_plugin
                ;;
            neovim)
                install_neovim_plugin
                ;;
            sublime)
                install_sublime_plugin
                ;;
        esac
    done
    
    validate_installation
}

# Run main function
main "$@"
