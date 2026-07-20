"""Repository boundary checks."""

import base64
import json
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_related_project_name_is_absent_from_repo_content():
    pattern = "ka" + "tch|Ka" + "tch"

    result = subprocess.run(
        ["rg", "-n", pattern, "."],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr


def test_make_check_is_non_mutating():
    makefile = (ROOT / "Makefile").read_text()

    assert "format-check:" in makefile
    assert "$(PYTHON) -m black --check ." in makefile
    assert "check: format-check lint typecheck" in makefile
    assert "check: format lint typecheck" not in makefile


def test_root_guide_files_are_local_only():

    result = subprocess.run(
        ["git", "check-ignore", "AGENTS.md", "CLAUDE.md", "TODO.md"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert set(result.stdout.splitlines()) == {"AGENTS.md", "CLAUDE.md", "TODO.md"}


def test_project_scripts_do_not_run_git_clean():
    checked_paths = [
        ROOT / "Makefile",
        *sorted((ROOT / "scripts").glob("*.ps1")),
        *sorted((ROOT / "scripts").glob("*.py")),
    ]

    for path in checked_paths:
        source = path.read_text()
        assert "git clean" not in source.lower(), f"{path} should not clean ignored files"


def test_pyinstaller_spec_does_not_bundle_local_config():
    spec = (ROOT / "scripts" / "twitchadavoider.spec").read_text()

    assert 'os.path.join(ROOT, "config")' not in spec
    assert '"PyQt5"' not in spec
    assert '"PyQt6"' not in spec
    assert '"PySide2"' not in spec


def test_powershell_scripts_are_ascii_safe():
    script_paths = [
        ROOT / "scripts" / "run.ps1",
        ROOT / "scripts" / "update-daily-exe.ps1",
        ROOT / "scripts" / "build.ps1",
        ROOT / "scripts" / "release.ps1",
        ROOT / "scripts" / "TwitchUtilities.psm1",
    ]

    for script_path in script_paths:
        script_path.read_text(encoding="ascii")


def test_powershell_scripts_parse_when_powershell_is_available():
    powershell = shutil.which("powershell")
    if powershell is None:
        return

    script_paths = [
        ROOT / "scripts" / "run.ps1",
        ROOT / "scripts" / "update-daily-exe.ps1",
        ROOT / "scripts" / "build.ps1",
        ROOT / "scripts" / "release.ps1",
        ROOT / "scripts" / "TwitchUtilities.psm1",
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
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
