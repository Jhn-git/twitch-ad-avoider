# TwitchAdAvoider daily desktop EXE updater
# Builds a fresh EXE, replaces the desktop copy, and relaunches one instance.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Import-Module "$ProjectRoot\scripts\TwitchUtilities.psm1" -Force

$BuiltExe = Join-Path $ProjectRoot "dist\TwitchAdAvoider.exe"
$TargetExe = "C:\Users\redacted\Desktop\Jhn Apps\jhn-twitch-viewer\twitchadavoider.exe"
$BackupExe = "C:\Users\redacted\Desktop\Jhn Apps\jhn-twitch-viewer\twitchadavoider.previous.exe"
$TargetDir = Split-Path -Parent $TargetExe

function Get-DesktopExeProcesses {
    Get-Process | Where-Object {
        try {
            $_.Path -eq $TargetExe
        }
        catch {
            $false
        }
    }
}

try {
    Write-Info "TwitchAdAvoider daily EXE updater"
    Write-Info "================================"

    if (-not (Test-PythonInstallation)) {
        throw "Python is required to build TwitchAdAvoider."
    }

    if (-not (Test-Path $TargetDir)) {
        throw "Desktop app folder not found: $TargetDir"
    }

    Write-Info "Building fresh executable..."
    python scripts/build_executable.py --skip-deps
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path $BuiltExe)) {
        throw "Build completed but EXE was not found at $BuiltExe."
    }

    $runningProcesses = @(Get-DesktopExeProcesses)
    if ($runningProcesses.Count -gt 0) {
        Write-Info "Stopping $($runningProcesses.Count) running desktop instance(s)..."
        foreach ($process in $runningProcesses) {
            Write-Info "Stopping PID $($process.Id)"
            Stop-Process -Id $process.Id -Force
        }

        $deadline = (Get-Date).AddSeconds(10)
        while ((Get-DesktopExeProcesses).Count -gt 0 -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 250
        }

        $remainingProcesses = @(Get-DesktopExeProcesses)
        if ($remainingProcesses.Count -gt 0) {
            throw "Could not stop all running desktop instances. Update aborted."
        }
    }
    else {
        Write-Info "Desktop app is not running."
    }

    if (Test-Path $TargetExe) {
        Copy-Item -LiteralPath $TargetExe -Destination $BackupExe -Force
        Write-Success "Backed up current EXE to $BackupExe"
    }
    else {
        Write-Warning "Current desktop EXE not found. A new copy will be placed there."
    }

    Copy-Item -LiteralPath $BuiltExe -Destination $TargetExe -Force
    Write-Success "Replaced desktop EXE at $TargetExe"

    Start-Process -FilePath $TargetExe -WorkingDirectory $TargetDir
    Write-Success "Relaunched TwitchAdAvoider"
}
catch {
    Write-Error "Daily EXE update failed: $($_.Exception.Message)"
    Write-Warning "The desktop copy was not changed unless the build and backup steps already succeeded."
    exit 1
}
