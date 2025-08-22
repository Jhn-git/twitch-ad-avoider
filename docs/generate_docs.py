#!/usr/bin/env python3
"""
Documentation generation script for TwitchAdAvoider.

This script provides convenient commands for building and managing project documentation
using Sphinx. It supports multiple output formats and includes cleanup functionality.

Usage:
    python generate_docs.py [command] [options]

Commands:
    html        Build HTML documentation (default)
    clean       Clean build artifacts
    help        Show available Sphinx targets
    linkcheck   Check for broken external links
    
Example:
    python generate_docs.py html    # Build HTML docs
    python generate_docs.py clean   # Clean build files
    
See Also:
    - docs/Makefile: Standard Sphinx Makefile with all available targets
    - docs/conf.py: Sphinx configuration file
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_sphinx_command(target: str, source_dir: str = ".", build_dir: str = "_build"):
    """
    Run a Sphinx build command.
    
    Args:
        target: Sphinx build target (html, clean, etc.)
        source_dir: Source directory containing RST files
        build_dir: Build output directory
        
    Returns:
        int: Return code from sphinx-build command
    """
    cmd = ["sphinx-build", "-M", target, source_dir, build_dir]
    
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, cwd=Path(__file__).parent)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error building documentation: {e}")
        return e.returncode
    except FileNotFoundError:
        print("Error: sphinx-build not found. Install Sphinx with: pip install sphinx")
        return 1


def main():
    """Main entry point for documentation generation script."""
    parser = argparse.ArgumentParser(
        description="Generate TwitchAdAvoider documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available targets:
  html       Build HTML documentation
  clean      Clean all build artifacts  
  linkcheck  Check external links
  help       Show all available targets
        """
    )
    
    parser.add_argument(
        "target", 
        nargs="?", 
        default="html",
        choices=["html", "clean", "help", "linkcheck"],
        help="Documentation build target (default: html)"
    )
    
    parser.add_argument(
        "--build-dir", 
        default="_build",
        help="Build output directory (default: _build)"
    )
    
    args = parser.parse_args()
    
    # Change to docs directory
    docs_dir = Path(__file__).parent
    if not docs_dir.exists():
        print(f"Error: Documentation directory not found: {docs_dir}")
        return 1
        
    print(f"Building documentation in: {docs_dir}")
    
    # Run the sphinx command
    return run_sphinx_command(args.target, ".", args.build_dir)


if __name__ == "__main__":
    sys.exit(main())