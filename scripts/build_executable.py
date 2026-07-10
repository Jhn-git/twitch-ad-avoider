#!/usr/bin/env python3
"""
TwitchAdAvoider Windows Build Script
Automated Windows executable building with PyInstaller.
"""

import os
import sys
import argparse
import subprocess
import shutil
import platform

APP_NAME = "twitchadavoider"


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print("[OK] SUCCESS")
        if result.stdout:
            print("Output:", result.stdout[-500:])  # Last 500 chars
        return True
    except subprocess.CalledProcessError as e:
        print("[FAIL] FAILED")
        print("Error:", e.stderr)
        return False


def clean_build():
    """Clean previous build artifacts."""
    print("[CLEAN] Cleaning previous builds...")

    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed {dir_name}/")

    # Clean .pyc files
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".pyc"):
                os.remove(os.path.join(root, file))


def check_dependencies():
    """Verify all required dependencies are installed."""
    print("[CHECK] Checking dependencies...")

    # Package mapping: name -> import_name
    required_packages = {
        "pyinstaller": "PyInstaller",
        "streamlink": "streamlink",
        "requests": "requests",
        "pywebview": "webview",
    }

    missing_packages = []
    for package, import_name in required_packages.items():
        # Check for the module in the current interpreter (the same one
        # build_executable() uses to invoke PyInstaller), not just anything
        # on PATH, which can point at an unrelated Python install.
        try:
            __import__(import_name)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [FAIL] {package} - MISSING")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n[ERROR] Missing packages: {', '.join(missing_packages)}")
        print("Install them with: pip install " + " ".join(missing_packages))
        return False

    return True


def build_executable(spec_file, build_type):
    """Build executable using specified spec file."""
    print(f"[BUILD] Building {build_type} executable...")

    if not os.path.exists(spec_file):
        print(f"[ERROR] Spec file not found: {spec_file}")
        return False

    # Use the same Python executable to ensure version consistency
    cmd = f'"{sys.executable}" -m PyInstaller {spec_file}'
    return run_command(cmd, f"Building {build_type} executable")


def get_file_size(filepath):
    """Get file size in human readable format."""
    size = os.path.getsize(filepath)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def show_results():
    """Display build results."""
    print("\n" + "=" * 60)
    print("BUILD RESULTS")
    print("=" * 60)

    if not os.path.exists("dist"):
        print("[ERROR] No dist/ directory found")
        return

    for item in os.listdir("dist"):
        item_path = os.path.join("dist", item)
        if os.path.isfile(item_path):
            size = get_file_size(item_path)
            print(f"  [FILE] {item}: {size}")
        elif os.path.isdir(item_path):
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(item_path)
                for filename in filenames
            )
            readable_size = get_file_size_from_bytes(total_size)
            print(f"  [DIR]  {item}/: {readable_size}")


def get_file_size_from_bytes(size_bytes):
    """Convert bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def create_launcher_script():
    """Create Windows launcher script inside the built app folder."""
    print("[LAUNCHER] Creating Windows launcher script...")

    # Windows batch file
    windows_launcher = """@echo off
echo Starting TwitchAdAvoider...
twitchadavoider.exe
pause
"""

    try:
        app_dir = os.path.join("dist", APP_NAME)
        with open(os.path.join(app_dir, "launch.bat"), "w") as f:
            f.write(windows_launcher)

        print("  [OK] Created Windows launcher script")
        return True
    except Exception as e:
        print(f"  [FAIL] Failed to create Windows launcher: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build TwitchAdAvoider executable")
    parser.add_argument("--no-clean", action="store_true", help="Skip cleaning previous builds")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency check")

    args = parser.parse_args()

    print("[START] TwitchAdAvoider Windows Build Script")
    print(f"Platform: {platform.system()} {platform.architecture()[0]}")
    print(f"Python: {sys.version.split()[0]}")

    # Check dependencies
    if not args.skip_deps and not check_dependencies():
        sys.exit(1)

    # Clean previous builds
    if not args.no_clean:
        clean_build()

    # Build executable
    success = build_executable("scripts/twitchadavoider.spec", "Windows")

    if success:
        create_launcher_script()
        show_results()
        print("\n[OK] Build completed successfully!")
        print("\nNext steps:")
        print(f"  1. Test the Windows executable in dist/{APP_NAME}/{APP_NAME}.exe")
        print("  2. Check that the WebView Stream Manager launches properly")
        print("  3. Verify embedded playback and clip creation")
    else:
        print("\n[ERROR] Build failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
