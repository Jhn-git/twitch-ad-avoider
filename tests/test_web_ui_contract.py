"""Lightweight checks for no-build web UI wiring."""

from pathlib import Path


def test_app_refreshes_favorites_on_startup_when_enabled():
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "gui_web" / "app.jsx").read_text()

    assert "refreshFavoritesOnStartup" in app_source
    assert "favorites_auto_refresh === false" in app_source
    assert "bridge.refresh_favorites()" in app_source
    assert "refreshFavoritesOnStartup(bridge, initial)" in app_source


def test_video_stage_shows_live_preview_image_without_playback():
    root = Path(__file__).resolve().parents[1]
    stage_source = (root / "gui_web" / "components" / "video_stage.jsx").read_text()
    index_source = (root / "gui_web" / "index.html").read_text()

    assert "preview?.preview_image_url" in stage_source
    assert "!hasPlayback && selectedChannel && preview?.is_live" in stage_source
    assert 'className="stream-preview-image"' in stage_source
    assert ".stream-preview-image" in index_source


def test_dropdown_has_viewport_aware_placement():
    root = Path(__file__).resolve().parents[1]
    dropdown_source = (root / "gui_web" / "components" / "dropdown.jsx").read_text()
    index_source = (root / "gui_web" / "index.html").read_text()

    assert "useLayoutEffect" in dropdown_source
    assert "getBoundingClientRect()" in dropdown_source
    assert "spaceBelow" in dropdown_source
    assert "spaceAbove" in dropdown_source
    assert "dropdown-${placement.direction}" in dropdown_source
    assert "maxHeight" in dropdown_source
    assert ".dropdown-up .dropdown-menu" in index_source
    assert "overflow-y: auto" in index_source


def test_clip_duration_split_button_stays_connected():
    root = Path(__file__).resolve().parents[1]
    stage_source = (root / "gui_web" / "components" / "video_stage.jsx").read_text()
    index_source = (root / "gui_web" / "index.html").read_text()

    assert 'className="clip-split"' in stage_source
    assert 'className="clip-duration-dropdown"' in stage_source
    assert 'buttonClassName="clip-menu-button"' in stage_source
    assert ".clip-split .btn.primary" in index_source
    assert ".clip-duration-dropdown.open .clip-menu-button" in index_source
    assert "border-radius: 7px 0 0 7px" in index_source
    assert "border-radius: 0 7px 7px 0" in index_source


def test_clip_saved_toast_is_event_driven_only():
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "gui_web" / "app.jsx").read_text()
    helpers_source = (root / "gui_web" / "helpers.jsx").read_text()
    manager_source = (root / "gui_web" / "components" / "stream_manager.jsx").read_text()

    assert 'event.type === "clip_created"' in app_source
    assert app_source.count('"Clip saved"') == 1
    assert 'window.__onStreamEvent?.({ type: "clip_created"' in helpers_source
    assert '"Clip saved"' not in manager_source
    assert 'if (!result.ok)' in manager_source
    assert 'result.error || "Clip failed"' in manager_source
