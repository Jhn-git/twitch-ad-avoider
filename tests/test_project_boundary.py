"""Repository boundary checks."""

import base64
import json
import subprocess
import shutil
from pathlib import Path


def test_related_project_name_is_absent_from_repo_content():
    root = Path(__file__).resolve().parents[1]
    pattern = "ka" + "tch|Ka" + "tch"

    result = subprocess.run(
        ["rg", "-n", pattern, "."],
        cwd=root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr


def test_make_check_is_non_mutating():
    root = Path(__file__).resolve().parents[1]
    makefile = (root / "Makefile").read_text()

    assert "format-check:" in makefile
    assert "$(PYTHON) -m black --check ." in makefile
    assert "check: format-check lint typecheck" in makefile
    assert "check: format lint typecheck" not in makefile


def test_pyinstaller_spec_does_not_bundle_local_config():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "scripts" / "twitchadavoider.spec").read_text()

    assert 'os.path.join(ROOT, "config")' not in spec
    assert '"PyQt5"' not in spec
    assert '"PyQt6"' not in spec
    assert '"PySide2"' not in spec


def test_powershell_scripts_are_ascii_safe():
    root = Path(__file__).resolve().parents[1]
    script_paths = [
        root / "scripts" / "run.ps1",
        root / "scripts" / "update-daily-exe.ps1",
        root / "scripts" / "build.ps1",
        root / "scripts" / "release.ps1",
        root / "scripts" / "TwitchUtilities.psm1",
    ]

    for script_path in script_paths:
        script_path.read_text(encoding="ascii")


def test_powershell_scripts_parse_when_powershell_is_available():
    powershell = shutil.which("powershell")
    if powershell is None:
        return

    root = Path(__file__).resolve().parents[1]
    script_paths = [
        root / "scripts" / "run.ps1",
        root / "scripts" / "update-daily-exe.ps1",
        root / "scripts" / "build.ps1",
        root / "scripts" / "release.ps1",
        root / "scripts" / "TwitchUtilities.psm1",
    ]

    paths_json = json.dumps([str(path) for path in script_paths])
    parser_script = f"""
    $ErrorActionPreference = 'Stop'
    $paths = ConvertFrom-Json @'
{paths_json}
'@
    foreach ($path in $paths) {{
        $tokens = $null
        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $path,
            [ref]$tokens,
            [ref]$errors
        ) | Out-Null
        if ($errors.Count -gt 0) {{
            $messages = ($errors | ForEach-Object {{ $_.Message }}) -join '; '
            throw "$path parse failed: $messages"
        }}
    }}
    """
    encoded_script = base64.b64encode(parser_script.encode("utf-16le")).decode("ascii")

    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_script],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
