"""Repository boundary checks."""

import subprocess
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
