"""Headless quality pass: hand a diff to Luna (a local Codex run) and print its findings.

Luna runs read-only inside this repo, so it can open any file for context but cannot edit
anything. It needs a locally signed-in Codex CLI; no keys are handled here.

    python scripts/luna_review.py                 # uncommitted work (tracked diff + new files)
    python scripts/luna_review.py --base main     # everything since main
    python scripts/luna_review.py --commits 3     # the last 3 commits
    python scripts/luna_review.py --files src/webapi.py gui_web/app.jsx
    python scripts/luna_review.py --animations    # code-level animation pass only
    python scripts/luna_review.py --dry-run       # print the prompt, don't call Codex

Exit code: 0 clean or findings printed, 1 on a tool failure.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = "gpt-6-luna"
DEFAULT_EFFORT = "high"
DEFAULT_TIMEOUT = 900
MAX_INLINE_DIFF = 150_000  # bytes; larger diffs are left for Luna to read with `git diff`
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "summary", "findings", "process_gaps"],
    "properties": {
        "verdict": {"type": "string", "enum": ["clean", "minor", "needs_work"]},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "severity", "file", "line", "problem", "fix"],
                "properties": {
                    "kind": {"type": "string", "enum": ["bug", "issue", "qol"]},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "problem": {"type": "string"},
                    "fix": {"type": "string"},
                },
            },
        },
        "process_gaps": {"type": "string"},
    },
}

BASE_BRIEF = """You are Luna, doing the final quality pass on finished work in this repo.
Another AI wrote the change and believes it is done. Your job is to find what it missed.

Rules:
- You are read-only. Do not edit files. Open any file you need for context: the full changed
  files, their callers, and the tests. Read AGENTS.md first for the repo's conventions.
- Report only real, specific findings you can point to (file + line). Skip style nitpicks that
  Black/flake8 already enforce. Do not invent problems to look useful; "clean" is a valid verdict.
- Kinds: bug = wrong behavior or crash; issue = fragile, risky, untested or inconsistent
  code; qol = a small improvement that makes the app nicer to use or maintain.
- Severity: high = breaks users or data; medium = likely to bite; low = minor.
- Give each finding a concrete fix in one or two sentences.
- Check the tests: is the new behavior covered, and would the tests fail if it broke?
- `process_gaps`: one or two sentences on anything about how this work was done or checked that
  left gaps (missing tests, unverified assumptions). Empty string if none.
"""

ANIMATION_BRIEF = """This is an ANIMATION pass, code level only. Do not judge how it looks or feels.
Review only the animation code itself: timers/intervals/requestAnimationFrame that are never
cleaned up, listeners that leak, work done every frame that could be cached, layout-thrashing
properties animated instead of transform/opacity, missing prefers-reduced-motion handling,
animations that keep running when hidden or unmounted, state updates racing with unmount,
and CSS keyframes/transitions that conflict or are dead. Ignore non-animation code."""


class ReviewError(RuntimeError):
    pass


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=NO_WINDOW,
    )
    if proc.returncode != 0:
        raise ReviewError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def is_repo_file(name: str) -> bool:
    path = (REPO_ROOT / name).resolve()
    return path.is_file() and REPO_ROOT in path.parents


def gather_target(args: argparse.Namespace) -> tuple[str, str]:
    """Return (description of what's under review, inline diff or file listing)."""
    if args.files:
        missing = [f for f in args.files if not is_repo_file(f)]
        if missing:
            raise ReviewError(f"Not a file inside the repo: {', '.join(missing)}")
        return "these whole files: " + ", ".join(args.files), ""
    if args.base:
        return f"all changes since `{args.base}`", git("diff", f"{args.base}...HEAD")
    if args.commits:
        return f"the last {args.commits} commit(s)", git("diff", f"HEAD~{args.commits}", "HEAD")
    diff = git("diff", "HEAD")
    new_files = [f for f in git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    if new_files:
        diff += "\n\nNew untracked files (read them from disk):\n" + "\n".join(new_files)
    return "uncommitted work (`git diff HEAD` plus new files)", diff


def build_prompt(args: argparse.Namespace) -> str:
    target, diff = gather_target(args)
    parts = [BASE_BRIEF]
    if args.animations:
        parts.append(ANIMATION_BRIEF)
    if args.focus:
        parts.append(f"Extra focus from the author: {args.focus}")
    parts.append(f"Review target: {target}.")
    if args.files:
        parts.append("Read each listed file in full.")
    elif not diff.strip():
        raise ReviewError("Nothing to review: the diff is empty.")
    elif len(diff.encode("utf-8")) > MAX_INLINE_DIFF:
        parts.append("The diff is too large to inline. Run the equivalent `git diff` yourself.")
    else:
        parts.append("Diff:\n\n" + diff)
    return "\n\n".join(parts)


def codex_command() -> str:
    npm = Path(os.environ.get("APPDATA", "")) / "npm" / "codex.cmd"
    for candidate in (shutil.which("codex.cmd"), shutil.which("codex"), str(npm)):
        if candidate and Path(candidate).is_file():
            return candidate
    raise ReviewError("Couldn't find the Codex CLI. Install it and sign in first.")


def kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            creationflags=NO_WINDOW,
        )
    proc.kill()


def ask_luna(prompt: str, effort: str, timeout: int) -> dict:
    work = Path(tempfile.mkdtemp(prefix="luna-review-"))
    schema_file, out_file = work / "schema.json", work / "out.json"
    schema_file.write_text(json.dumps(SCHEMA), encoding="utf-8")
    cmd = [
        codex_command(),
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--model",
        MODEL,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "--sandbox",
        "read-only",
        "--output-schema",
        str(schema_file),
        "--output-last-message",
        str(out_file),
        "--cd",
        str(REPO_ROOT),
        "-",
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=NO_WINDOW,
        )
        try:
            stdout, stderr = proc.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            kill_tree(proc)
            proc.communicate()
            raise ReviewError(f"Luna took longer than {timeout} seconds.") from exc
        if proc.returncode != 0:
            raise ReviewError(
                (stderr or stdout or "Luna stopped without an answer.").strip()[-800:]
            )
        try:
            return check_report(json.loads(out_file.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReviewError("Luna's answer wasn't readable JSON.") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_report(report: object) -> dict:
    """Fail loudly on a report that doesn't match SCHEMA instead of crashing in render()."""
    if not isinstance(report, dict):
        raise ReviewError("Luna's report wasn't a JSON object.")
    finding_keys = set(SCHEMA["properties"]["findings"]["items"]["required"])
    missing = set(SCHEMA["required"]) - set(report)
    findings = report.get("findings")
    if missing or not isinstance(findings, list):
        raise ReviewError("Luna's report is missing required fields.")
    for finding in findings:
        if not isinstance(finding, dict) or finding_keys - set(finding):
            raise ReviewError("Luna's report has a malformed finding.")
    return report


def render(report: dict) -> str:
    findings = report.get("findings", [])
    order = {"high": 0, "medium": 1, "low": 2}
    findings = sorted(findings, key=lambda f: order.get(f.get("severity"), 3))
    lines = [f"Verdict: {report.get('verdict')}", report.get("summary", ""), ""]
    for i, f in enumerate(findings, 1):
        where = f"{f['file']}:{f['line']}" if f.get("line") else f["file"]
        lines.append(f"{i}. [{f['severity']}/{f['kind']}] {where}")
        lines.append(f"   Problem: {f['problem']}")
        lines.append(f"   Fix: {f['fix']}")
    if not findings:
        lines.append("No findings.")
    if report.get("process_gaps"):
        lines += ["", f"Gaps in the process: {report['process_gaps']}"]
    return "\n".join(lines)


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--base", help="review everything since this ref (e.g. main)")
    target.add_argument("--commits", type=positive_int, help="review the last N commits")
    target.add_argument("--files", nargs="+", help="review whole files instead of a diff")
    parser.add_argument("--animations", action="store_true", help="code-level animation pass only")
    parser.add_argument("--focus", help="extra thing for Luna to look at")
    parser.add_argument("--effort", default=DEFAULT_EFFORT, help=f"default {DEFAULT_EFFORT}")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds")
    parser.add_argument("--json", action="store_true", help="print the raw JSON report")
    parser.add_argument("--dry-run", action="store_true", help="print the prompt and stop")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        prompt = build_prompt(args)
        if args.dry_run:
            print(prompt)
            return 0
        report = ask_luna(prompt, args.effort, args.timeout)
    except ReviewError as exc:
        print(f"luna_review: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
