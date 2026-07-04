"""
Coverage for the preview dimming/desaturation behavior applied while a
stream is being watched (ChatPanel.set_streaming toggles preview dimming).

Regression coverage: an earlier implementation dimmed the preview via a
QGraphicsOpacityEffect installed directly on _LandscapePreviewLabel. That
effect suppressed the title_label overlay child's own stylesheet-painted
background entirely - a Qt quirk where a parent widget's QGraphicsEffect
breaks rendering of a child that has its own separate QGraphicsEffect (here,
title_label's QGraphicsDropShadowEffect) - even at opacity 1.0, i.e. before
any actual dimming occurred. This made the stream title caption invisible in
the real app immediately, not just while a stream was playing. The fix bakes
both the fade and the desaturation directly into pixel data (image) / an
inline stylesheet override (title), instead of a widget-level QGraphicsEffect.

These tests apply the real dark theme stylesheet (not just a bare
QApplication) because the title's background/padding come entirely from
`QLabel#streamPreviewTitle` in dark.qss/light.qss - without it, a bug that
merely suppresses that rule wouldn't show up in a pixel-level check.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from gui_qt.components.chat_panel import ChatPanel

_STYLES_DIR = Path(__file__).resolve().parent.parent / "gui_qt" / "styles"


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _apply_real_theme(app, theme="dark"):
    stylesheet = (_STYLES_DIR / f"{theme}.qss").read_text(encoding="utf-8")
    assets_dir = (_STYLES_DIR.parent / "assets").as_posix()
    app.setStyleSheet(stylesheet.replace("__ASSETS_DIR__", assets_dir))


def _build_panel_with_preview():
    app = _ensure_app()
    _apply_real_theme(app)
    panel = ChatPanel()
    panel.resize(400, 600)
    panel.show()

    label = panel._preview_image_label
    pixmap = QPixmap(640, 360)
    pixmap.fill(QColor("red"))
    label.set_source_pixmap(pixmap)
    label.set_title("Some Stream Title")
    app.processEvents()
    return app, panel, label


def test_title_overlay_stays_visible_and_styled_through_dim_cycle():
    """The title overlay must stay visible - and keep its QSS-painted
    background - across a dim/undim cycle driven by set_streaming().
    """
    app, panel, label = _build_panel_with_preview()
    title = label.title_label
    tx, ty = title.geometry().center().x(), title.geometry().center().y()

    def bar_pixel():
        return label.grab().toImage().pixelColor(tx, ty).getRgb()[:3]

    pixel_before = bar_pixel()
    assert title.isVisible()
    assert title.text() == "Some Stream Title"
    # The bar sits on rgba(0, 0, 0, 150) per QSS, over a pure red image, so
    # it must render darker than pure red - not fully transparent.
    assert pixel_before != (255, 0, 0)

    panel.set_streaming(True)
    app.processEvents()
    assert title.isVisible(), "Title overlay disappeared while dimmed"
    assert title.text() == "Some Stream Title"
    assert bar_pixel() != (255, 0, 0)

    panel.set_streaming(False)
    app.processEvents()
    assert title.isVisible()
    assert title.text() == "Some Stream Title"
    assert bar_pixel() == pixel_before

    panel.deleteLater()


def test_preview_image_desaturates_and_fades_while_dimmed():
    """The thumbnail should turn grayscale while dimmed and fully restore after."""
    app, panel, label = _build_panel_with_preview()

    def corner_pixel():
        return label.grab().toImage().pixelColor(5, 5).getRgb()[:3]

    assert corner_pixel() == (255, 0, 0)

    panel.set_streaming(True)
    app.processEvents()
    r, g, b = corner_pixel()
    assert r == g == b, "Image should be fully desaturated (grayscale) while dimmed"
    assert (r, g, b) != (255, 0, 0)

    panel.set_streaming(False)
    app.processEvents()
    assert corner_pixel() == (255, 0, 0)

    panel.deleteLater()
