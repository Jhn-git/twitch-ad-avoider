# Session 05: Dropdown Popup Dark-Square Artifact — Resolved

Date: 2026-07-01

## What Happened

- Continued the session-04 investigation into the dark square artifact behind rounded combo/menu popup corners on Windows.
- Tried two OS-level hypotheses first, both live-tested in the real app and confirmed by the user to have **no visible effect**:
  1. `DwmSetWindowAttribute(..., DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_DONOTROUND)` to stop Windows 11 DWM's own auto corner-rounding from fighting our mask.
  2. Directly clearing the `CS_DROPSHADOW` window-class style bit via `GetClassLongPtrW`/`SetClassLongPtrW`.
- Instead of guessing a third OS-level fix, wrote a standalone diagnostic script that created a real `QComboBox` popup and dumped its actual live Win32/Qt state (HWND, mask rect vs widget rect, `WS_EX_LAYERED`, window-class style, `autoFillBackground`, and — critically — the container's direct child objects).
- That dump revealed the real root cause: `QComboBoxPrivateContainer` (Qt's internal popup host class) attaches its **own `QGraphicsDropShadowEffect`** to the container widget. This paints a soft offset shadow entirely inside Qt's own software compositing pipeline — completely independent of DWM, window-class styles, `WA_TranslucentBackground`, or our manually-applied `QRegion` mask, which is exactly why neither prior fix could touch it.
- Fixed it by clearing that effect: `widget.setGraphicsEffect(None)` inside the same deferred `QTimer.singleShot(0, ...)` refresh callback that already re-applies the rounded mask, so it's stripped every time the popup shows.
- Live-tested in the real app: the user confirmed the dark square is gone from the Favorites Quality dropdown.

## Key Decisions

- Kept both earlier OS-level fixes (`DWMWCP_DONOTROUND`, `CS_DROPSHADOW` strip) in place even though they turned out not to be the cause here — they're cheap, additive, fail silently, and the diagnostic showed `CS_DROPSHADOW` was never actually set on this system/Qt version, so we can't rule out it mattering on a different Windows/Qt combination.
- Treat direct runtime introspection (dumping real Win32/Qt object state) as the right escalation path once two theory-driven fixes fail to change the visible symptom, rather than continuing to guess from documentation alone.
- Accepted a minor remaining cosmetic issue: popup positioning is "a bit oddly positioned" relative to its anchor control. Not blocking, deferred for now.

## Files Changed

- `gui_qt/popup_utils.py` — added `_disable_dwm_corner_rounding`, `_strip_cs_dropshadow`, and `_strip_qt_graphics_shadow` (the actual fix), all wired into the existing deferred `_queue_mask_refresh` callback.
- `tests/test_popup_utils.py` — new file; focused `monkeypatch`-based tests for the DWM and `CS_DROPSHADOW` helpers (mechanism-only, since they don't change the visible outcome here).

## Verification

- Ran `.\.venv\Scripts\python.exe -m pytest tests/test_popup_utils.py tests/test_settings_tab.py tests/test_favorites_panel.py tests/test_chat_panel.py` — `15 passed`.
- Ran `.\.venv\Scripts\python.exe -m py_compile gui_qt/popup_utils.py tests/test_popup_utils.py`.
- Live-verified in the real desktop app (`python main.py`): opened the Favorites panel Quality dropdown before and after the `QGraphicsDropShadowEffect` fix — user confirmed the dark square is gone.
- Diagnostic script (scratchpad, not committed) confirmed `container.graphicsEffect()` is `None` after the fix, versus a live `QGraphicsDropShadowEffect` instance before it.

## Current Progress

- The dark-square popup host artifact that was open since session-04 is resolved for the Favorites Quality dropdown, which was the primary reported surface.
- The same fix applies to all popup surfaces via the shared `popup_utils.py` helpers (Settings tab combos, Favorites quality combo, chat clip-duration menu), since they all funnel through the same `_configure_popup_surface` → `_queue_mask_refresh` path.
- Popup positioning has a minor, non-blocking offset from its anchor control noted by the user as "a bit oddly positioned" — not yet investigated.

## Things We Haven't Tried Yet

- Explicitly re-confirming the fix visually on the Settings tab combos (`player_combo`, `quality_combo`, `log_level_combo`) and the chat panel clip-duration `QMenu`, not just the Favorites quality combo that was directly screenshotted.
- Confirming light-theme behavior (all live checks so far were in dark theme).
- Investigating the minor popup positioning offset if it becomes bothersome.

## Next Steps

- Only revisit popup positioning if it becomes a real annoyance; otherwise treat this investigation as closed.
- If a similar dark-shadow-behind-rounded-popup artifact ever resurfaces elsewhere, check `widget.graphicsEffect()` / `widget.children()` for a Qt-internal effect first, before assuming it's an OS/DWM-level issue.
