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
    Write-ColorOutput "[OK] $Message" "Green"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "[ERROR] $Message" "Red"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "[WARN] $Message" "Yellow"
}

function Write-Info {
    param([string]$Message)
    Write-ColorOutput "[INFO] $Message" "Cyan"
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
                Write-Info "Please install Python 3.10, 3.11, 3.12, or 3.13 from https://python.org"
                return $false
            }
        }
    }
    catch {
        Write-Error "Python is not installed or not in PATH"
        Write-Info "Please install Python 3.10, 3.11, 3.12, or 3.13 from https://python.org"
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

# Upgrade streamlink to the latest available version
function Update-Streamlink {
    Write-Info "Upgrading streamlink..."
    try {
        pip install --upgrade streamlink 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $version = python -c "import streamlink; print(streamlink.__version__)" 2>&1
            Write-Success "streamlink upgraded to $version"
            return $true
        }
        else {
            Write-Warning "streamlink upgrade exited with code $LASTEXITCODE - continuing with installed version"
            return $false
        }
    }
    catch {
        Write-Warning "streamlink upgrade failed: $_ - continuing with installed version"
        return $false
    }
}

# Matches only a line that starts with `version = "x.y.z"` (the [project] version). Anchoring to
# line start keeps keys that merely end in "version", like mypy's python_version, untouched.
$script:PyprojectVersionPattern = '(?m)^(version\s*=\s*")([0-9]+\.[0-9]+\.[0-9]+)(")'

# Return the [project] version from pyproject.toml text, or $null if absent
function Get-PyprojectVersion {
    param([Parameter(Mandatory)][string]$Content)

    if ($Content -match $script:PyprojectVersionPattern) {
        return $Matches[2]
    }
    return $null
}

# Return pyproject.toml text with only the [project] version replaced
function Set-PyprojectVersion {
    param(
        [Parameter(Mandatory)][string]$Content,
        [Parameter(Mandatory)][string]$Version
    )

    return $Content -replace $script:PyprojectVersionPattern, "`${1}$Version`${3}"
}

# Export functions
Export-ModuleMember -Function Write-ColorOutput, Write-Success, Write-Error, Write-Warning, Write-Info, Test-ChannelName, Test-PythonInstallation, Test-StreamlinkInstallation, Update-Streamlink, Get-PyprojectVersion, Set-PyprojectVersion
