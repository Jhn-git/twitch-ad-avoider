# TwitchAdAvoider MSI Build Script
# Usage: .\scripts\build_msi.ps1 [-Version X.Y.Z]
# Packages dist\twitchadavoider (produced by build_executable.py) into a
# per-machine MSI installer using WiX Toolset v6. Requires 'wix' on PATH.
# Does NOT rebuild the exe - run build_executable.py / 'make build' first.

param(
    [string]$Version
)

$ErrorActionPreference = "Stop"

$ProjectRoot   = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
Import-Module "$PSScriptRoot\TwitchUtilities.psm1" -Force

$WxsPath       = "scripts\installer\twitchadavoider.wxs"
$AppDir        = "dist\twitchadavoider"
$ExePath       = "$AppDir\twitchadavoider.exe"
$PyprojectPath = "pyproject.toml"

Write-Info "TwitchAdAvoider MSI Build"
Write-Info "========================="

# RESOLVE VERSION (reuse pyproject.toml as the single source of truth, same
# regex release.ps1 uses)
if (-not $Version) {
    $pyprojectContent = Get-Content $PyprojectPath -Raw
    if ($pyprojectContent -match 'version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
        $Version = $Matches[1]
    } else {
        Write-Error "Could not parse version from $PyprojectPath"
        exit 1
    }
}
Write-Info "Version: $Version"

# VERIFY WIX IS AVAILABLE
if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
    Write-Error "WiX Toolset ('wix' command) not found on PATH."
    Write-Info "Install WiX Toolset v6 from https://wixtoolset.org/ (or: dotnet tool install --global wix)"
    exit 1
}
Write-Success "WiX found: $(wix --version)"

# VERIFY THE UI EXTENSION IS AVAILABLE (installed globally already; no
# network access needed if it's present)
$extListText = (wix extension list --global 2>&1) -join "`n"
if ($extListText -notmatch 'WixToolset\.UI\.wixext') {
    Write-Warning "WixToolset.UI.wixext not found in the global WiX extension cache."
    Write-Info "Install it with: wix extension add WixToolset.UI.wixext"
}

# VERIFY THE PYINSTALLER ONEDIR BUILD EXISTS
if (-not (Test-Path $ExePath)) {
    Write-Error "$ExePath not found. Run 'python scripts\build_executable.py' (or 'make build') first."
    exit 1
}
Write-Success "Found app build: $AppDir"

$MsiPath = "dist\twitchadavoider-v$Version.msi"
if (Test-Path $MsiPath) {
    Remove-Item -LiteralPath $MsiPath -Force
}

# Fixed-name copy (version-less) so GitHub's /releases/latest/download/
# evergreen link always resolves to the current release without needing
# manual updates on every version bump.
$FixedMsiPath = "dist\twitchadavoider.msi"

# BUILD
Write-Info "Building MSI..."
$AbsAppDir = (Resolve-Path $AppDir).Path

wix build $WxsPath `
    -arch x64 `
    -ext WixToolset.UI.wixext `
    -d SourceDir="$AbsAppDir" `
    -d Version=$Version `
    -intermediateFolder build\wix `
    -out $MsiPath

if ($LASTEXITCODE -ne 0) {
    Write-Error "wix build failed (exit code $LASTEXITCODE)."
    exit 1
}

if (-not (Test-Path $MsiPath)) {
    Write-Error "wix build reported success but $MsiPath was not created."
    exit 1
}

Write-Success "Created $MsiPath"

Copy-Item -LiteralPath $MsiPath -Destination $FixedMsiPath -Force
Write-Success "Created $FixedMsiPath (fixed-name alias for the evergreen download link)"
