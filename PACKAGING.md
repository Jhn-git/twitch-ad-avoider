# TwitchAdAvoider Windows EXE Packaging Guide

This guide covers how to package TwitchAdAvoider into standalone Windows executables using PyInstaller.

## Quick Start

### Windows Users
```powershell
# Run the PowerShell build script
.\build.ps1

# Or with options
.\build.ps1 -NoClean
```


## Build Options

### Windows Build

The build system creates a single Windows executable (`twitchadavoider.spec`):
   - Includes all necessary features and dependencies
   - File size (~30MB)
   - Configured for Twitch streaming

### Build Script Options

```powershell
# Build Windows executable
.\build.ps1

# Skip dependency check
.\build.ps1 -SkipDeps

# Don't clean previous builds
.\build.ps1 -NoClean
```

Or using Python directly:
```bash
# Build executable
python build_executable.py
```

## Manual Windows Building

If you prefer to build manually:

```bash
# Windows build
pyinstaller twitchadavoider.spec
```

## Build Requirements

### System Requirements
- Python 3.8 or higher
- PyInstaller 6.0 or higher
- All project dependencies installed

### Dependencies
The build system will check for these required packages:
- `pyinstaller` - Packaging tool
- `streamlink` - Core streaming functionality
- `requests` - HTTP client
- `cryptography` - Security features

Install missing dependencies:
```bash
pip install pyinstaller streamlink requests cryptography
```

## Build Outputs

After building, you'll find:

```
dist/
├── TwitchAdAvoider.exe          # Windows build executable
└── launch.bat                   # Windows launcher script
```

## Windows Build Size

| Build Type | Windows |
|------------|--------|
| Standard   | ~30MB  |

*Size is approximate and may vary based on system configuration*

## Troubleshooting

### Common Build Issues

1. **Missing Dependencies**
   ```bash
   # Install all dependencies
   pip install -e .
   ```

2. **Import Errors**
   - Check that all modules are in the `hiddenimports` list in the spec file
   - Verify Python path includes the project directory

3. **Large Executable Size**
   - Check excludes list in spec file
   - Consider using directory distribution instead of single file

4. **GUI Not Working**
   - Ensure PySide6 is properly installed and included
   - Check that Qt platform plugins are bundled
   - Verify all Qt GUI components are in hidden imports
   - Ensure QSS stylesheet files are included in datas

### Windows-Specific Issues

- Windows Defender may flag the executable as suspicious (common with PyInstaller)
- Add exclusion for the dist/ folder in Windows Defender if needed
- Ensure Visual C++ Redistributable is installed on target systems
- Some antivirus software may quarantine the executable
- Test on clean Windows systems without development tools


## Advanced Configuration

### Customizing Spec Files

The `.spec` files can be customized for specific needs:

```python
# Add custom data files
datas=[
    ('my_data.txt', '.'),
    ('config/', 'config/'),
],

# Add hidden imports
hiddenimports=[
    'my_module',
    'another_module',
],

# Exclude unnecessary modules
excludes=[
    'matplotlib',
    'numpy',
],
```

### Build Hooks

Create custom PyInstaller hooks in `hooks/` directory:

```python
# hooks/hook-mymodule.py
hiddenimports = ['mymodule.submodule']
datas = [('mymodule/data', 'mymodule/data')]
```

## Distribution

### Single File vs Directory

**Single File** (default):
- Pros: Easy to distribute, single executable
- Cons: Slower startup, larger memory usage
- Good for: Simple distribution, portable apps

**Directory Distribution**:
```python
# In spec file, change to:
exe = EXE(..., onefile=False)
```
- Pros: Faster startup, smaller memory footprint
- Cons: Multiple files to distribute
- Good for: Local installation, frequent use

### Creating Windows Installers

Use Windows-specific installer tools:
- **Inno Setup**: Free installer for Windows applications
- **NSIS**: Nullsoft Scriptable Install System
- **WiX Toolset**: Windows Installer XML toolset
- **Advanced Installer**: Commercial solution with GUI

## Testing

Always test built executables:

1. **Windows Functionality Test**
   ```powershell
   # Test CLI mode
   .\TwitchAdAvoider.exe --help
   
   # Test GUI mode
   .\TwitchAdAvoider.exe
   ```

2. **Different Windows Environments**
   - Clean Windows VMs (Windows 10, Windows 11)
   - Different Python versions (if source available)
   - Various Windows hardware configurations

3. **Performance Test**
   - Startup time
   - Memory usage
   - Streaming performance

## Version Information

Add version info to Windows executables:

1. Create `version_info.txt`:
   ```
   VSVersionInfo(
     ffi=FixedFileInfo(
       filevers=(2,0,0,0),
       prodvers=(2,0,0,0),
       # ... more version info
     ),
     # ... string info
   )
   ```

2. Reference in spec file:
   ```python
   exe = EXE(..., version='version_info.txt')
   ```

## Icon Customization

Add custom application icon:

Windows executable icon: `.ico` file

```python
# In spec file
exe = EXE(..., icon='app_icon.ico')
```

## Security Considerations

- Antivirus software may flag PyInstaller executables
- Consider code signing certificates for distribution
- Test on multiple antivirus engines before release
- Document known false positives

## Performance Notes

1. **Import Optimization**
   - Lazy imports used where appropriate
   - Unnecessary modules excluded

2. **Spec File Configuration**
   - Excludes unnecessary packages
   - Uses specific hidden imports

3. **UPX Compression**
   - Enabled to reduce file size
   - Can reduce file size by 30-50%
   - May trigger antivirus warnings

## Support

For build issues:
1. Check this documentation
2. Review PyInstaller documentation
3. Check project issue tracker
4. Create detailed bug report with:
   - Build platform and Python version
   - Complete error messages
   - Spec file configuration

---

*This packaging system was designed for TwitchAdAvoider v2.0.0 and tested with PyInstaller 6.14.1 on Windows 10/11*