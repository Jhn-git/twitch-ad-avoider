# Session 34: Headless Luna Review Tool

Date: 2026-10-08

## What Happened

User added a standing rule to the (gitignored) `AGENTS.md`: after finishing work, spawn a "Luna"
subagent for a full quality pass (bugs, issues, QoL), at most one spawn per session unless Jhn
approves more. They asked for the "how" to be clarified, tested, and possibly turned into a small
headless tool. No app code changed this session.

### 1. The tool

- New `scripts/luna_review.py` (stdlib only, Python 3.10+). It runs the local, signed-in Codex CLI
  headlessly: `codex exec --ephemeral --ignore-user-config --sandbox read-only --output-schema ...`.
  Luna can read any file in the repo but cannot edit anything.
- Targets: uncommitted work (default: `git diff HEAD` plus untracked files), `--base REF`,
  `--commits N`, or `--files a b` for whole files. `--focus "..."` adds a steer; `--effort` (default
  `high`), `--timeout`, `--json`, `--dry-run` (prints the prompt, no Codex call).
- Output is a schema-constrained report: verdict (clean/minor/needs_work), summary, findings
  (bug/issue/qol, severity, file:line, problem, fix) and a "gaps in the process" note.
- Model is auto-picked: `latest_luna_model()` reads Codex's own `models_cache.json`
  (`$CODEX_HOME` or `~/.codex`) and takes the highest `gpt-<version>-luna`; falls back to
  `gpt-6-luna` if the list is unreadable. `--model` pins one. Today this resolves to `gpt-6-luna`.
- `tests/test_luna_review.py`: 7 tests (path containment, positive `--commits`, report-shape
  validation, severity sort, empty diff, oversized diff not inlined, latest-model pick/fallback).
- `AGENTS.md` (local only) now has a short "How to spawn Luna" section under the rule.

### 2. Lessons and fixes found while testing

- **`--ignore-rules` breaks file reads.** Copied from an existing reference project's text-only
  Codex calls; in this read-only review it made Codex reject every shell command ("blocked by
  policy"), so Luna reported it couldn't read anything. Removed. `--ignore-user-config` is fine.
- The real test run (Luna reviewing the tool itself, medium effort, ~1 minute) found three real
  issues, all fixed: `--files` accepted paths outside the repo, a malformed report would crash
  `render()` instead of failing cleanly, and `--commits 0`/negatives were accepted.
- Model was first hard-coded to the older `gpt-5.6-luna`; Jhn pointed out 6.0 is current. Fixed,
  then replaced the hard-coded ID with the auto-pick above.
- An animations mode (code-level pass) was built, then removed: it came from a different content
  project and doesn't belong here. The sentence about animations was also removed from `AGENTS.md`.

### 3. Commits (local, not pushed)

`feat: Add headless Luna review script...`, `fix: Use gpt-6-luna...`,
`feat: Auto-pick the newest Luna model...`, `refactor: Drop animation mode...`.

## What Was NOT Done

- **Nothing pushed.**
- **No full-size review on gpt-6-luna yet.** The only real review ran on `gpt-5.6-luna`; 6.0 was
  smoke-tested with a one-word prompt in the same read-only mode. First real use will be its first
  real test. The two test runs already used this session's one-spawn budget.
- **`--effort` default is `high`**; an existing reference project uses `max`. Jhn hasn't chosen.
- Codex config (`default_subagent_model`) and the reference project's own Luna runner still name the
  older `gpt-5.6-luna`, and that project passes `--ignore-rules`, which would break any call there
  that needs file reads. Both are outside this repo; left untouched.
- The model list only refreshes when Codex itself refreshes it, so a brand-new Luna may take a
  while to be auto-picked.
- `make check` fails on Black for `scripts/probe_twitch_vod_audio.py` and its test. Pre-existing and
  unrelated; not touched.

## Next

- Use `python scripts/luna_review.py` at the end of the next real piece of work and judge whether the
  findings are useful; adjust the prompt or effort from that.
