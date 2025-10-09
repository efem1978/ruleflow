@echo off
REM MCP Rules Assistant - One-Click Installer (Windows)
REM License: MIT

setlocal enabledelayedexpansion

echo.
echo ===============================================
echo   MCP Rules Assistant - OSS Edition
echo   One-Click Installer (Windows)
echo   License: MIT
echo ===============================================
echo.

REM Check Python
echo [INFO] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ first.
    echo Visit: https://www.python.org/downloads/
    exit /b 1
)

python --version
echo [OK] Python found

REM Get project directory
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
echo [INFO] Project directory: %PROJECT_DIR%

REM Create virtual environment
set "VENV_DIR=%PROJECT_DIR%.venv"
echo [INFO] Creating virtual environment...
if exist "%VENV_DIR%" (
    echo [WARN] Virtual environment already exists
) else (
    python -m venv "%VENV_DIR%"
    echo [OK] Virtual environment created
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install package
echo [INFO] Installing mcp-rules-assistant...
pip install -e . --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Installation failed
    exit /b 1
)
echo [OK] Package installed

REM Verify installation
echo [INFO] Verifying installation...
mcp-rules-assistant --version
if %errorlevel% neq 0 (
    echo [ERROR] Verification failed
    exit /b 1
)
echo [OK] Installation verified

REM Initialize (optional)
echo [INFO] Initializing configuration...
if not exist ".mcp\assistant.yaml" (
    mcp-rules-assistant init
)

REM Install VS Code extension (works for VS Code, Cursor, Windsurf)
echo [INFO] Installing VS Code extension...
set "VSIX_FILE=%PROJECT_DIR%extensions\vscode\mcp-rules-assistant-0.3.2.vsix"
if exist "%VSIX_FILE%" (
    where code >nul 2>&1
    if %errorlevel% equ 0 (
        code --install-extension "%VSIX_FILE%" >nul 2>&1
        if %errorlevel% equ 0 (
            echo [OK] Installed for VS Code
        ) else (
            echo [WARN] VS Code install failed
        )
    )
    
    where cursor >nul 2>&1
    if %errorlevel% equ 0 (
        cursor --install-extension "%VSIX_FILE%" >nul 2>&1
        if %errorlevel% equ 0 (
            echo [OK] Installed for Cursor
        )
    )
    
    REM Manual hint if no CLI found
    where code >nul 2>&1
    if %errorlevel% neq 0 (
        where cursor >nul 2>&1
        if %errorlevel% neq 0 (
            echo [WARN] No IDE CLI found
            echo Manual: code --install-extension %VSIX_FILE%
        )
    )
) else (
    echo [WARN] VS Code extension .vsix file not found
)

echo.
echo ===============================================
echo   Installation Complete!
echo ===============================================
echo.
echo Activate venv: .venv\Scripts\activate.bat
echo Run CLI: mcp-rules-assistant --help
echo.
echo Quick Start:
echo   1. mcp-rules-assistant diagnose
echo   2. pytest -q
echo   3. See README.md for more
echo.
echo Happy coding! 🚀
echo.
pause
