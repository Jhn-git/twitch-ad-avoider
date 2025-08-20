param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$ChannelName,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipPlayerCheck
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Import shared utilities
Import-Module "$PSScriptRoot\scripts\TwitchUtilities.psm1" -Force

# Check for available video players (essential players only)
function Test-VideoPlayers {
    $players = [ordered]@{
        "VLC" = @("vlc", "vlc.exe")
        "MPV" = @("mpv", "mpv.exe", "mpv.com") 
        "MPC-HC" = @("mpc-hc", "mpc-hc.exe", "mpc-hc64.exe")
    }
    
    $knownPaths = [ordered]@{
        "VLC" = @(
            "C:\Program Files\VideoLAN\VLC\vlc.exe",
            "C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
        )
        "MPV" = @(
            "C:\ProgramData\chocolatey\lib\mpvio.install\tools\mpv.exe"
        )
        "MPC-HC" = @(
            "C:\Program Files\MPC-HC\mpc-hc64.exe",
            "C:\Program Files (x86)\MPC-HC\mpc-hc.exe"
        )
    }
    
    $foundPlayers = @()
    $playerPaths = @{}
    
    # Check PATH and known paths for each player
    foreach ($playerName in $players.Keys) {
        # Try PATH first
        foreach ($exe in $players[$playerName]) {
            $playerPath = Get-Command $exe -ErrorAction SilentlyContinue
            if ($playerPath) {
                Write-Success "Found ${playerName}: $($playerPath.Source)"
                $foundPlayers += $playerName
                $playerPaths[$playerName] = $playerPath.Source
                break
            }
        }
        
        # If not found in PATH, try known paths
        if ($foundPlayers -notcontains $playerName -and $knownPaths.ContainsKey($playerName)) {
            foreach ($path in $knownPaths[$playerName]) {
                if (Test-Path $path) {
                    Write-Success "Found ${playerName}: $path"
                    $foundPlayers += $playerName
                    $playerPaths[$playerName] = $path
                    break
                }
            }
        }
    }
    
    if ($foundPlayers.Count -eq 0) {
        Write-Error "No supported video players found"
        Write-Info "Please install VLC, MPV, or MPC-HC"
        return $false
    }
    
    Write-Success "Available players: $($foundPlayers -join ', ')"
    
    # Export first found player for Python integration
    $primaryPlayer = $foundPlayers[0]
    $env:TWITCH_PLAYER_NAME = $primaryPlayer
    $env:TWITCH_PLAYER_PATH = $playerPaths[$primaryPlayer]
    Write-Info "Using: $primaryPlayer"
    
    return $true
}

# Setup virtual environment
function Initialize-VirtualEnvironment {
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
        Write-Success "Virtual environment already exists"
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

# Install dependencies
function Install-Dependencies {
    if (Test-Path "requirements.txt") {
        Write-Info "Installing dependencies..."
        try {
            pip install -r requirements.txt
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Dependencies installed successfully"
                return $true
            }
            else {
                Write-Error "Failed to install dependencies"
                return $false
            }
        }
        catch {
            Write-Error "Failed to install dependencies: $_"
            return $false
        }
    }
    else {
        Write-Warning "requirements.txt not found"
        return $false
    }
}

# Main execution
try {
    Write-Info "TwitchAdAvoider PowerShell Runner"
    Write-Info "================================"
    
    # Set working directory
    Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
    
    # Validate and setup
    $validatedChannel = Test-ChannelName $ChannelName
    Write-Success "Channel: $validatedChannel"
    
    # Check requirements
    if (-not (Test-PythonInstallation)) { exit 1 }
    if (-not (Test-StreamlinkInstallation)) { exit 1 }
    
    # Check video players unless skipped
    if (-not $SkipPlayerCheck) {
        if (-not (Test-VideoPlayers)) { 
            Write-Warning "Use -SkipPlayerCheck flag to bypass, but ensure a player is installed"
            exit 1 
        }
    } else {
        Write-Warning "Player check skipped - ensure VLC/MPV/MPC-HC is installed"
    }
    
    # Setup virtual environment
    if (-not (Initialize-VirtualEnvironment)) {
        exit 1
    }
    
    # Install dependencies
    if (-not (Install-Dependencies)) {
        Write-Warning "Continuing anyway, but the script may fail if dependencies are missing"
    }
    
    # Run the main script
    Write-Info "Starting TwitchAdAvoider for channel: $validatedChannel"
    Write-Info "Press Ctrl+C to stop the stream"
    
    try {
        python watch_stream.py $validatedChannel
    }
    catch {
        Write-Error "Failed to start stream: $_"
        exit 1
    }
}
catch {
    Write-Error "Unexpected error: $_"
    exit 1
}
finally {
    Write-Info "Script completed"
}