"""Lightweight checks for no-build web UI wiring."""

from pathlib import Path


def test_app_refreshes_favorites_on_startup_when_enabled():
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "gui_web" / "app.jsx").read_text()

    assert "refreshFavoritesOnStartup" in app_source
    assert "favorites_auto_refresh === false" in app_source
    assert "bridge.refresh_favorites()" in app_source
    assert "refreshFavoritesOnStartup(bridge, initial)" in app_source
