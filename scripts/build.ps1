# TwitchAdAvoider Windows EXE Build Script
# Streamlined Windows executable build process

param(
    [switch]$NoClean,
    [switch]$SkipDeps
)

Write-Host "[START] TwitchAdAvoider Windows Build Script" -ForegroundColor Green
Write-Host "Platform: Windows $(if ([Environment]::Is64BitProcess) { '64-bit' } else { '32-bit' })"
Write-Host "PowerShell: $($PSVersionTable.PSVersion)"

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found in PATH" -ForegroundColor Red
    exit 1
}

# Run the Python build script
$pythonArgs = @()

if ($NoClean) {
    $pythonArgs += "--no-clean"
}

if ($SkipDeps) {
    $pythonArgs += "--skip-deps"  
}

Write-Host "Executing: python scripts/build_executable.py $($pythonArgs -join ' ')" -ForegroundColor Yellow

try {
    python scripts/build_executable.py @pythonArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n[OK] Build completed successfully!" -ForegroundColor Green
        
        # Open dist folder for user
        if (Test-Path "dist") {
            Write-Host "Opening dist folder..." -ForegroundColor Cyan
            Start-Process "dist"
        }
    } else {
        Write-Host "`n[ERROR] Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "[ERROR] Build script execution failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[DONE] Windows build process complete!" -ForegroundColor Green