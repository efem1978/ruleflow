#!/bin/bash
# MCP Rules Assistant - One-Click Installer (OSS Edition)
# Supports: Linux, macOS, Windows (Git Bash)
# License: MIT

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

# Banner
echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════╗
║  MCP Rules Assistant - OSS Edition       ║
║  One-Click Installer                      ║
║  License: MIT                             ║
╚═══════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Detect OS
OS="unknown"
case "$(uname -s)" in
    Linux*)     OS="Linux";;
    Darwin*)    OS="macOS";;
    CYGWIN*|MINGW*|MSYS*) OS="Windows";;
esac
info "Detected OS: $OS"

# Check Python
info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 not found. Please install Python 3.10+ first."
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
info "Python version: $PYTHON_VERSION"

# Check Python version
MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
    error "Python 3.10+ required. Current: $PYTHON_VERSION"
fi
success "Python version check passed"

# Check Git
info "Checking Git installation..."
if ! command -v git &> /dev/null; then
    error "Git not found. Please install Git first."
fi
success "Git found: $(git --version)"

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "Project directory: $PROJECT_DIR"
cd "$PROJECT_DIR"

# Create virtual environment
VENV_DIR="$PROJECT_DIR/.venv"
info "Creating virtual environment at $VENV_DIR..."
if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists, skipping creation"
else
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created"
fi

# Activate virtual environment
info "Activating virtual environment..."
if [ "$OS" = "Windows" ]; then
    source "$VENV_DIR/Scripts/activate"
else
    source "$VENV_DIR/bin/activate"
fi
success "Virtual environment activated"

# Upgrade pip
info "Upgrading pip..."
python -m pip install --upgrade pip --quiet
success "pip upgraded"

# Install package in editable mode
info "Installing mcp-rules-assistant in editable mode..."
pip install -e . --quiet
success "Package installed"

# Install development dependencies (optional)
if [ "${INSTALL_DEV:-0}" = "1" ]; then
    info "Installing development dependencies..."
    if [ -f "constraints-ci.txt" ]; then
        pip install -r constraints-ci.txt --quiet
    fi
    success "Development dependencies installed"
fi

# Verify installation
info "Verifying installation..."
if ! command -v mcp-rules-assistant &> /dev/null; then
    error "Installation verification failed"
fi
VERSION=$(mcp-rules-assistant --version 2>&1 || echo "unknown")
success "Installation verified: $VERSION"

# Initialize configuration (optional)
if [ "${SKIP_INIT:-0}" = "0" ]; then
    info "Initializing configuration..."
    if [ ! -f ".mcp/assistant.yaml" ]; then
        mcp-rules-assistant init --quiet || warn "Initialization skipped (already configured)"
    else
        warn "Configuration already exists, skipping init"
    fi
fi

# Install Git hooks (optional)
if [ "${INSTALL_HOOKS:-1}" = "1" ]; then
    info "Installing Git hooks..."
    mcp-rules-assistant install-hooks || warn "Git hooks installation failed (non-blocking)"
    success "Git hooks installed"
fi

# Install VS Code extension (works for VS Code, Cursor, Windsurf)
if [ "${INSTALL_VSCODE_EXT:-1}" = "1" ]; then
    VSIX_FILE="$PROJECT_DIR/extensions/vscode/mcp-rules-assistant-0.3.2.vsix"
    
    if [ ! -f "$VSIX_FILE" ]; then
        warn "VS Code extension .vsix file not found, skipping"
    else
        info "Installing VS Code extension (compatible with VS Code/Cursor/Windsurf)..."
        
        # Try VS Code
        if command -v code &> /dev/null; then
            code --install-extension "$VSIX_FILE" 2>/dev/null && success "Installed for VS Code" || warn "VS Code install failed"
        fi
        
        # Try Cursor
        if command -v cursor &> /dev/null; then
            cursor --install-extension "$VSIX_FILE" 2>/dev/null && success "Installed for Cursor" || warn "Cursor install failed"
        fi
        
        # Try Windsurf (if it has CLI)
        if command -v windsurf &> /dev/null; then
            windsurf --install-extension "$VSIX_FILE" 2>/dev/null && success "Installed for Windsurf" || warn "Windsurf install failed"
        fi
        
        # Manual installation hint
        if ! command -v code &> /dev/null && ! command -v cursor &> /dev/null && ! command -v windsurf &> /dev/null; then
            warn "No compatible IDE CLI found"
            info "Manual installation:"
            info "  VS Code: code --install-extension $VSIX_FILE"
            info "  Cursor: cursor --install-extension $VSIX_FILE"
            info "  Or install via IDE: Extensions → Install from VSIX..."
        fi
    fi
fi

# Summary
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation Complete!                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
info "Activate virtual environment: source $VENV_DIR/bin/activate"
info "Run CLI: mcp-rules-assistant --help"
info "VS Code Extension: Install from extensions/vscode/"
echo ""
info "Quick Start:"
echo "  1. Activate venv: source .venv/bin/activate"
echo "  2. Check status: mcp-rules-assistant diagnose"
echo "  3. Run tests: pytest -q"
echo "  4. View docs: cat README.md"
echo ""
success "Happy coding! 🚀"
