# Shortcut: forwards to scripts/build.ps1 so it can be run from the repo root.
Push-Location $PSScriptRoot
try { & "$PSScriptRoot\scripts\build.ps1" @args } finally { Pop-Location }
