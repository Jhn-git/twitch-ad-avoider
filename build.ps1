# TwitchAdAvoider Windows EXE Build Script
# Streamlined Windows executable build process

param(
    [switch]$NoClean,
    [switch]$SkipDeps
)

Write-Host "🚀 TwitchAdAvoider Windows Build Script" -ForegroundColor Green
Write-Host "Platform: Windows $(if ([Environment]::Is64BitProcess) { '64-bit' } else { '32-bit' })"
Write-Host "PowerShell: $($PSVersionTable.PSVersion)"

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found in PATH" -ForegroundColor Red
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

Write-Host "Executing: python build_executable.py $($pythonArgs -join ' ')" -ForegroundColor Yellow

try {
    python build_executable.py @pythonArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ Build completed successfully!" -ForegroundColor Green
        
        # Open dist folder for user
        if (Test-Path "dist") {
            Write-Host "Opening dist folder..." -ForegroundColor Cyan
            Start-Process "dist"
        }
    } else {
        Write-Host "`n❌ Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "❌ Build script execution failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n🎉 Windows build process complete!" -ForegroundColor Green