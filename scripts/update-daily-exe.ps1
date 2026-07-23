# TwitchAdAvoider daily desktop EXE updater
# Builds a fresh EXE, replaces the desktop copy, and relaunches one instance.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Import-Module "$ProjectRoot\scripts\TwitchUtilities.psm1" -Force

$BuiltAppDir = Join-Path $ProjectRoot "dist\twitchadavoider"
$TargetDir = Join-Path $env:USERPROFILE "Desktop\Jhn Apps\jhn-twitch-viewer"
$TargetExe = Join-Path $TargetDir "twitchadavoider.exe"
$TargetParentDir = Split-Path -Parent $TargetDir

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

    if (-not (Test-Path $TargetParentDir)) {
        throw "Desktop app parent folder not found: $TargetParentDir"
    }

    Update-Streamlink

    Write-Info "Building fresh executable..."
    python scripts/build_executable.py --skip-deps
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path $BuiltAppDir)) {
        throw "Build completed but app folder was not found at $BuiltAppDir."
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

    if (-not (Test-Path $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir | Out-Null
    }

    # Only replace build output (exe, _internal, launch.bat). User data such as
    # config/, clips/, logs/, and temp/ lives alongside the build output in the
    # same folder and must never be touched by an update. Each replaced item is
    # backed up as "<name>.previous" for rollback.
    Get-ChildItem -LiteralPath $BuiltAppDir | ForEach-Object {
        $destPath = Join-Path $TargetDir $_.Name
        $backupPath = Join-Path $TargetDir "$($_.Name).previous"

        if (Test-Path $destPath) {
            if (Test-Path $backupPath) {
                Remove-Item -LiteralPath $backupPath -Recurse -Force
            }
            Move-Item -LiteralPath $destPath -Destination $backupPath
        }

        Copy-Item -LiteralPath $_.FullName -Destination $destPath -Recurse -Force
    }
    Write-Success "Replaced build output in $TargetDir (previous build backed up as *.previous)"

    Start-Process -FilePath $TargetExe -WorkingDirectory $TargetDir
    Write-Success "Relaunched TwitchAdAvoider"
}
catch {
    Write-Error "Daily EXE update failed: $($_.Exception.Message)"
    Write-Warning "The desktop copy was not changed unless the build output replace step already succeeded."
    exit 1
}
