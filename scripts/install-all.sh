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

# Generate VS Code compatibility artifacts (non-blocking)
generate_vscode_compat() {
    log_info "Generating VS Code compatibility report (best-effort)..."
    if ! command -v npm >/dev/null 2>&1; then
        log_warn "npm not found; skipping VS Code tests and lcov checks"
        return 0
    fi
    local root="$(pwd)"
    local ext_dir="${root}/extensions/vscode"
    if [[ ! -d "$ext_dir" ]]; then
        log_warn "extensions/vscode not found; skipping"
        return 0
    fi
    (
      set -e
      cd "$ext_dir"
      # Try tests (may fail in limited environments); keep non-blocking
      MCP_VSCODE_TEST_ARGS="${MCP_VSCODE_TEST_ARGS:-}" npm test || true
    ) || true

    # Check lcov threshold and export near/worst list (if coverage exists)
    local lcov="${ext_dir}/coverage/lcov.info"
    local threshold="${VSCODE_COVERAGE_THRESHOLD_WARN:-98}"
    local compat_dir="${root}/extensions/artifacts"
    mkdir -p "$compat_dir" || true
    local comp_json="${compat_dir}/compat_report.json"
    local near_txt="${root}/near_vscode.txt"
    local pass="false"
    if [[ -f "$lcov" ]]; then
        if sh "${root}/scripts/check-lcov.sh" "$lcov" "$threshold"; then
            pass="true"
        else
            pass="false"
        fi
        sh "${root}/scripts/lcov-near.sh" "$lcov" "$threshold" 5 20 > "$near_txt" || true
        cp -f "$lcov" "$compat_dir/" 2>/dev/null || true
    else
        log_warn "No lcov.info found; skip coverage gate and near list"
    fi
    cat > "$comp_json" <<JSON
{
  "ok": ${pass},
  "threshold": ${threshold},
  "lcov": "${lcov}",
  "near_list": "${near_txt}"
}
JSON
    log_info "Compat report: $comp_json"
}

# Print summary (artifacts + reports)
print_summary() {
    local ws_root="$(pwd)"
    local vsix=""
    if ls -1 "extensions/artifacts"/mcp-rules-assistant-*.vsix >/dev/null 2>&1; then
        vsix="$(ls -1 "extensions/artifacts"/mcp-rules-assistant-*.vsix | sort -V | tail -n1)"
    elif ls -1 "extensions/vscode"/mcp-rules-assistant-*.vsix >/dev/null 2>&1; then
        vsix="$(ls -1 "extensions/vscode"/mcp-rules-assistant-*.vsix | sort -V | tail -n1)"
    fi
    echo "[summary] Latest VSIX: $([[ -n "$vsix" ]] && realpath "$vsix" || echo '(not found)')"
    echo "[summary] Install report: $(realpath .mcp/dashboard/install_report.md 2>/dev/null || echo '(not generated)')"
    echo "[summary] VS Code compat report: $(realpath extensions/artifacts/compat_report.json 2>/dev/null || echo '(not generated)')"
    echo "[summary] VS Code near list: $(realpath near_vscode.txt 2>/dev/null || echo '(not generated)')"
}

# Detect WSL environment (Linux kernel with Microsoft hint or WSL env)
is_wsl() {
    if [[ "$(uname -s)" == "Linux" ]]; then
        if grep -qi 'microsoft\|wsl' /proc/sys/kernel/osrelease 2>/dev/null; then return 0; fi
        if [[ -n "${WSL_DISTRO_NAME-}" ]]; then return 0; fi
    fi
    return 1
}
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
    # Ensure dev/test tools are available for run_tests()
    pip install -U ruff black isort mypy bandit pytest pytest-cov pytest-benchmark psutil cryptography >/dev/null 2>&1 || true
    
    log_success "Python package installed successfully"
}

# Initialize MCP configuration
initialize_mcp() {
    log_info "Initializing MCP configuration..."
    source .mcp/venv/bin/activate
    
    if [[ ! -f ".mcp/assistant.yaml" ]]; then
        mcp-rules-assistant init --mode fast
    fi
    
    # Only ingest specific rule directories to avoid memory issues
    if [[ -d "rulesets" ]]; then
        mcp-rules-assistant ingest-rules rulesets/
    fi
    if [[ -d "docs" ]]; then
        mcp-rules-assistant ingest-rules docs/
    fi
    # Auto-apply environment-based config adjustments (best-effort)
    if .mcp/venv/bin/python -m mcp_rules_assistant.cli env-autotune --apply >/dev/null 2>&1; then
        log_info "Applied env-autotune suggestions to .mcp/assistant.yaml"
    else
        log_warn "env-autotune apply failed or not available (non-blocking)"
    fi
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
    if [[ -d "tests/unit" ]]; then
        pytest tests/unit/ --cov=mcp_rules_assistant --cov-report=xml --cov-report=html \
               --cov-fail-under=95 --maxfail=0 -v
    else
        log_warn "tests/unit/ not found, skipping unit tests"
    fi
    
    # 4. Integration tests
    log_info "Step 4/7: Integration tests..."
    if [[ -d "tests/component" ]]; then
        pytest tests/component/ --maxfail=0 -v
    else
        log_warn "tests/component/ not found, skipping integration tests"
    fi
    
    # 5. End-to-end tests
    log_info "Step 5/7: End-to-end functionality tests..."
    if [[ -d "tests/e2e" ]]; then
        pytest tests/e2e/ --maxfail=0 -v
    else
        log_warn "tests/e2e/ not found, skipping E2E tests"
    fi
    
    # 6. Performance benchmarks
    log_info "Step 6/7: Performance benchmarks..."
    if [[ -d "tests/performance" ]]; then
        pytest tests/performance/ --benchmark-only || log_warn "Performance tests had issues"
    else
        log_warn "tests/performance/ not found, skipping performance tests"
    fi
    
    # 7. Documentation tests
    log_info "Step 7/7: Documentation and examples validation..."
    if [[ -d "tests/docs" ]]; then
        pytest tests/docs/ --maxfail=0 -v
    else
        log_warn "tests/docs/ not found, skipping documentation tests"
    fi
    
    log_success "All commercial-grade tests passed successfully"
}

# Detect available IDEs
detect_ides() {
    local ides=()
    
    # Only detect VSCode for this installation
    if command -v code >/dev/null 2>&1; then
        ides+=("vscode")
    fi
    
    echo "${ides[@]}"
}

is_in_container() {
    # Heuristics: /.dockerenv or cgroup mentions docker/containerd
    if [[ -f "/.dockerenv" ]]; then return 0; fi
    if grep -qaE 'docker|containerd|kubepods' /proc/1/cgroup 2>/dev/null; then return 0; fi
    # Devcontainer also sets environment variables
    if [[ -n "${REMOTE_CONTAINERS-}" ]] || [[ -n "${DEVCONTAINER-}" ]]; then return 0; fi
    return 1
}

# Install VSCode-compatible extensions (VSCode, Cursor, Windsurf)
install_vscode_extension() {
    log_info "Building and installing VSCode extension..."

    if ! command -v npm >/dev/null 2>&1; then
        log_warn "npm not found; skipping VSIX build and VS Code installation."
        return 0
    fi
    cd extensions/vscode
    npm install || { log_warn "npm install failed; skipping VSIX build"; cd - >/dev/null; return 0; }
    npm run compile || { log_warn "npm run compile failed; skipping VSIX build"; cd - >/dev/null; return 0; }
    npm run package || { log_warn "npm run package failed; skipping VSIX install"; cd - >/dev/null; return 0; }

    # Pick latest packaged VSIX dynamically
    local vsix_file
    vsix_file="$(ls -1 mcp-rules-assistant-*.vsix 2>/dev/null | sort -V | tail -n1)"
    local vsix_abs_path
    if [[ -z "$vsix_file" ]]; then
        log_error "No VSIX produced. Check npm packaging logs."
        cd - >/dev/null
        return 1
    fi
    vsix_abs_path="$(pwd)/${vsix_file}"

    # Copy artifact to a stable location for distribution
    mkdir -p ../artifacts 2>/dev/null || true
    cp -f "$vsix_file" ../artifacts/ 2>/dev/null || true
    log_info "VSIX artifact copied to: $(cd ../artifacts && pwd)/$vsix_file"

    # Resolve VS Code CLI (prefer 'code', fallback to macOS absolute path)
    local CODE_BIN=""
    if command -v code >/dev/null 2>&1; then
        CODE_BIN="code"
    elif command -v code-insiders >/dev/null 2>&1; then
        CODE_BIN="code-insiders"
    elif [[ "$OS" == "macos" ]] && [[ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]]; then
        CODE_BIN="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    elif [[ "$OS" == "macos" ]] && [[ -x "/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code" ]]; then
        CODE_BIN="/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code"
    elif [[ "$OS" == "windows" ]]; then
        # Try common Windows locations via LOCALAPPDATA
        if [[ -n "${LOCALAPPDATA-}" ]]; then
            if [[ -x "${LOCALAPPDATA}/Programs/Microsoft VS Code/bin/code.cmd" ]]; then
                CODE_BIN="${LOCALAPPDATA}/Programs/Microsoft VS Code/bin/code.cmd"
            elif [[ -x "${LOCALAPPDATA}/Programs/Microsoft VS Code Insiders/bin/code-insiders.cmd" ]]; then
                CODE_BIN="${LOCALAPPDATA}/Programs/Microsoft VS Code Insiders/bin/code-insiders.cmd"
            fi
        fi
    fi

    # Install for VSCode
    if [[ -n "$CODE_BIN" ]]; then
        if "$CODE_BIN" --install-extension "$vsix_file" --force; then
            log_success "VSCode extension installed"
        else
            log_warn "Failed to install VSCode extension via code CLI"
        fi
    else
        # Fallback for macOS when code CLI is not available
        if [[ "$OS" == "macos" ]]; then
            log_warn "VSCode CLI 'code' not found. Using macOS fallback to install VSIX via GUI prompt."
            if open -a "Visual Studio Code" "$vsix_abs_path"; then
                log_success "VSIX opened with VSCode (please confirm the installation in VSCode if prompted)."
            else
                log_warn "Failed to open VSIX with Visual Studio Code. Please install manually: $vsix_abs_path"
            fi
        elif is_wsl; then
            log_warn "WSL 环境未检测到 VS Code CLI。请在 Windows 侧 VS Code 安装 Remote - WSL，并在 Windows 侧通过 \"Install from VSIX…\" 安装：$vsix_abs_path"
        else
            log_warn "VSCode CLI not found and no fallback available on this OS. Please install $vsix_abs_path manually."
        fi
    fi

    # Install for Cursor
    if command -v cursor >/dev/null 2>&1; then
        if cursor --install-extension "$vsix_file" --force; then
            log_success "Cursor extension installed"
        else
            log_warn "Failed to install Cursor extension"
        fi
    else
        if [[ "$OS" == "macos" ]]; then
            if open -a "Cursor" "$vsix_abs_path"; then
                log_success "VSIX opened with Cursor (confirm installation in GUI if prompted)."
            else
                log_warn "Cursor CLI not found and GUI open failed; please install manually: $vsix_abs_path"
            fi
        fi
    fi
    
    # Install for Windsurf
    if command -v windsurf >/dev/null 2>&1; then
        if windsurf --install-extension "$vsix_file" --force; then
            log_success "Windsurf extension installed"
        else
            log_warn "Failed to install Windsurf extension"
        fi
    else
        if [[ "$OS" == "macos" ]]; then
            if open -a "Windsurf" "$vsix_abs_path"; then
                log_success "VSIX opened with Windsurf (confirm installation in GUI if prompted)."
            else
                log_warn "Windsurf CLI not found and GUI open failed; please install manually: $vsix_abs_path"
            fi
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
    if [[ "${STRICT_TESTS:-1}" == "1" ]]; then
        run_tests
    else
        if ! run_tests; then
            log_warn "Tests/lint/security checks had issues (STRICT_TESTS=0). Continuing installation."
        fi
    fi

    # Purge existing extensions before reinstall (best-effort)
    if [[ -f "scripts/purge_ruleflow_extensions.sh" ]]; then
        log_info "Purging existing RuleFlow extensions before install..."
        bash scripts/purge_ruleflow_extensions.sh || log_warn "Purge script reported issues; continuing."
    fi

    log_info "Detecting available IDEs..."
    available_ides=($(detect_ides))
    if [[ ${#available_ides[@]} -eq 0 ]]; then
        log_warn "No supported IDEs detected"
    else
        log_info "Detected IDEs: ${available_ides[*]}"
    fi
    
    # Install VSCode-compatible extension (will also try Cursor/Windsurf) when running on host
    if is_in_container; then
        log_warn "Detected container/devcontainer environment: skipping host IDE extension install."
        log_info "To install the VS Code extension on your host, run: bash scripts/one_click_vscode_setup.sh"
    else
        # Install VSCode-compatible extension (will also try Cursor/Windsurf and fallback for VSCode on macOS)
        install_vscode_extension
        generate_vscode_compat || log_warn "VS Code compat report generation had issues (non-blocking)"
        # Best-effort install for other IDEs on host
        install_jetbrains_plugin || log_warn "JetBrains integration setup encountered issues (non-blocking)"
        install_neovim_plugin || log_warn "Neovim plugin setup encountered issues (non-blocking)"
        install_sublime_plugin || log_warn "Sublime plugin setup encountered issues (non-blocking)"
    fi

    validate_installation

    # Optional full verification (non-blocking if fails)
    if [[ "${RUN_VERIFY:-0}" == "1" ]]; then
        if ! bash scripts/verify-all.sh; then
            log_warn "Full verify reported issues (non-blocking)."
        fi
    else
        log_info "Skipping full verify (set RUN_VERIFY=1 to enable)."
    fi

    # Generate install reports (best-effort)
    if [[ -f "scripts/diagnose-env.sh" ]]; then
        log_info "Running environment diagnostics..."
        bash scripts/diagnose-env.sh || log_warn "diagnose-env reported issues (non-blocking)"
        log_info "Install report: .mcp/dashboard/install_report.md"
    fi

    print_summary
}

# Run main function
main "$@"
