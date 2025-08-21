param(
    [switch]$Dev,
    [switch]$Development,
    [switch]$Help
)

# TwitchAdAvoider - GUI Launcher
# Handles virtual environment setup, modern dependency installation, and launches the GUI
# Uses pyproject.toml for dependency management

# Set error action preference
$ErrorActionPreference = "Stop"

# Import shared utilities for colored output
Import-Module "$PSScriptRoot\scripts\TwitchUtilities.psm1" -Force

function Initialize-VirtualEnvironment {
    """Setup or use existing virtual environment"""
    $venvPath = "venv"
    
    if (-not (Test-Path $venvPath)) {
        Write-Info "Creating virtual environment..."
        try {
            python -m venv $venvPath
            Write-Success "Virtual environment created"
        }
        catch {
            Write-Error "Failed to create virtual environment: $_"
            return $false
        }
    }
    else {
        Write-Success "Using existing virtual environment"
    }
    
    # Activate virtual environment
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        try {
            Write-Info "Activating virtual environment..."
            & $activateScript
            Write-Success "Virtual environment activated"
            return $true
        }
        catch {
            Write-Error "Failed to activate virtual environment: $_"
            return $false
        }
    }
    else {
        Write-Error "Virtual environment activation script not found"
        return $false
    }
}

function Install-Dependencies {
    """Install Python dependencies from pyproject.toml"""
    param(
        [switch]$Development = $false
    )
    
    if (Test-Path "pyproject.toml") {
        if ($Development) {
            Write-Info "Installing project with development dependencies..."
            $installCommand = "pip install -e .[dev] --quiet"
        }
        else {
            Write-Info "Installing project dependencies..."
            $installCommand = "pip install -e . --quiet"
        }
        
        try {
            Write-Info "Running: $installCommand"
            Invoke-Expression $installCommand
            if ($LASTEXITCODE -eq 0) {
                if ($Development) {
                    Write-Success "Project and development dependencies installed successfully"
                    Write-Info "Development tools available: pytest, black, flake8, mypy, coverage, pre-commit"
                    Write-Info "You can now run: python -m pytest, black ., flake8 ., mypy src/"
                }
                else {
                    Write-Success "Project dependencies installed successfully"
                    Write-Info "Core dependency: streamlink>=5.0.0"
                    Write-Info "Project installed in editable mode - changes will be reflected immediately"
                }
                return $true
            }
            else {
                Write-Warning "Installation completed with warnings (exit code: $LASTEXITCODE)"
                Write-Info "This is usually not a problem and the application should still work"
                return $true  # Continue anyway
            }
        }
        catch {
            Write-Warning "Failed to install dependencies: $_"
            Write-Info "Manual installation commands:"
            Write-Info "  pip install -e .        # For basic usage"
            Write-Info "  pip install -e .[dev]   # For development"
            Write-Warning "The application may not work properly without dependencies"
            return $true  # Continue anyway to let user try
        }
    }
    else {
        Write-Error "pyproject.toml not found - project configuration missing"
        return $false
    }
}

function Start-GUI {
    """Launch the TwitchAdAvoider GUI"""
    Write-Info "Launching TwitchAdAvoider GUI..."
    Write-Info "==============================="
    
    try {
        python main.py
        return $true
    }
    catch {
        Write-Error "Failed to start GUI: $_"
        return $false
    }
}

# Main execution

# Show help if requested
if ($Help) {
    Write-Info "TwitchAdAvoider GUI Launcher"
    Write-Info "============================"
    Write-Info "Usage: .\run.ps1 [options]"
    Write-Info ""
    Write-Info "Options:"
    Write-Info "  -Dev, -Development    Install with development dependencies (pytest, black, etc.)"
    Write-Info "  -Help                 Show this help message"
    Write-Info ""
    Write-Info "Examples:"
    Write-Info "  .\run.ps1                 # Standard installation and launch"
    Write-Info "  .\run.ps1 -Dev            # Install with development tools"
    Write-Info "  .\run.ps1 -Development    # Same as -Dev"
    exit 0
}

# Determine if development mode is requested
$isDevelopment = $Dev -or $Development

try {
    Write-Info "TwitchAdAvoider GUI Launcher"
    Write-Info "============================"
    
    if ($isDevelopment) {
        Write-Info "Development mode enabled - installing dev dependencies"
    }
    
    # Set working directory to script location
    Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
    
    # Check Python installation
    if (-not (Test-PythonInstallation)) { 
        Write-Error "Python is required. Please install Python 3.7+ from https://python.org"
        Write-Info "This project requires Python 3.7 or newer as specified in pyproject.toml"
        Read-Host "Press Enter to exit"
        exit 1 
    }
    
    # Setup virtual environment
    if (-not (Initialize-VirtualEnvironment)) {
        Write-Error "Failed to initialize virtual environment"
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    # Install dependencies (with development option if requested)
    if (-not (Install-Dependencies -Development:$isDevelopment)) {
        Write-Error "Failed to install dependencies"
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    # Launch GUI
    if (-not (Start-GUI)) {
        Write-Error "Failed to launch GUI"
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    Write-Success "GUI session completed"
}
catch {
    Write-Error "Unexpected error: $_"
    Read-Host "Press Enter to exit"
    exit 1
}
finally {
    Write-Info "Launcher finished"
}