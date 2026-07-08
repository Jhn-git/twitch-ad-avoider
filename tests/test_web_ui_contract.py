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
