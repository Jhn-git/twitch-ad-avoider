"""Lightweight checks for no-build web UI wiring."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_refreshes_favorites_on_startup_when_enabled():
    app_source = (ROOT / "gui_web" / "app.jsx").read_text()

    assert "refreshFavoritesOnStartup" in app_source
    assert "favorites_auto_refresh === false" in app_source
    assert "bridge.refresh_favorites()" in app_source
    assert "refreshFavoritesOnStartup(bridge, initial)" in app_source


def test_video_stage_shows_live_preview_image_without_playback():
    stage_source = (ROOT / "gui_web" / "components" / "video_stage.jsx").read_text()
    index_source = (ROOT / "gui_web" / "index.html").read_text()

    assert "preview?.preview_image_url" in stage_source
    assert "!isViewingActiveStream && selectedChannel && preview?.is_live" in stage_source
    assert 'className="stream-preview-image"' in stage_source
    assert ".stream-preview-image" in index_source


def test_player_volume_persists_through_ui_state():
    helpers_source = (ROOT / "gui_web" / "helpers.jsx").read_text()
    manager_source = (ROOT / "gui_web" / "components" / "stream_manager.jsx").read_text()
    stage_source = (ROOT / "gui_web" / "components" / "video_stage.jsx").read_text()

    assert "volume:" in helpers_source
    assert 'onUiState("volume", value)' in manager_source
    assert "video.volume = volumeRef.current" in stage_source
    assert '"volumechange"' in stage_source


def test_dropdown_has_viewport_aware_placement():
    dropdown_source = (ROOT / "gui_web" / "components" / "dropdown.jsx").read_text()
    index_source = (ROOT / "gui_web" / "index.html").read_text()

    assert "useLayoutEffect" in dropdown_source
    assert "getBoundingClientRect()" in dropdown_source
    assert "spaceBelow" in dropdown_source
    assert "spaceAbove" in dropdown_source
    assert "dropdown-${placement.direction}" in dropdown_source
    assert "maxHeight" in dropdown_source
    assert ".dropdown-up .dropdown-menu" in index_source
    assert "overflow-y: auto" in index_source


def test_clip_duration_split_button_stays_connected():
    stage_source = (ROOT / "gui_web" / "components" / "video_stage.jsx").read_text()
    index_source = (ROOT / "gui_web" / "index.html").read_text()

    assert 'className="clip-split"' in stage_source
    assert 'className="clip-duration-dropdown"' in stage_source
    assert 'buttonClassName="clip-menu-button"' in stage_source
    assert ".clip-split .btn.primary" in index_source
    assert ".clip-duration-dropdown.open .clip-menu-button" in index_source
    assert "border-radius: 7px 0 0 7px" in index_source
    assert "border-radius: 0 7px 7px 0" in index_source


def test_clip_button_has_persistent_edit_after_toggle_and_quick_mode():
    app_source = (ROOT / "gui_web" / "app.jsx").read_text()
    helpers_source = (ROOT / "gui_web" / "helpers.jsx").read_text()
    manager_source = (ROOT / "gui_web" / "components" / "stream_manager.jsx").read_text()
    stage_source = (ROOT / "gui_web" / "components" / "video_stage.jsx").read_text()
    index_source = (ROOT / "gui_web" / "index.html").read_text()

    assert "stream_manager_edit_after_clip" in helpers_source
    assert "event.open_editor !== false" in app_source
    assert "api.create_clip(clipDuration, behindLiveSeconds, editAfterClip)" in manager_source
    assert 'onUiState("stream_manager_edit_after_clip", !editAfterClip)' in manager_source
    assert "aria-pressed={editAfterClip}" in stage_source
    assert "Edit after" in stage_source
    assert ".clip-edit-mode.is-active" in index_source


def test_clip_saved_toast_is_event_driven_only():
    app_source = (ROOT / "gui_web" / "app.jsx").read_text()
    helpers_source = (ROOT / "gui_web" / "helpers.jsx").read_text()
    manager_source = (ROOT / "gui_web" / "components" / "stream_manager.jsx").read_text()

    assert 'event.type === "clip_created"' in app_source
    assert app_source.count('"Clip saved"') == 1
    assert 'type: "clip_created"' in helpers_source
    assert '"Clip saved"' not in manager_source
    assert "if (!result.ok)" in manager_source
    assert 'result.error || errorMessage || "Action failed"' in manager_source
    assert 'errorMessage: "Clip failed"' in manager_source


def test_clip_button_uses_backend_clip_readiness_not_just_recording_flag():
    stage_source = (ROOT / "gui_web" / "components" / "video_stage.jsx").read_text()
    helpers_source = (ROOT / "gui_web" / "helpers.jsx").read_text()

    assert "stream?.clip_ready" in stage_source
    assert "clipReadySeconds >= clipDuration" in stage_source
    assert "disabled={!isViewingActiveStream || !clipReady}" in stage_source
    assert "title={clipButtonTitle}" in stage_source
    assert "clip_ready_seconds" in helpers_source
    assert "clip_warmup_reason" in helpers_source


def test_recent_clip_editor_is_event_driven_and_reopenable():
    app_source = (ROOT / "gui_web" / "app.jsx").read_text()
    manager_source = (ROOT / "gui_web" / "components" / "stream_manager.jsx").read_text()
    stage_source = (ROOT / "gui_web" / "components" / "video_stage.jsx").read_text()
    index_source = (ROOT / "gui_web" / "index.html").read_text()

    assert 'event.type === "clip_edit_updated"' in app_source
    assert "setClipEditorOpen(true)" in app_source
    assert "bridge.get_recent_clip?.()" in app_source
    assert "<window.Components.ClipEditor" in manager_source
    assert "Edit Latest Clip" in stage_source
    assert "video.muted = true" in stage_source
    assert "video.muted = wasMuted" in stage_source
    assert 'src="components/clip_editor.jsx"' in index_source


def test_clip_editor_replays_boundaries_and_exposes_tail_and_save_actions():
    editor_source = (ROOT / "gui_web" / "components" / "clip_editor.jsx").read_text()
    helpers_source = (ROOT / "gui_web" / "helpers.jsx").read_text()

    assert "video.currentTime = safeStart" in editor_source
    assert "video.currentTime >= selectionEnd" in editor_source
    assert "const END_AUDITION_SECONDS = 5" in editor_source
    assert 'auditionModeRef.current === "end"' in editor_source
    assert "Math.max(selectionStart, selectionEnd - END_AUDITION_SECONDS)" in editor_source
    assert 'applySelection(selectionStart, selectionEnd - 1, "end")' in editor_source
    assert 'type="range"' in editor_source
    assert editor_source.count("max={previewDuration}") == 2
    assert "selectionEnd - minimumSelectionSeconds" in editor_source
    assert "selectionStart + minimumSelectionSeconds" in editor_source
    assert "Keep {window.AppHelpers.timeLabel(selectedDuration)}" in editor_source
    assert "request_clip_tail_extension(clip.id, 5)" in editor_source
    assert "retry_clip_edit_preparation(clip.id)" in editor_source
    assert "Boolean(clip?.can_edit)" in editor_source
    assert "const retryable = Boolean(clip?.retry_available) && !busy" in editor_source
    assert "Retry preparation" in editor_source
    assert "pendingTailSelectionRef" in editor_source
    assert "save_clip_edit(clip.id, selectionStart, selectionEnd, title)" in editor_source
    assert "Save &amp; Return" in editor_source
    assert "kebabSlug(title)" in editor_source
    assert "kebabSlug(value)" in helpers_source
