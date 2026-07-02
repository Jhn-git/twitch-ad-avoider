"""Helpers for shaping popup hosts so rounded styles render cleanly on Windows."""

from __future__ import annotations

import sys
import ctypes
import ctypes.wintypes

from PySide6.QtCore import QEvent, QObject, QRectF, QTimer, Qt
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QComboBox, QMenu, QWidget

from src.logging_config import get_logger


logger = get_logger(__name__)

COMBO_POPUP_CONTAINER_NAME = "comboPopupContainer"
POPUP_SURFACE_RADIUS = 6

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DONOTROUND = 1

GCL_STYLE = -26
CS_DROPSHADOW = 0x00020000


class _RoundedPopupSurfaceFilter(QObject):
    """Apply a rounded top-level mask whenever a popup surface changes size."""

    def __init__(self, radius: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._radius = radius

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(watched, QWidget) and event.type() in {
            QEvent.Type.Move,
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            _queue_mask_refresh(watched, self._radius)
        return False


def _apply_rounded_mask(widget: QWidget, radius: int) -> None:
    """Match the popup window silhouette to the rounded body painted in QSS."""
    rect = widget.rect()
    if rect.isEmpty():
        return

    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


def _install_surface_filter(widget: QWidget, radius: int) -> None:
    """Keep a popup mask in sync with the actual top-level surface size."""
    event_filter = getattr(widget, "_rounded_popup_surface_filter", None)
    if event_filter is None:
        event_filter = _RoundedPopupSurfaceFilter(radius, widget)
        widget.installEventFilter(event_filter)
        widget._rounded_popup_surface_filter = event_filter

    _queue_mask_refresh(widget, radius)


def _disable_dwm_corner_rounding(widget: QWidget) -> None:
    """Stop Windows 11 DWM's own corner-rounding/shadow from fighting our mask.

    NoDropShadowWindowHint only suppresses the legacy CS_DROPSHADOW window-class
    shadow; it does nothing to DWM's separate composited corner rounding, which
    otherwise shows through as a dark square behind our manually-painted mask.
    """
    if sys.platform != "win32":
        return

    try:
        hwnd = int(widget.winId())
        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(DWMWCP_DONOTROUND)
        result = dwmapi.DwmSetWindowAttribute(
            ctypes.wintypes.HWND(hwnd),
            ctypes.wintypes.DWORD(DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
        if result != 0:
            logger.debug("DwmSetWindowAttribute returned HRESULT 0x%x for popup host", result)
    except (OSError, AttributeError, ValueError) as exc:
        logger.debug("Skipping DWM corner-rounding override: %s", exc)


def _declare_signature(func, argtypes: list, restype) -> None:
    """Best-effort ctypes signature declaration.

    Real ctypes function pointers support assigning `.argtypes`/`.restype`; the
    plain-object doubles used in tests to stand in for `ctypes.windll.user32` are
    bound methods, which don't support attribute assignment at all. Swallow that
    case here so declaring signatures never changes whether the underlying call
    happens -- it only makes the real Win32 call well-defined.
    """
    try:
        func.argtypes = argtypes
        func.restype = restype
    except (AttributeError, TypeError):
        pass


def _strip_cs_dropshadow(widget: QWidget) -> None:
    """Clear the native CS_DROPSHADOW window-class style.

    DWM paints CS_DROPSHADOW as a shadow decoration outside our window's own
    pixel buffer, so neither our QRegion mask nor NoDropShadowWindowHint can
    clip it away -- Qt's hint does not reliably clear this bit for the popup
    container window classes QComboBox/QMenu create internally, which is what
    shows up as a hard-edged dark rectangle behind the rounded popup.
    """
    if sys.platform != "win32":
        return

    try:
        hwnd = ctypes.wintypes.HWND(int(widget.winId()))
        user32 = ctypes.windll.user32
        if hasattr(user32, "GetClassLongPtrW"):
            get_class_long = user32.GetClassLongPtrW
            set_class_long = user32.SetClassLongPtrW
            # GetClassLongPtrW/SetClassLongPtrW return/take a pointer-width ULONG_PTR.
            value_type = ctypes.c_size_t
        else:
            get_class_long = user32.GetClassLongW
            set_class_long = user32.SetClassLongW
            # The 32-bit fallback returns/takes a plain DWORD, not a pointer-width value.
            value_type = ctypes.wintypes.DWORD

        _declare_signature(get_class_long, [ctypes.wintypes.HWND, ctypes.c_int], value_type)
        _declare_signature(
            set_class_long, [ctypes.wintypes.HWND, ctypes.c_int, value_type], value_type
        )

        style = get_class_long(hwnd, ctypes.c_int(GCL_STYLE))
        if style & CS_DROPSHADOW:
            set_class_long(hwnd, ctypes.c_int(GCL_STYLE), value_type(style & ~CS_DROPSHADOW))
    except (OSError, AttributeError, ValueError) as exc:
        logger.debug("Skipping CS_DROPSHADOW override: %s", exc)


def _strip_qt_graphics_shadow(widget: QWidget) -> None:
    """Remove the QGraphicsDropShadowEffect Qt installs on popup containers.

    QComboBoxPrivateContainer attaches its own QGraphicsDropShadowEffect to
    render a soft offset shadow entirely within Qt's software paint pipeline,
    independent of DWM, window-class styles, or our own mask. That effect is
    what actually paints the dark offset square behind our rounded corners.
    """
    if widget.graphicsEffect() is not None:
        widget.setGraphicsEffect(None)


def _queue_mask_refresh(widget: QWidget, radius: int) -> None:
    """Re-apply popup shaping after Qt finishes its own popup geometry updates.

    The mask is geometry-dependent and must be recomputed on every Move/Resize.
    The DWM corner-preference and window-class style overrides are properties of
    the native window itself and don't reset on move/resize, so they only need
    to run once per widget (on its first Show, once a native HWND exists).
    """

    def _refresh() -> None:
        _apply_rounded_mask(widget, radius)
        if not getattr(widget, "_rounded_popup_native_configured", False):
            _disable_dwm_corner_rounding(widget)
            _strip_cs_dropshadow(widget)
            _strip_qt_graphics_shadow(widget)
            widget._rounded_popup_native_configured = True

    QTimer.singleShot(0, _refresh)


def _configure_popup_surface(
    popup: QWidget,
    *,
    radius: int = POPUP_SURFACE_RADIUS,
    object_name: str | None = None,
    transparent_stylesheet: str | None = None,
) -> None:
    """Apply host-window settings that let rounded popup bodies render cleanly."""
    if object_name is not None:
        popup.setObjectName(object_name)

    popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    popup.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
    popup.setWindowFlags(
        popup.windowFlags()
        | Qt.WindowType.NoDropShadowWindowHint
        | Qt.WindowType.FramelessWindowHint
    )

    if transparent_stylesheet is not None:
        popup.setStyleSheet(transparent_stylesheet)

    _install_surface_filter(popup, radius)


def configure_combo_popup_container(combo: QComboBox) -> None:
    """Configure a combo popup host so its real window matches the rounded view."""
    container = combo.view().window()
    _configure_popup_surface(
        container,
        object_name=COMBO_POPUP_CONTAINER_NAME,
        transparent_stylesheet=(
            f"QFrame#{COMBO_POPUP_CONTAINER_NAME} {{ background: transparent; border: none; }}"
        ),
    )


def configure_menu_popup_surface(menu: QMenu) -> None:
    """Configure a top-level menu surface so its real window has rounded corners."""
    _configure_popup_surface(menu)
