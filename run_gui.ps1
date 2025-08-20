param(
    [Parameter(Mandatory=$false)]
    [switch]$ForceRecreate
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Import shared utilities
Import-Module "$PSScriptRoot\scripts\TwitchUtilities.psm1" -Force

# Function to create virtual environment
function Initialize-VirtualEnvironmentForGUI {
    param(
        [bool]$ForceRecreate = $false
    )
    
    # Check for existing venv directories
    $venvPath = "venv"
    $altVenvPath = ".venv"
    
    # Remove corrupted .venv if it exists and is incomplete
    if ((Test-Path $altVenvPath) -and (-not (Test-Path "$altVenvPath\pyvenv.cfg"))) {
        Write-Warning "Found corrupted .venv directory, attempting to remove it..."
        try {
            Remove-Item $altVenvPath -Recurse -Force -ErrorAction SilentlyContinue
            Write-Success "Removed corrupted .venv directory"
        }
        catch {
            Write-Warning "Could not remove .venv directory (I/O error), continuing with venv directory"
        }
    }
    
    # Determine which venv to use
    $activeVenvPath = $null
    
    if ((Test-Path $venvPath) -and (Test-Path "$venvPath\pyvenv.cfg") -and (-not $ForceRecreate)) {
        Write-Success "Using existing virtual environment: $venvPath"
        $activeVenvPath = $venvPath
    }
    elseif ((Test-Path $altVenvPath) -and (Test-Path "$altVenvPath\pyvenv.cfg") -and (-not $ForceRecreate)) {
        Write-Success "Using existing virtual environment: $altVenvPath"
        $activeVenvPath = $altVenvPath
    }
    else {
        # Create new virtual environment
        if ($ForceRecreate -and (Test-Path $venvPath)) {
            Write-Info "Force recreating virtual environment..."
            Remove-Item $venvPath -Recurse -Force -ErrorAction SilentlyContinue
        }
        
        Write-Info "Creating virtual environment..."
        try {
            python -m venv $venvPath
            if (Test-Path "$venvPath\pyvenv.cfg") {
                Write-Success "Virtual environment created successfully"
                $activeVenvPath = $venvPath
            }
            else {
                throw "Virtual environment creation failed"
            }
        }
        catch {
            Write-Error "Failed to create virtual environment: $_"
            return $null
        }
    }
    
    return $activeVenvPath
}

# Function to activate virtual environment and install dependencies
function Start-VirtualEnvironment {
    param([string]$VenvPath)
    
    # Determine activation script path
    $activateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
    
    if (-not (Test-Path $activateScript)) {
        Write-Error "Virtual environment activation script not found: $activateScript"
        return $false
    }
    
    # Activate virtual environment
    Write-Info "Activating virtual environment..."
    try {
        & $activateScript
        Write-Success "Virtual environment activated"
    }
    catch {
        Write-Error "Failed to activate virtual environment: $_"
        return $false
    }
    
    # Install dependencies if requirements.txt exists
    if (Test-Path "requirements.txt") {
        Write-Info "Installing dependencies..."
        try {
            pip install -r requirements.txt --quiet
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Dependencies installed successfully"
            }
            else {
                Write-Warning "Some dependencies may not have installed correctly"
            }
        }
        catch {
            Write-Warning "Failed to install some dependencies: $_"
        }
    }
    
    return $true
}

# Function to launch GUI
function Start-GUI {
    Write-Info "Launching TwitchAdAvoider GUI..."
    Write-Info "=================================="
    
    try {
        python run_gui.py
    }
    catch {
        Write-Error "Failed to start GUI: $_"
        return $false
    }
    
    return $true
}

# Main execution
try {
    Write-Info "TwitchAdAvoider GUI Launcher"
    Write-Info "============================"
    
    # Set working directory
    Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
    
    # Check Python installation
    if (-not (Test-PythonInstallation)) { 
        Write-Error "Python is required to run the GUI"
        exit 1 
    }
    
    # Initialize virtual environment
    $venvPath = Initialize-VirtualEnvironmentForGUI -ForceRecreate $ForceRecreate.IsPresent
    if (-not $venvPath) {
        Write-Error "Failed to initialize virtual environment"
        exit 1
    }
    
    # Start virtual environment and install dependencies
    if (-not (Start-VirtualEnvironment -VenvPath $venvPath)) {
        Write-Error "Failed to start virtual environment"
        exit 1
    }
    
    # Check if tkinter is available
    Write-Info "Checking tkinter availability..."
    try {
        $tkinterCheck = python -c "import tkinter; print('tkinter available')" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "tkinter is available"
        }
        else {
            Write-Error "tkinter is not available. Please install python3-tk package:"
            Write-Info "  Ubuntu/Debian: sudo apt-get install python3-tk"
            Write-Info "  Windows: tkinter should be included with Python"
            Write-Info "  If using conda: conda install tk"
            exit 1
        }
    }
    catch {
        Write-Error "Failed to check tkinter: $_"
        exit 1
    }
    
    # Launch GUI
    if (-not (Start-GUI)) {
        exit 1
    }
    
    Write-Success "GUI session completed"
}
catch {
    Write-Error "Unexpected error: $_"
    exit 1
}
finally {
    Write-Info "GUI launcher finished"
}