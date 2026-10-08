"""Tests for the headless Luna review script (no Codex calls are made)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "luna_review.py"
    spec = importlib.util.spec_from_file_location("luna_review", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


luna = load_module()

FINDING = {
    "kind": "bug",
    "severity": "high",
    "file": "src/a.py",
    "line": 3,
    "problem": "p",
    "fix": "f",
}


def report(**overrides):
    base = {"verdict": "minor", "summary": "s", "findings": [FINDING], "process_gaps": ""}
    base.update(overrides)
    return base


class LunaReviewTests(unittest.TestCase):
    def test_files_must_live_inside_repo(self):
        self.assertTrue(luna.is_repo_file("scripts/luna_review.py"))
        self.assertFalse(luna.is_repo_file("../outside.txt"))
        self.assertFalse(luna.is_repo_file(str(Path(sys.executable))))
        self.assertFalse(luna.is_repo_file("scripts"))

    def test_commits_must_be_positive(self):
        self.assertEqual(luna.positive_int("2"), 2)
        for bad in ("0", "-1"):
            with self.assertRaises(luna.argparse.ArgumentTypeError):
                luna.positive_int(bad)

    def test_check_report_accepts_valid_and_rejects_malformed(self):
        self.assertEqual(luna.check_report(report())["verdict"], "minor")
        for bad in (
            [],
            {"verdict": "clean"},
            report(findings="nope"),
            report(findings=[{"file": "x"}]),
        ):
            with self.assertRaises(luna.ReviewError):
                luna.check_report(bad)

    def test_render_sorts_by_severity_and_shows_gaps(self):
        low = dict(FINDING, severity="low", file="low.py")
        text = luna.render(report(findings=[low, FINDING], process_gaps="no tests"))
        self.assertLess(text.index("src/a.py:3"), text.index("low.py:3"))
        self.assertIn("Gaps in the process: no tests", text)
        self.assertIn("No findings.", luna.render(report(findings=[])))

    def test_empty_diff_is_an_error(self):
        args = luna.parse_args([])
        with patch.object(luna, "git", return_value=""):
            with self.assertRaises(luna.ReviewError):
                luna.build_prompt(args)

    def test_animation_mode_adds_code_only_brief(self):
        args = luna.parse_args(["--animations", "--files", "scripts/luna_review.py"])
        prompt = luna.build_prompt(args)
        self.assertIn("code level only", prompt)
        self.assertNotIn(
            "code level only",
            luna.build_prompt(luna.parse_args(["--files", "scripts/luna_review.py"])),
        )

    def test_oversized_diff_is_not_inlined(self):
        args = luna.parse_args([])
        huge = "x" * (luna.MAX_INLINE_DIFF + 1)
        with patch.object(luna, "git", side_effect=[huge, ""]):
            prompt = luna.build_prompt(args)
        self.assertIn("too large to inline", prompt)
        self.assertNotIn(huge, prompt)


if __name__ == "__main__":
    unittest.main()
