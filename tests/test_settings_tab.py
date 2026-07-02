"""Tests for settings tab validation behavior."""

from PySide6.QtWidgets import QApplication

from gui_qt.components import settings_tab as settings_tab_module
from gui_qt.components.settings_tab import SettingsTab
from gui_qt.popup_utils import COMBO_POPUP_CONTAINER_NAME
from src.config_manager import ConfigManager
from conftest import assert_popup_surface


def test_apply_settings_rejects_invalid_batch_without_save(monkeypatch, tmp_path):
    """Invalid settings are reported before config mutation or file save."""
    app = QApplication.instance() or QApplication([])
    mock_config_manager = ConfigManager(tmp_path / "test_settings.json")
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

    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_settings_combos_use_shaped_popup_hosts(tmp_path):
    """Settings combo popups get shaped top-level surfaces once shown."""
    app = QApplication.instance() or QApplication([])
    mock_config_manager = ConfigManager(tmp_path / "test_settings.json")
    widget = SettingsTab(mock_config_manager)
    widget.show()
    app.processEvents()

    for combo in (widget.player_combo, widget.quality_combo, widget.log_level_combo):
        combo.showPopup()
        app.processEvents()
        popup_container = combo.view().window()
        assert popup_container.objectName() == COMBO_POPUP_CONTAINER_NAME
        assert_popup_surface(popup_container)
        combo.hidePopup()
        app.processEvents()

    widget.close()
    widget.deleteLater()
    app.processEvents()
