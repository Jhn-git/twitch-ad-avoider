# Shortcut: forwards to scripts/run.ps1 so it can be run from the repo root.
Push-Location $PSScriptRoot
try { & "$PSScriptRoot\scripts\run.ps1" @args } finally { Pop-Location }
