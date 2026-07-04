"""
Coverage for the preview-thumbnail layout/sizing fix.

Root cause (confirmed against the real running app's log + screenshots):
`_LandscapePreviewLabel` derived its height purely from its own width at a
fixed 16:9 ratio, with no regard for how much vertical room the "Stream"
panel actually had. On a wide-but-not-proportionally-tall maximized window
(e.g. 1920x1009), that formula demanded ~620px of height for the image alone
- more than `ChatPanel`'s own allotted height once the row above it
(StreamActions) and the row below (StatusDisplay/"Activity") took their
share - so the image's bottom edge extended past `ChatPanel`'s own bottom
edge and got clipped there. This matched the user's exact report ("goes
beyond the square and part of the preview image is being cut off") and was
reproduced deterministically offscreen using the real
MainWindow/FavoritesPanel/StreamActions/StatusDisplay/ChatPanel hierarchy at
the exact dimensions from the real app's log.

An earlier theory (QLabel's default sizeHint/minimumSizeHint tracking the
held pixmap, feeding back into the QGridLayout's column-width negotiation)
was investigated first but could not be reproduced under any resize pattern,
including a real showMaximized() call - the 60/40 column split held steady
throughout. That fix (below) is kept anyway since it removes a real
anti-pattern, but it did not address the actual bug.
"""

from PySide6.QtCore import QBuffer, QIODevice, QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from gui_qt.components.chat_panel import ChatPanel, _LandscapePreviewLabel
from gui_qt.components.favorites_panel import FavoritesPanel
from gui_qt.components.status_display import StatusDisplay
from gui_qt.components.stream_actions import StreamActions
from gui_qt.main_window import MainWindow
from src.config_manager import ConfigManager


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_test_image_bytes(width=1280, height=720):
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def _build_nested_window(tmp_path):
    app = _ensure_app()
    config = ConfigManager(tmp_path / "settings.json")
    window = MainWindow(config)
    chat_panel = ChatPanel()
    favorites = FavoritesPanel()
    window.add_component_to_layout(favorites, row=1, column=0)
    window.add_component_to_layout(chat_panel, row=1, column=1)
    chat_panel.set_channel("teststreamer")
    return app, window, chat_panel, favorites


def _build_full_app_window(tmp_path):
    """Build the complete real grid: StreamActions/Favorites/ChatPanel/StatusDisplay.

    Matches gui_qt/stream_gui.py's _setup_layout() row/column placement exactly,
    since the vertical-overflow bug only manifests once the rows above and
    below the preview are competing for the same window height.
    """
    app, window, chat_panel, favorites = _build_nested_window(tmp_path)
    stream_actions = StreamActions()
    status_display = StatusDisplay()
    window.add_component_to_layout(stream_actions, row=0, column=0, row_span=1, column_span=2)
    window.add_component_to_layout(status_display, row=2, column=0, row_span=1, column_span=2)
    return app, window, chat_panel, favorites, status_display


def test_chat_panel_column_stays_within_grid_share_during_drag(tmp_path):
    """Sanity check: the Stream panel column should stay near its 60% grid
    share once both columns' minimum sizes are satisfied.

    This is not a reproduction of the originally-reported overflow (see
    module docstring) - it's regression coverage so a future change can't
    silently break the 2:3 stretch ratio.
    """
    app, window, chat_panel, favorites = _build_nested_window(tmp_path)
    chat_panel.set_preview_image(_make_test_image_bytes())
    window.show()
    app.processEvents()

    start_width, end_width, steps = 900, 1900, 40
    for i in range(steps):
        w = round(start_width + (end_width - start_width) * i / (steps - 1))
        window.resize(w, window.height())
        app.processEvents()

        chat_col_width = chat_panel.geometry().width()
        favorites_col_width = favorites.geometry().width()
        columns_total = chat_col_width + favorites_col_width
        if columns_total == 0:
            continue  # layout not yet settled for this frame
        assert chat_col_width <= columns_total * 0.62 + 5, (
            f"ChatPanel column ({chat_col_width}px of {columns_total}px total) "
            f"exceeded its 60% grid share at step {i} (window width {w}px)"
        )

    window.close()


def test_preview_image_does_not_overflow_chat_panel_on_wide_maximized_window(tmp_path):
    """Reproduces the actual reported bug: preview image clipped by ChatPanel's
    own bottom edge on a wide-but-not-proportionally-tall maximized window.

    Uses the real Twitch thumbnail resolution (640x360) and the exact window
    dimensions seen in the real app's log for this exact failure (1920x1009,
    reached via an intermediate 902x823 "first maximize frame").
    """
    app, window, chat_panel, favorites, status_display = _build_full_app_window(tmp_path)

    pixmap = QPixmap(640, 360)
    pixmap.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    chat_panel.set_preview_image(bytes(buffer.data()))

    window.show()
    app.processEvents()

    for w, h in [(902, 823), (1920, 1009)]:
        window.resize(w, h)
        app.processEvents()

        label = chat_panel._preview_image_label
        label_bottom = label.geometry().y() + label.height()
        assert label_bottom <= chat_panel.height(), (
            f"Preview image (bottom={label_bottom}px) overflowed ChatPanel's "
            f"own bottom edge ({chat_panel.height()}px) at window size {w}x{h}"
        )

        status_bottom = status_display.geometry().y() + status_display.height()
        assert status_bottom <= window.height(), (
            f"StatusDisplay ('Activity') bottom edge ({status_bottom}px) fell "
            f"outside the window ({window.height()}px) at window size {w}x{h}"
        )

    window.close()


def test_preview_label_size_hint_is_independent_of_held_pixmap():
    """sizeHint/minimumSizeHint must stay constant regardless of pixmap size.

    A QLabel's default sizeHint tracks whatever pixmap it currently holds -
    this asserts the fix removes that coupling entirely.
    """
    _ensure_app()
    label = _LandscapePreviewLabel()

    expected = QSize(160, round(160 / (16 / 9)))
    assert label.sizeHint() == expected
    assert label.minimumSizeHint() == expected

    small = QPixmap(64, 36)
    small.fill(QColor("blue"))
    label.set_source_pixmap(small)
    assert label.sizeHint() == expected
    assert label.minimumSizeHint() == expected

    large = QPixmap(1920, 1080)
    large.fill(QColor("green"))
    label.set_source_pixmap(large)
    assert label.sizeHint() == expected
    assert label.minimumSizeHint() == expected

    label.deleteLater()
