"""Subtle ad-blocked indicator dot for the TwitchAdAvoider Qt GUI."""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class AdBlockIndicator(QWidget):
    """A small dot that blinks red while an ad is being filtered, dim/gray otherwise."""

    _ACTIVE_COLOR = QColor("#E74C3C")
    _IDLE_COLOR = QColor("#6B6B6B")
    _DIAMETER = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._DIAMETER, self._DIAMETER)
        self.setToolTip("No ad currently detected")
        self._active = False

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        # A slow, subtle breathing pulse rather than a hard on/off blink.
        self._blink_animation = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._blink_animation.setDuration(2000)
        self._blink_animation.setKeyValueAt(0.0, 1.0)
        self._blink_animation.setKeyValueAt(0.5, 0.35)
        self._blink_animation.setKeyValueAt(1.0, 1.0)
        self._blink_animation.setEasingCurve(QEasingCurve.InOutSine)
        self._blink_animation.setLoopCount(-1)

    def set_active(self, active: bool) -> None:
        """Update whether an ad is currently being filtered."""
        if active == self._active:
            return
        self._active = active
        if active:
            self.setToolTip("Ad currently being blocked")
            self._blink_animation.start()
        else:
            self.setToolTip("No ad currently detected")
            self._blink_animation.stop()
            self._opacity_effect.setOpacity(1.0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self._ACTIVE_COLOR if self._active else self._IDLE_COLOR
        painter.setBrush(color)
        painter.setPen(color.darker(130))
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        painter.end()
