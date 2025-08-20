# TwitchAdAvoider - Simple GUI Launcher
# Handles virtual environment setup and launches the GUI

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
    """Install Python dependencies from requirements.txt"""
    if (Test-Path "requirements.txt") {
        Write-Info "Installing dependencies..."
        try {
            pip install -r requirements.txt --quiet
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Dependencies installed successfully"
                return $true
            }
            else {
                Write-Warning "Some dependencies may not have installed correctly"
                return $true  # Continue anyway
            }
        }
        catch {
            Write-Warning "Failed to install some dependencies: $_"
            return $true  # Continue anyway
        }
    }
    else {
        Write-Warning "requirements.txt not found"
        return $true
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
try {
    Write-Info "TwitchAdAvoider GUI Launcher"
    Write-Info "============================"
    
    # Set working directory to script location
    Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
    
    # Check Python installation
    if (-not (Test-PythonInstallation)) { 
        Write-Error "Python is required. Please install Python 3.6+ from https://python.org"
        Read-Host "Press Enter to exit"
        exit 1 
    }
    
    # Setup virtual environment
    if (-not (Initialize-VirtualEnvironment)) {
        Write-Error "Failed to initialize virtual environment"
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    # Install dependencies
    if (-not (Install-Dependencies)) {
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