# TwitchAdAvoider Troubleshooting Guide

## Critical Issue: Hardcoded Path Resolution Problem

### Problem Description

The application is attempting to use a hardcoded path that includes an old project directory name `TwitchAdAvoider-lite-2`, even though the current project is located in `twitch-viewer`. This manifests as:

```
Fatal error in launcher: Unable to create process using '"C:\Users\thewa\Documents\GitHub\twitch-viewer\TwitchAdAvoider-lite-2\venv\Scripts\python.exe"  "C:\Users\thewa\Documents\GitHub\twitch-viewer\venv\Scripts\pip.exe" install -e . --quiet': The system cannot find the file specified.
```

### Root Cause Analysis

#### Most Likely Sources (High Priority)

1. **Windows Python Launcher Cache Issue** ⭐⭐⭐
   - The Windows Python launcher (`py.exe`) has cached the old project path
   - This affects how Python processes are spawned, especially in subprocess calls
   - The launcher maintains internal path mappings that can become stale

2. **Virtual Environment Path Corruption** ⭐⭐⭐
   - The virtual environment was created with absolute paths referencing the old directory name
   - Virtual environment activation scripts contain hardcoded paths
   - The `pyvenv.cfg` file may contain old path references

#### Other Potential Sources

3. **PowerShell Environment Variables**
   - PowerShell script may be setting or inheriting environment variables with old paths
   - `PYTHONPATH`, `VIRTUAL_ENV`, or custom environment variables

4. **Windows Registry Python Associations**
   - Python file associations in Windows registry pointing to old executable
   - COM object registrations with old paths

5. **Build Cache/PyInstaller Remnants**
   - Previous PyInstaller builds created executables with hardcoded paths
   - Build cache files containing old path references

6. **Windows File System Cache**
   - NTFS alternate data streams or file system metadata caching old paths
   - Windows Search indexer maintaining old path associations

7. **Git Hooks or IDE Configuration**
   - Git hooks or IDE settings referencing old paths
   - VSCode/PyCharm project configurations

### Diagnostic Steps

Run these commands to identify the root cause:

#### 1. Check Virtual Environment Integrity
```powershell
# Check venv configuration
Get-Content venv\pyvenv.cfg

# Check activation script
Get-Content venv\Scripts\Activate.ps1 | Select-String "TwitchAdAvoider-lite-2"

# Check Python executable path
venv\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.prefix)"
```

#### 2. Check Python Launcher
```powershell
# Check Python launcher configuration
py -c "import sys; print(sys.executable)"

# List all Python installations
py -0p
```

#### 3. Check Environment Variables
```powershell
# Check for problematic environment variables
Get-ChildItem Env: | Where-Object {$_.Value -like "*TwitchAdAvoider-lite-2*"}

# Check Python-specific variables
echo $env:PYTHONPATH
echo $env:VIRTUAL_ENV
echo $env:PATH | ForEach-Object {$_.Split(';')} | Select-String "TwitchAdAvoider-lite-2"
```

#### 4. Check Registry (Advanced)
```powershell
# Check Python registry entries (run as administrator)
Get-ItemProperty "HKLM:\SOFTWARE\Python\PythonCore\*\InstallPath" -ErrorAction SilentlyContinue
Get-ItemProperty "HKCU:\SOFTWARE\Python\PythonCore\*\InstallPath" -ErrorAction SilentlyContinue
```

### Solution Approaches

#### Quick Fix: Recreate Virtual Environment
```powershell
# Remove existing virtual environment
Remove-Item -Recurse -Force venv

# Create fresh virtual environment
python -m venv venv

# Activate and install dependencies
venv\Scripts\Activate.ps1
pip install -e .
```

#### Advanced Fix: Clear Python Launcher Cache
```powershell
# Clear Python launcher cache (Windows)
Remove-Item "$env:LOCALAPPDATA\py.ini" -ErrorAction SilentlyContinue
Remove-Item "$env:APPDATA\Python\*" -Recurse -Force -ErrorAction SilentlyContinue

# Clear pip cache
pip cache purge
```

#### Nuclear Option: Fresh Project Setup
```powershell
# Navigate to parent directory
cd ..

# Clone fresh copy
git clone <your-repo-url> twitch-viewer-fresh
cd twitch-viewer-fresh

# Create clean virtual environment
python -m venv venv
venv\Scripts\Activate.ps1
pip install -e .
```

#### Registry Cleanup (Run as Administrator)
```powershell
# Search and remove registry entries with old paths
# WARNING: Only run if you understand registry editing
$oldPath = "TwitchAdAvoider-lite-2"
Get-ChildItem "HKLM:\SOFTWARE\Python" -Recurse -ErrorAction SilentlyContinue | 
    Where-Object {$_.GetValue("") -like "*$oldPath*"}
```

### Environment Variable Cleanup
```powershell
# Check and clean user environment variables
[Environment]::GetEnvironmentVariables("User") | Where-Object {$_.Value -like "*TwitchAdAvoider-lite-2*"}

# Check and clean system environment variables (admin required)
[Environment]::GetEnvironmentVariables("Machine") | Where-Object {$_.Value -like "*TwitchAdAvoider-lite-2*"}
```

### Testing the Fix

After applying a solution, verify it works:

```powershell
# Test virtual environment
venv\Scripts\python.exe -c "print('Virtual env Python works')"

# Test pip installation
venv\Scripts\pip.exe --version

# Test streamlink
venv\Scripts\streamlink.exe --version

# Test application launch
python main.py --help
```

### Prevention

1. **Always use relative paths** in configuration files
2. **Recreate virtual environments** when moving/renaming project directories
3. **Clear Python caches** after major directory changes
4. **Use `python -m pip`** instead of direct pip executable calls
5. **Set explicit Python interpreter** in IDE settings

### Additional Resources

- [Python Virtual Environments Guide](https://docs.python.org/3/tutorial/venv.html)
- [Windows Python Launcher Documentation](https://docs.python.org/3/using/windows.html#launcher)
- [PowerShell Execution Policy](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies)

## OAuth Authentication Issues

### Problem: redirect_mismatch Error

If you encounter OAuth authentication errors like:
```
Authentication Failed
Error: redirect_mismatch
Please close this window and try again. http://localhost:8080/auth/callback?error=redirect_mismatch
```

This indicates a mismatch between the redirect URI configured in your Twitch application and what the code expects.

#### Solution: Update Twitch Application Settings

1. **Go to Twitch Developer Console**:
   - Visit: https://dev.twitch.tv/console
   - Log in with your Twitch account

2. **Select Your Application**:
   - Find your TwitchAdAvoider application
   - Click "Manage"

3. **Update OAuth Redirect URLs**:
   - In the "OAuth Redirect URLs" section
   - **Add**: `http://localhost:8080/auth/callback`
   - **Remove**: `http://localhost:8080` (if present)
   - Click "Save Changes"

4. **Configure Client Credentials**:
   - Make sure your `config/settings.json` has both:
     - `"twitch_client_id": "your_client_id_here"`
     - `"twitch_client_secret": "your_client_secret_here"`
   - These should match the credentials shown in your Twitch app settings

#### Expected Configuration

Your Twitch app should have:
- **Name**: TwitchAdAvoider (or your chosen name)
- **OAuth Redirect URLs**: `http://localhost:8080/auth/callback`
- **Category**: Game Integration
- **Client Type**: Public

### Problem: Token Exchange Failed (400 Error)

If you see "Authentication Successful!" in the browser but get:
```
Token exchange failed: 400
Authentication failed: Token exchange failed: 400
```

This means the client_secret is missing or incorrect.

#### Solution:
1. **Get Client Secret from Twitch**:
   - Go to https://dev.twitch.tv/console
   - Click "Manage" on your TwitchAdAvoider app
   - Copy the "Client Secret" (click "New Secret" if none exists)

2. **Update settings.json**:
   ```json
   {
     "twitch_client_id": "your_client_id_here",
     "twitch_client_secret": "your_client_secret_here"
   }
   ```

#### Testing Authentication

After updating your Twitch app settings:
1. Start TwitchAdAvoider: `python main.py`
2. Click "Authenticate with Twitch" in the GUI
3. Complete the OAuth flow in your browser
4. Verify you see "Authentication Successful!" message
5. Check that the application shows you as logged in

### Status: Issue Resolved ✅

✅ **Resolution Applied**: Virtual environment recreated and hardcoded paths fixed

**What Was Fixed**:
1. **Virtual Environment**: Removed corrupted `venv/` directory and recreated with correct paths
2. **Dependencies**: Successfully reinstalled all project dependencies via `pip install -e .`
3. **OAuth Configuration**: Updated redirect URI to `http://localhost:8080/auth/callback`
4. **Documentation**: Updated hardcoded URLs in:
   - `pyproject.toml` (project metadata URLs)
   - `README.md` (clone instructions)
   - `CONTRIBUTING.md` (setup instructions)
   - `docs/installation.rst` (example commands)

**Root Cause Confirmed**: Virtual environment corruption with hardcoded paths from old project directory name `TwitchAdAvoider-lite-2`

## Chat Message Sending Issues

### Problem: Messages Don't Appear in Local Chat

If your messages appear on the streamer's chat but don't show up in your local application chat, or you see timeout errors like:
```
Message timed out without confirmation from Twitch IRC: [your message]
```

**Root Cause**: The application was incorrectly waiting for PRIVMSG echoes instead of USERSTATE messages for confirmation.

### Solution Applied ✅

1. **Updated IRC Capabilities**: Now requests `twitch.tv/tags` and `twitch.tv/commands` for proper message confirmation
2. **USERSTATE Message Handling**: Messages are now confirmed via USERSTATE messages (the correct Twitch IRC method)
3. **Enhanced Logging**: Added detailed debug logging to track message sending and confirmation
4. **Message Tracking**: Implements proper pending message tracking for reliable confirmation

**What to Expect**: 
- Messages appear exactly once in local chat after Twitch confirms them via USERSTATE
- No more timeout errors for successfully sent messages  
- Clean logging without spurious warnings
- Messages appear on both the actual stream and in your local chat consistently

## Complete Resolution Status ✅

### All Issues Resolved Successfully

**✅ OAuth Authentication**: 
- Fixed redirect URI mismatch (`http://localhost:8080` → `http://localhost:8080/auth/callback`)
- Added proper client_secret support for token exchange
- OAuth flow now works completely end-to-end

**✅ Chat Message Sending**: 
- Implemented proper USERSTATE message confirmation (instead of PRIVMSG echoes)
- Messages appear exactly once in local chat after Twitch confirms them
- Messages appear on actual streams consistently
- Eliminated timeout errors and duplicate message displays

**✅ Logging and Diagnostics**:
- Clean production logging without spurious warnings
- Proper debug logging available when needed
- USERSTATE timing issues resolved

### System Architecture

The chat system now uses the correct Twitch IRC message confirmation flow:
1. **Send Message** → IRC PRIVMSG command sent to Twitch
2. **Twitch Processing** → Message appears on actual stream 
3. **USERSTATE Confirmation** → Twitch sends USERSTATE to confirm delivery
4. **Local Display** → Message added to application chat panel

This follows Twitch's official IRC specifications and provides reliable message delivery confirmation.

---

*Last updated: 2025-09-07*
*Issue tracking: RESOLVED - Virtual environment recreated and all hardcoded paths fixed*