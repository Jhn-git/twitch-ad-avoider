"""Tests for temporary recent-live highlighting in the favorites panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui_qt.components.favorites_panel import (
    FavoritesPanel,
    _ITEM_KIND_HEADER,
    _ITEM_KIND_ROLE,
)
from gui_qt.popup_utils import COMBO_POPUP_CONTAINER_NAME
from conftest import assert_popup_surface


RECENT_LIVE_ROLE = Qt.UserRole + 2


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _find_item(panel: FavoritesPanel, channel: str):
    items = panel.list_widget.findItems(channel, Qt.MatchExactly)
    assert items, f"Expected favorite item for {channel}"
    return items[0]


def _list_texts(panel: FavoritesPanel):
    return [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]


def test_mark_recently_live_sets_role_and_starts_timers():
    """Newly-live favorites are marked and tracked with active expiry timers."""
    _ensure_app()
    panel = FavoritesPanel()
    panel.add_favorite("ninja", is_live=True)
    panel.add_favorite("shroud", is_live=True)

    panel.mark_recently_live(["ninja", "shroud"])

    assert _find_item(panel, "ninja").data(RECENT_LIVE_ROLE) is True
    assert _find_item(panel, "shroud").data(RECENT_LIVE_ROLE) is True
    assert panel._recent_live_channels == {"ninja", "shroud"}
    assert panel._recent_live_timers["ninja"].isActive()
    assert panel._recent_live_timers["shroud"].isActive()

    panel.deleteLater()


def test_pinned_channels_render_under_section_headers():
    """Pinned favorites get their own section header and display ahead of others."""
    _ensure_app()
    panel = FavoritesPanel()
    panel.add_favorite("zeta", is_live=False, is_pinned=False)
    panel.add_favorite("alpha", is_live=True, is_pinned=True)
    panel.add_favorite("beta", is_live=False, is_pinned=True)
    panel.add_favorite("gamma", is_live=True, is_pinned=False)

    assert _list_texts(panel) == ["Pinned", "alpha", "beta", "Others", "gamma", "zeta"]
    assert panel.get_favorites() == ["alpha", "beta", "gamma", "zeta"]

    pinned_header = panel.list_widget.item(0)
    others_header = panel.list_widget.item(3)
    assert pinned_header.data(_ITEM_KIND_ROLE) == _ITEM_KIND_HEADER
    assert others_header.data(_ITEM_KIND_ROLE) == _ITEM_KIND_HEADER
    assert not (pinned_header.flags() & Qt.ItemIsSelectable)
    assert not (others_header.flags() & Qt.ItemIsSelectable)

    panel.deleteLater()


def test_updating_pin_status_rebuilds_section_headers():
    """Pinning a favorite moves it into the pinned section and adds headers as needed."""
    _ensure_app()
    panel = FavoritesPanel()
    panel.add_favorite("alpha", is_live=True, is_pinned=False)
    panel.add_favorite("beta", is_live=False, is_pinned=False)

    panel.update_pin_status("beta", True)

    assert _list_texts(panel) == ["Pinned", "beta", "Others", "alpha"]
    assert panel.get_favorites() == ["beta", "alpha"]

    panel.deleteLater()


def test_recent_live_expiry_clears_role_and_timer():
    """Timer expiry removes the temporary highlight state."""
    _ensure_app()
    panel = FavoritesPanel()
    panel.add_favorite("ninja", is_live=True)
    panel.mark_recently_live(["ninja"])

    panel._expire_recent_live("ninja")

    assert _find_item(panel, "ninja").data(RECENT_LIVE_ROLE) is False
    assert "ninja" not in panel._recent_live_channels
    assert "ninja" not in panel._recent_live_timers

    panel.deleteLater()


def test_update_favorite_status_offline_clears_recent_live_state():
    """Going offline clears the temporary recent-live cue immediately."""
    _ensure_app()
    panel = FavoritesPanel()
    panel.add_favorite("ninja", is_live=True)
    panel.mark_recently_live(["ninja"])

    panel.update_favorite_status("ninja", False)

    assert _find_item(panel, "ninja").data(RECENT_LIVE_ROLE) is False
    assert "ninja" not in panel._recent_live_channels
    assert "ninja" not in panel._recent_live_timers

    panel.deleteLater()


def test_quality_combo_popup_container_uses_shaped_host():
    """Quality combo popup host gets a shaped top-level surface when shown."""
    app = _ensure_app()
    panel = FavoritesPanel()
    panel.show()
    app.processEvents()

    panel.quality_combo.showPopup()
    app.processEvents()

    popup_container = panel.quality_combo.view().window()

    assert popup_container.objectName() == COMBO_POPUP_CONTAINER_NAME
    assert_popup_surface(popup_container)

    panel.quality_combo.hidePopup()
    panel.deleteLater()
