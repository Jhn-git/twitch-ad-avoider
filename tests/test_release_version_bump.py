"""Checks that the release version bump only rewrites the [project] version."""

import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "TwitchUtilities.psm1"

SAMPLE_PYPROJECT = """\
[project]
name = "twitchadavoider"
version = "2.0.15"
dependencies = [
    "typing-extensions>=4.0.0; python_version<'3.9'",
]

[tool.black]
target-version = ['py310', 'py311']

[tool.mypy]
python_version = "3.10"
warn_unused_configs = true
"""


def _bump(content: str, version: str) -> dict:
    """Run Get/Set-PyprojectVersion from the real PowerShell module on ``content``."""
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is not available")

    payload = json.dumps({"module": str(MODULE_PATH), "content": content, "version": version})
    script = f"""
    $ErrorActionPreference = 'Stop'
    $payload = ConvertFrom-Json @'
{payload}
'@
    Import-Module $payload.module -Force
    @{{
        current = Get-PyprojectVersion -Content $payload.content
        bumped = Set-PyprojectVersion -Content $payload.content -Version $payload.version
    }} | ConvertTo-Json -Compress
    """
    encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")

    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_bump_only_rewrites_project_version(newline):
    content = SAMPLE_PYPROJECT.replace("\n", newline)

    result = _bump(content, "2.0.16")

    assert result["current"] == "2.0.15"
    expected = content.replace('version = "2.0.15"', 'version = "2.0.16"')
    assert result["bumped"] == expected
    assert 'python_version = "3.10"' in result["bumped"]
    assert "python_version<'3.9'" in result["bumped"]


def test_bump_ignores_python_version_that_appears_first():
    mypy_first, project_first = SAMPLE_PYPROJECT.split("[tool.mypy]")
    content = "[tool.mypy]" + project_first + mypy_first

    result = _bump(content, "3.0.0")

    assert result["current"] == "2.0.15"
    assert 'python_version = "3.10"' in result["bumped"]
    assert 'version = "3.0.0"' in result["bumped"]


def test_repo_mypy_python_version_is_a_python_release():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    match = re.search(r'^python_version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)

    assert match is not None
    assert re.fullmatch(r"3\.\d+", match.group(1)), match.group(1)
