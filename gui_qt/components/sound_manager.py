"""Qt sound effects for lightweight GUI polish."""

from pathlib import Path
from typing import Dict, Set

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QPushButton, QWidget

from src.config_manager import ConfigManager
from src.logging_config import get_logger

logger = get_logger(__name__)


class GuiSoundManager(QObject):
    """Owns short GUI sound players and button hover event filtering."""

    LIVE_SOUND = Path("assets/live-notification-sound-effect-52434.mp3")
    HOVER_SOUND = Path("assets/minimalist-button-hover-sound-effect-399749.mp3")

    def __init__(self, config: ConfigManager, parent: QWidget):
        super().__init__(parent)
        self.config = config
        self._players: Dict[str, QMediaPlayer] = {}
        self._audio_outputs: Dict[str, QAudioOutput] = {}
        self._filtered_buttons: Set[int] = set()
        self._hover_timer = QElapsedTimer()
        self._hover_interval_ms = 120

        self._create_player("live", self.LIVE_SOUND, volume=0.55)
        self._create_player("hover", self.HOVER_SOUND, volume=0.22)

    def _create_player(self, name: str, relative_path: Path, volume: float) -> None:
        """Create a media player for a bundled sound if the asset exists."""
        asset_path = Path(__file__).resolve().parents[2] / relative_path
        if not asset_path.exists():
            logger.warning(f"Sound asset missing: {asset_path}")
            return

        audio_output = QAudioOutput(self)
        audio_output.setVolume(volume)

        player = QMediaPlayer(self)
        player.setAudioOutput(audio_output)
        player.setSource(QUrl.fromLocalFile(str(asset_path)))

        self._audio_outputs[name] = audio_output
        self._players[name] = player

    def install_button_hover_sounds(self, root_widget: QWidget) -> None:
        """Install hover sound handling on all current QPushButton children."""
        for button in root_widget.findChildren(QPushButton):
            marker = id(button)
            if marker in self._filtered_buttons:
                continue
            button.installEventFilter(self)
            self._filtered_buttons.add(marker)

    def play_live_notification(self) -> None:
        """Play the live notification sound if enabled."""
        if self.config.get("favorite_live_notification_sound_enabled", True):
            self._play("live")

    def play_button_hover(self) -> None:
        """Play the hover sound if enabled and not throttled."""
        if not self.config.get("button_hover_sound_enabled", True):
            return

        if self._hover_timer.isValid() and self._hover_timer.elapsed() < self._hover_interval_ms:
            return

        self._hover_timer.restart()
        self._play("hover")

    def _play(self, name: str) -> None:
        """Start a sound from the beginning."""
        player = self._players.get(name)
        if not player:
            return

        player.stop()
        player.setPosition(0)
        player.play()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Enter and isinstance(watched, QPushButton):
            if watched.isEnabled():
                self.play_button_hover()

        return super().eventFilter(watched, event)
