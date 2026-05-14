"""Tests for settings tab validation behavior."""

from PySide6.QtWidgets import QApplication

from gui_qt.components import settings_tab as settings_tab_module
from gui_qt.components.settings_tab import SettingsTab


def test_apply_settings_rejects_invalid_batch_without_save(monkeypatch, mock_config_manager):
    """Invalid settings are reported before config mutation or file save."""
    QApplication.instance() or QApplication([])
    widget = SettingsTab(mock_config_manager)
    warnings = []
    saved = {"called": False}
    emitted = []

    def fake_warning(*args):
        warnings.append(args)

    def fake_save_settings():
        saved["called"] = True
        return True

    monkeypatch.setattr(settings_tab_module.QMessageBox, "warning", fake_warning)
    monkeypatch.setattr(mock_config_manager, "save_settings", fake_save_settings)
    widget.settings_changed.connect(lambda: emitted.append(True))

    widget.player_args_edit.setText("--fullscreen && whoami")
    widget._on_apply_settings()

    assert warnings
    assert not saved["called"]
    assert emitted == []
    assert mock_config_manager.get("player_args") != "--fullscreen && whoami"

    widget.deleteLater()
