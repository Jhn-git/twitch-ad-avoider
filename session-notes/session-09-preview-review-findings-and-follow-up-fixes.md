# Session 09: Preview Review Findings + Follow-Up Fix List

Date: 2026-07-04

Continuation of the recent preview work from [session-06-stream-preview-thumbnail-and-resize-bug.md](session-06-stream-preview-thumbnail-and-resize-bug.md), [session-07-preview-resize-fix-and-title-overlay.md](session-07-preview-resize-fix-and-title-overlay.md), and [session-08-preview-dimming-and-title-regression-fix.md](session-08-preview-dimming-and-title-regression-fix.md).

This session was a code-review pass focused on the latest preview/dimming changes plus adjacent recent refactors (settings, config wiring, reconnect logic, and test health). The goal was not to implement fixes yet, but to identify the highest-value cleanup and repair work before starting the next coding pass.

## What Happened

- Reviewed the recent change set centered on stream preview fetching, preview rendering, dimming while streaming, settings wiring, and related tests.
- Ran targeted tests for the changed areas in the repo venv: **69 passed**.
- Also checked full-suite health: the full test run still fails during collection because `tests/test_katch_*` imports a `katch` package that is not present in this checkout.
- Main conclusion: the app is not wildly inefficient overall, but preview/state/settings logic is now spread across enough places that it is getting easier to miss edge cases and harder to reason about confidently.

## Concrete Fixes To Make

1. **Fix the “turn previews off” behavior first.**
   - Disabling stream previews in Settings does not fully shut the feature off for the current selection.
   - Existing preview content can remain visible, and in-flight preview results can still repaint the UI after the setting is turned off.
   - Why this matters: this is the most visible user-facing issue and makes the setting feel broken/untrustworthy.

2. **Fix the type-checking config mistake.**
   - `tool.mypy.python_version` in `pyproject.toml` was bumped to the app version (`2.0.11`) instead of a real Python version.
   - Why this matters: users may never notice directly, but one of the repo’s safety/quality checks is now misconfigured.

3. **Make stream-preview requests use the app’s existing timeout settings.**
   - The preview feature currently hardcodes its own request timeout instead of following the existing config-driven timeout behavior.
   - Why this matters: behavior becomes inconsistent on slow/flaky connections, and the settings surface is less trustworthy.

4. **Stop the app from doing one last favorites refresh while closing.**
   - There is a queued one-shot refresh path that can still fire after shutdown starts.
   - Why this matters: small polish issue, but it can cause weird “still doing work while closing” behavior and noisy logs.

5. **Clean up the broken `katch` test situation separately.**
   - Targeted changed-area tests passed, but the full suite still fails because `tests/test_katch_config.py` and `tests/test_katch_keyword_matcher.py` import a missing `katch` package.
   - Why this matters: “run all tests” should mean something again; this is repo health, not a preview-feature bug.

## Logic / Maintainability Follow-Ups Worth Doing

1. **Centralize preview state logic first.**
   - Preview behavior is currently split across `StreamGUI`, `StreamPreviewController`, `ChatPanel`, settings, and config.
   - Why this matters: this one cleanup likely fixes multiple edge cases and makes the feature much easier to reason about.

2. **Reduce settings plumbing duplication.**
   - Settings have to be wired in multiple places: defaults, validation, UI load, UI save, and sometimes live runtime handling.
   - Why this matters: this is a “works until one piece is forgotten” pattern, and it is where subtle bugs are slipping in.

3. **Decide whether preview fetching should cache or reuse work.**
   - Re-selecting the same favorite can trigger fresh fetches again, and stale work is often ignored only after the network/thread work already happened.
   - Why this matters: this is the main place with clear avoidable extra work.

4. **Clean out dead or misleading settings.**
   - Some settings/config fields appear supported but do not really drive meaningful runtime behavior right now.
   - Why this matters: lowers mental overhead and makes the code easier to trust.

5. **Eventually replace the giant config validator with something more table-driven.**
   - `ConfigManager._validate_setting()` is doing too much in one large `if/elif` chain.
   - Why this matters: not urgent for performance, but strong value for long-term maintainability and safer future changes.

## Logic Quality Notes

- The app is **not** broadly overcomplicated in the “doing way too much work” sense.
- The status-checking path is actually pretty good: batched Twitch GQL requests in `StatusMonitor` are the right shape for efficiency.
- The bigger issue is **state sprawl**, not raw slowness.
- The preview feature is where logic is now most fragmented.
- The reconnect logic is long, but its core behavior is still reasonable; it feels more busy than fundamentally bad.

## Verification Performed

- Targeted changed-area tests in the repo venv: **69 passed**.
- Full suite check: collection fails on the pre-existing `katch` import problem.
- Also directly reproduced a real preview-setting issue: turning previews off does not currently clear/suppress preview UI the way a user would expect.

## Recommended Fix Order

1. Fix preview-off behavior.
2. Fix mypy config.
3. Wire preview requests to the existing timeout settings.
4. Stop the shutdown-time extra refresh.
5. Repair full-suite `katch` test health.
6. Then do the bigger architecture cleanups (preview-state centralization, settings deduplication, config cleanup, validator refactor).

## Current Status

- No implementation changes were made in this review pass.
- This note is the handoff / fix-context list for the next coding session.
- Once implementation starts, the best first move is the preview-off bug, since it is the clearest user-visible correctness issue in the current state.
