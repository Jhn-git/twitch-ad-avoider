# TwitchUtilities PowerShell Module
# Shared utility functions for TwitchAdAvoider scripts

# Function to write colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✓ $Message" "Green"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "✗ $Message" "Red"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "⚠ $Message" "Yellow"
}

function Write-Info {
    param([string]$Message)
    Write-ColorOutput "ℹ $Message" "Cyan"
}

# Validate channel name
function Test-ChannelName {
    param([string]$Channel)
    
    if ([string]::IsNullOrWhiteSpace($Channel)) {
        throw "Channel name cannot be empty"
    }
    
    if ($Channel.Length -lt 4 -or $Channel.Length -gt 25) {
        throw "Channel name must be between 4 and 25 characters"
    }
    
    if ($Channel -notmatch '^[a-zA-Z0-9_]+$') {
        throw "Channel name can only contain letters, numbers, and underscores"
    }
    
    return $Channel.ToLower()
}

# Check if Python is installed
function Test-PythonInstallation {
    try {
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python found: $pythonVersion"
            return $true
        }
        else {
            try {
                $pythonVersion = python3 --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Python found: $pythonVersion"
                    return $true
                }
            }
            catch {
                Write-Error "Python is not installed or not in PATH"
                Write-Info "Please install Python 3.6+ from https://python.org"
                return $false
            }
        }
    }
    catch {
        Write-Error "Python is not installed or not in PATH"
        Write-Info "Please install Python 3.6+ from https://python.org"
        return $false
    }
    return $false
}

# Check if streamlink is installed and working
function Test-StreamlinkInstallation {
    try {
        $streamlinkVersion = streamlink --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Streamlink found: $streamlinkVersion"
            return $true
        }
        else {
            Write-Error "Streamlink is not working properly"
            return $false
        }
    }
    catch {
        Write-Error "Streamlink is not installed or not in PATH"
        Write-Info "Please install streamlink using: pip install streamlink"
        return $false
    }
}

# Export functions
Export-ModuleMember -Function Write-ColorOutput, Write-Success, Write-Error, Write-Warning, Write-Info, Test-ChannelName, Test-PythonInstallation, Test-StreamlinkInstallation