"""Tests for popup host shaping helpers.

Deliberate exception to AGENTS.md's "skip GUI tests" guidance: this covers
non-trivial Win32/DWM ctypes logic (corner rounding, CS_DROPSHADOW stripping)
with no other regression coverage.
"""

from PySide6.QtWidgets import QApplication, QComboBox

from gui_qt import popup_utils
from gui_qt.popup_utils import configure_combo_popup_container


def test_disable_dwm_corner_rounding_calls_dwmapi_with_donotround(monkeypatch):
    """Popup hosts ask DWM to skip its own corner rounding on Windows."""
    app = QApplication.instance() or QApplication([])
    calls = []

    class _FakeDwmApi:
        def DwmSetWindowAttribute(self, hwnd, attribute, value_ptr, size):
            calls.append((hwnd, attribute))
            return 0

    monkeypatch.setattr(popup_utils.sys, "platform", "win32")
    monkeypatch.setattr(
        popup_utils.ctypes, "windll", type("W", (), {"dwmapi": _FakeDwmApi()})()
    )

    combo = QComboBox()
    combo.addItems(["a", "b"])
    configure_combo_popup_container(combo)
    combo.showPopup()
    app.processEvents()

    assert calls
    assert calls[0][1].value == popup_utils.DWMWA_WINDOW_CORNER_PREFERENCE

    combo.hidePopup()
    combo.deleteLater()


def test_disable_dwm_corner_rounding_swallows_errors(monkeypatch):
    """A missing/broken dwmapi never raises out of the popup shaping path."""
    monkeypatch.setattr(popup_utils.sys, "platform", "win32")

    class _BrokenDwmApi:
        def DwmSetWindowAttribute(self, *args, **kwargs):
            raise OSError("no dwmapi")

    monkeypatch.setattr(
        popup_utils.ctypes, "windll", type("W", (), {"dwmapi": _BrokenDwmApi()})()
    )

    app = QApplication.instance() or QApplication([])
    widget = QComboBox()
    widget.addItems(["a"])
    configure_combo_popup_container(widget)
    widget.showPopup()  # must not raise
    app.processEvents()
    widget.hidePopup()
    widget.deleteLater()


def test_disable_dwm_corner_rounding_noop_off_windows(monkeypatch):
    """Non-Windows platforms never touch ctypes.windll at all."""
    monkeypatch.setattr(popup_utils.sys, "platform", "linux")
    # Deliberately do NOT stub ctypes.windll -- if the guard is missing this
    # would raise AttributeError on non-Windows interpreters, failing the test.
    QApplication.instance() or QApplication([])
    widget = QComboBox()
    widget.addItems(["a"])
    configure_combo_popup_container(widget)
    widget.deleteLater()


def test_strip_cs_dropshadow_clears_style_bit(monkeypatch):
    """Popup hosts ask Win32 to drop the CS_DROPSHADOW window-class style."""
    app = QApplication.instance() or QApplication([])

    class _FakeUser32:
        def __init__(self) -> None:
            self.style = 0x00020003  # CS_HREDRAW | CS_VREDRAW | CS_DROPSHADOW
            self.set_calls = []

        def GetClassLongPtrW(self, hwnd, index):
            return self.style

        def SetClassLongPtrW(self, hwnd, index, value):
            self.set_calls.append((hwnd, index, value))
            self.style = value.value if hasattr(value, "value") else value
            return 0

    fake_user32 = _FakeUser32()
    monkeypatch.setattr(popup_utils.sys, "platform", "win32")
    monkeypatch.setattr(
        popup_utils.ctypes,
        "windll",
        type("W", (), {"dwmapi": type("D", (), {"DwmSetWindowAttribute": lambda *a: 0})(), "user32": fake_user32})(),
    )

    combo = QComboBox()
    combo.addItems(["a", "b"])
    configure_combo_popup_container(combo)
    combo.showPopup()
    app.processEvents()

    assert fake_user32.set_calls
    new_style = fake_user32.set_calls[0][2].value
    assert not new_style & popup_utils.CS_DROPSHADOW

    combo.hidePopup()
    combo.deleteLater()


def test_strip_cs_dropshadow_swallows_errors(monkeypatch):
    """A missing/broken user32 lookup never raises out of the popup shaping path."""
    monkeypatch.setattr(popup_utils.sys, "platform", "win32")

    class _BrokenUser32:
        def GetClassLongPtrW(self, *args, **kwargs):
            raise OSError("no user32")

    monkeypatch.setattr(
        popup_utils.ctypes,
        "windll",
        type("W", (), {"dwmapi": type("D", (), {"DwmSetWindowAttribute": lambda *a: 0})(), "user32": _BrokenUser32()})(),
    )

    app = QApplication.instance() or QApplication([])
    widget = QComboBox()
    widget.addItems(["a"])
    configure_combo_popup_container(widget)
    widget.showPopup()  # must not raise
    app.processEvents()
    widget.hidePopup()
    widget.deleteLater()
