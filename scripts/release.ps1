# TwitchAdAvoider Release Script
# Usage: .\scripts\release.ps1 [-Bump patch|minor|major] [-DryRun]
# Bumps version, builds exe, commits+tags, pushes, creates GitHub release.

param(
    [ValidateSet("patch", "minor", "major")]
    [string]$Bump = "patch",
    [switch]$DryRun
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
Import-Module "$PSScriptRoot\TwitchUtilities.psm1" -Force

$PyprojectPath = "pyproject.toml"
$ConstantsPath = "src\constants.py"
$SpecPath      = "scripts\twitchadavoider.spec"
$ExePath       = "dist\TwitchAdAvoider.exe"

# ─── PREFLIGHT ───────────────────────────────────────────────────────────────

Write-Info "TwitchAdAvoider Release Script"
Write-Info "=============================="
Write-Host ""
Write-Warning "Reminder: run 'make all' before releasing if you haven't already."
Write-Host ""

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) not found. Install from https://cli.github.com/"
    exit 1
}

# ─── READ CURRENT VERSION ────────────────────────────────────────────────────

$pyprojectContent = Get-Content $PyprojectPath -Raw

if ($pyprojectContent -match 'version\s*=\s*"([0-9]+)\.([0-9]+)\.([0-9]+)"') {
    [int]$verMajor = $Matches[1]
    [int]$verMinor = $Matches[2]
    [int]$verPatch = $Matches[3]
} else {
    Write-Error "Could not parse version from $PyprojectPath"
    exit 1
}

$currentVersion = "$verMajor.$verMinor.$verPatch"

# ─── CALCULATE NEW VERSION ───────────────────────────────────────────────────

switch ($Bump) {
    "major" { $verMajor++; $verMinor = 0; $verPatch = 0 }
    "minor" { $verMinor++; $verPatch = 0 }
    "patch" { $verPatch++ }
}

$newVersion = "$verMajor.$verMinor.$verPatch"

# ─── CAPTURE LAST COMMIT MESSAGE ─────────────────────────────────────────────

$lastCommitMessage = git log -1 --format="%s"

# ─── SHOW PLAN ───────────────────────────────────────────────────────────────

Write-Info "Bump type    : $Bump"
Write-Info "Version      : $currentVersion  ->  $newVersion"
Write-Info "Release notes: $lastCommitMessage"
Write-Host ""

if ($DryRun) {
    Write-Warning "DRY RUN — no changes will be made."
    Write-Host ""
    Write-Host "Would update version in:"
    Write-Host "  $PyprojectPath"
    Write-Host "  $ConstantsPath"
    Write-Host "  $SpecPath"
    Write-Host ""
    Write-Host "Would run: python scripts/build_executable.py"
    Write-Host "Would run: git commit -am 'bump: v$newVersion'"
    Write-Host "Would run: git tag v$newVersion"
    Write-Host "Would run: git push"
    Write-Host "Would run: git push --tags"
    Write-Host "Would run: gh release create v$newVersion $ExePath --title 'TwitchAdAvoider v$newVersion' --notes '$lastCommitMessage'"
    exit 0
}

# ─── UPDATE VERSION FILES ────────────────────────────────────────────────────

Write-Info "Updating version files..."

$content = Get-Content $PyprojectPath -Raw
$content = $content -replace '(version\s*=\s*")[^"]+(")', "`${1}$newVersion`${2}"
Set-Content $PyprojectPath -Value $content -NoNewline
Write-Success "Updated $PyprojectPath"

$content = Get-Content $ConstantsPath -Raw
$content = $content -replace '(APP_VERSION\s*=\s*")[^"]+(")' , "`${1}$newVersion`${2}"
Set-Content $ConstantsPath -Value $content -NoNewline
Write-Success "Updated $ConstantsPath"

$content = Get-Content $SpecPath -Raw
$content = $content -replace "(?<=VERSION\s*=\s*')[^']+", $newVersion
Set-Content $SpecPath -Value $content -NoNewline
Write-Success "Updated $SpecPath"

Write-Host ""

# ─── BUILD ───────────────────────────────────────────────────────────────────

Write-Info "Building executable..."
python scripts/build_executable.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed (exit code $LASTEXITCODE). Release aborted."
    exit 1
}

if (-not (Test-Path $ExePath)) {
    Write-Error "Build finished but $ExePath not found. Release aborted."
    exit 1
}

Write-Success "Build complete: $ExePath"
Write-Host ""

# ─── CONFIRM BEFORE PUSH ─────────────────────────────────────────────────────

Write-Warning "About to push and create GitHub release v$newVersion."
$confirm = Read-Host "Continue? [Y/n]"

if ($confirm -ne "" -and $confirm -notmatch '^[Yy]') {
    Write-Warning "Aborted. Version files updated and exe built, but nothing pushed."
    Write-Host ""
    Write-Info "To finish manually:"
    Write-Host "  git commit -am 'bump: v$newVersion'"
    Write-Host "  git tag v$newVersion"
    Write-Host "  git push; git push --tags"
    Write-Host "  gh release create v$newVersion $ExePath --title 'TwitchAdAvoider v$newVersion' --notes '$lastCommitMessage'"
    exit 0
}

# ─── GIT OPERATIONS ──────────────────────────────────────────────────────────

Write-Info "Committing version bump..."
git commit -am "bump: v$newVersion"
if ($LASTEXITCODE -ne 0) { Write-Error "git commit failed"; exit 1 }

git tag "v$newVersion"
if ($LASTEXITCODE -ne 0) { Write-Error "git tag failed"; exit 1 }

Write-Info "Pushing commit and tags..."
git push
if ($LASTEXITCODE -ne 0) { Write-Error "git push failed"; exit 1 }

git push --tags
if ($LASTEXITCODE -ne 0) { Write-Error "git push --tags failed"; exit 1 }

# ─── GITHUB RELEASE ──────────────────────────────────────────────────────────

Write-Info "Creating GitHub release..."
gh release create "v$newVersion" "$ExePath" `
    --title "TwitchAdAvoider v$newVersion" `
    --notes "$lastCommitMessage"

if ($LASTEXITCODE -ne 0) {
    Write-Error "gh release create failed"
    exit 1
}

Write-Host ""
Write-Success "Released TwitchAdAvoider v$newVersion"
