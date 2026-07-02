"""Tests for stream-side clip control wiring.

Deliberate exception to AGENTS.md's "skip GUI tests" guidance: this covers
non-trivial Win32/DWM ctypes logic (corner rounding, CS_DROPSHADOW stripping)
with no other regression coverage.
"""

from PySide6.QtWidgets import QApplication, QMenu, QToolButton

from gui_qt.components.chat_panel import ChatPanel
from conftest import assert_popup_surface


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_clip_split_button_exposes_targeted_style_hooks():
    """Clip controls keep stable object names for targeted stylesheet rules."""
    _ensure_app()
    panel = ChatPanel()

    clip_button = panel.findChild(QToolButton, "clipSplitButton")
    clip_menu = panel.findChild(QMenu, "clipDurationMenu")

    assert clip_button is not None
    assert clip_menu is not None
    assert clip_button.menu() is clip_menu
    assert [action.text() for action in clip_menu.actions()] == [
        "Last 30s",
        "Last 1 min",
        "Last 2 min",
        "Last 5 min",
    ]

    panel.deleteLater()


def test_clip_duration_menu_uses_shaped_popup_surface():
    """Clip duration menu configures its real top-level window for rounded corners."""
    app = _ensure_app()
    panel = ChatPanel()
    panel.set_streaming(True)
    panel.show()
    app.processEvents()

    clip_button = panel.findChild(QToolButton, "clipSplitButton")
    clip_menu = panel.findChild(QMenu, "clipDurationMenu")
    assert clip_button is not None
    assert clip_menu is not None

    clip_menu.popup(clip_button.mapToGlobal(clip_button.rect().bottomLeft()))
    app.processEvents()

    assert_popup_surface(clip_menu)

    clip_menu.close()
    panel.deleteLater()
