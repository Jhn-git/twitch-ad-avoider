"""JS-callable API surface for the pywebview-based Twitch viewer."""

from __future__ import annotations

import json
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.config_manager import ConfigManager
from src.constants import CLIPS_DIR, QUALITY_OPTIONS
from src.exceptions import ValidationError
from src.favorites_manager import FavoriteChannelInfo, FavoritesManager
from src.logging_config import get_logger, reconfigure_logging_from_config
from src.status_monitor import StatusMonitor
from src.stream_preview import StreamPreviewInfo, fetch_stream_preview_info
from src.validators import validate_channel_name
from src.web_stream_service import WebStreamService, open_path_in_explorer

logger = get_logger(__name__)


class TwitchViewerAPI:
    """Single Python bridge object exposed as ``window.pywebview.api``."""

    def __init__(
        self,
        config: ConfigManager,
        launch_channel: Optional[str] = None,
        launch_quality: str = "best",
    ):
        self._config = config
        self._window = None
        self._shutting_down = False
        self._favorites = FavoritesManager()
        self._status_monitor = StatusMonitor(
            check_timeout=self._int_setting("favorites_check_timeout", 5)
        )
        self._selected_channel = self._normalize_optional_channel(launch_channel)
        self._launch_quality = launch_quality if launch_quality in QUALITY_OPTIONS else "best"
        self._activity: list[dict[str, Any]] = []
        self._preview_cache: dict[str, dict[str, Any]] = {}
        self._stream_service = WebStreamService(
            config,
            push_event=self._on_stream_event,
            add_activity=self._add_activity,
        )
        threading.Thread(target=self._stream_service.purge_expired_recordings, daemon=True).start()

    # ------------------------------------------------------------------
    # Window and pushes
    # ------------------------------------------------------------------

    def set_window(self, window) -> None:
        self._window = window

    def toggle_fullscreen(self) -> dict:
        if not self._window:
            return {"ok": False, "error": "Window not ready"}
        self._window.toggle_fullscreen()
        return {"ok": True}

    def shutdown(self) -> None:
        # Runs synchronously on the UI thread via window.events.closing. Must be set
        # before stopping the stream service, since stop()/_add_activity() still push
        # JS events; evaluate_js() blocks on a continuation that can only be delivered
        # by this same (currently blocked) UI thread, deadlocking the close.
        self._shutting_down = True
        self._stream_service.shutdown()

    def _push(self, js_global: str, data: Any) -> None:
        if not self._window or self._shutting_down:
            return
        try:
            payload = json.dumps(data)
            self._window.evaluate_js(f"window.{js_global} && window.{js_global}({payload})")
        except Exception:
            logger.debug("JS push failed for %s", js_global, exc_info=True)

    def _on_stream_event(self, event: dict) -> None:
        self._push("__onStreamEvent", event)

    def _add_activity(self, level: str, message: str, category: Optional[str] = None) -> None:
        entry = {
            "id": f"a{int(time.time() * 1000)}-{len(self._activity)}",
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
            "category": category or "APP",
        }
        self._activity.append(entry)
        self._activity = self._activity[-500:]
        self._push("__onActivity", entry)

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def get_initial_state(self) -> dict:
        settings = self._config.get_all()
        if self._selected_channel is None:
            favorites = self._favorites.get_favorites_with_status()
            if favorites:
                self._selected_channel = favorites[0].channel_name
        preview = self._preview_payload(self._selected_channel) if self._selected_channel else None

        return {
            "settings": settings,
            "qualities": QUALITY_OPTIONS,
            "favorites": self._favorites_payload(),
            "selected_channel": self._selected_channel,
            "launch_quality": self._launch_quality,
            "preview": preview,
            "stream": self._stream_service.get_state(),
            "ui_state": self._ui_state_payload(settings),
            "activity": self._activity[-100:],
        }

    def _ui_state_payload(self, settings: dict) -> dict:
        return {
            "stream_manager_left_sidebar_open": settings.get(
                "stream_manager_left_sidebar_open", True
            ),
            "stream_manager_right_sidebar_open": settings.get(
                "stream_manager_right_sidebar_open", True
            ),
            "stream_manager_activity_drawer_open": settings.get(
                "stream_manager_activity_drawer_open", False
            ),
            "stream_manager_clip_duration_seconds": settings.get(
                "stream_manager_clip_duration_seconds", 30
            ),
        }

    # ------------------------------------------------------------------
    # Favorites and preview
    # ------------------------------------------------------------------

    def get_favorites(self) -> list[dict]:
        return self._favorites_payload()

    def add_favorite(self, channel: str) -> dict:
        try:
            normalized = validate_channel_name(channel)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        if not self._favorites.add_favorite(normalized):
            return {"ok": False, "error": "Favorite already exists"}
        self._add_activity("info", f"Added favorite: {normalized}", "FAVORITES")
        payload = self._favorites_payload()
        self._push("__onFavoritesUpdated", payload)
        return {"ok": True, "favorites": payload}

    def remove_favorite(self, channel: str) -> dict:
        if not self._favorites.remove_favorite(channel):
            return {"ok": False, "error": "Favorite not found"}
        if self._selected_channel == channel:
            self._selected_channel = None
        self._add_activity("info", f"Removed favorite: {channel}", "FAVORITES")
        payload = self._favorites_payload()
        self._push("__onFavoritesUpdated", payload)
        return {"ok": True, "favorites": payload, "selected_channel": self._selected_channel}

    def toggle_pin(self, channel: str) -> dict:
        new_state = self._favorites.toggle_pin(channel)
        payload = self._favorites_payload()
        self._push("__onFavoritesUpdated", payload)
        return {"ok": True, "is_pinned": new_state, "favorites": payload}

    def refresh_favorites(self) -> dict:
        favorites = self._favorites.get_favorites()
        if not favorites:
            return {"ok": True, "favorites": []}
        self._status_monitor.update_timeout(self._int_setting("favorites_check_timeout", 5))
        status_results = self._status_monitor.check_channels(favorites)
        if not status_results:
            return {"ok": False, "error": "Status check failed, showing last known status"}
        newly_live: list[str] = []
        for channel, is_live in status_results.items():
            previous = self._favorites.get_channel_info(channel)
            if is_live and previous and not previous.is_live:
                newly_live.append(channel)
        self._favorites.update_channel_statuses(status_results)
        payload = self._favorites_payload()
        self._push("__onFavoritesUpdated", payload)
        live_count = sum(1 for is_live in status_results.values() if is_live)
        self._add_activity(
            "info",
            f"Refresh complete: {live_count}/{len(status_results)} live",
            "FAVORITES",
        )
        if newly_live and self._config.get("favorite_live_notifications_enabled", True):
            self._push("__onToast", {"kind": "success", "message": ", ".join(newly_live) + " live"})
        if newly_live and self._config.get("favorite_live_notification_sound_enabled", True):
            self._push("__onFavoriteLiveSound", {"channels": newly_live})
        return {"ok": True, "favorites": payload}

    def select_channel(self, channel: str) -> dict:
        try:
            normalized = validate_channel_name(channel)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        self._selected_channel = normalized
        preview = self._cached_preview_payload(normalized)
        return {"ok": True, "selected_channel": normalized, "preview": preview}

    def get_preview(self, channel: str) -> dict:
        try:
            normalized = validate_channel_name(channel)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "preview": self._preview_payload(normalized)}

    def _favorites_payload(self) -> list[dict]:
        return [
            self._favorite_payload(info) for info in self._favorites.get_favorites_with_status()
        ]

    def _favorite_payload(self, info: FavoriteChannelInfo) -> dict:
        return {
            "channel_name": info.channel_name,
            "is_live": info.is_live,
            "is_pinned": info.is_pinned,
            "profile_image_url": self._profile_image_for_channel(info.channel_name),
            "last_checked": self._datetime_payload(info.last_checked),
            "last_seen_live": self._datetime_payload(info.last_seen_live),
        }

    def _preview_payload(self, channel: Optional[str]) -> Optional[dict]:
        if not channel:
            return None
        info = fetch_stream_preview_info(
            channel,
            timeout=self._int_setting("network_timeout", 30),
        )
        payload = self._stream_preview_payload(info)
        self._preview_cache[payload["channel"]] = payload
        return payload

    def _cached_preview_payload(self, channel: str) -> dict:
        return self._preview_cache.get(
            channel,
            {
                "channel": channel,
                "is_live": False,
                "title": None,
                "preview_image_url": None,
                "profile_image_url": None,
            },
        )

    def _stream_preview_payload(self, info: StreamPreviewInfo) -> dict:
        return {
            "channel": info.channel,
            "is_live": info.is_live,
            "title": info.title,
            "preview_image_url": info.preview_image_url,
            "profile_image_url": info.profile_image_url,
        }

    def _profile_image_for_channel(self, channel: str) -> Optional[str]:
        cached = self._preview_cache.get(channel)
        if not cached:
            return None
        value = cached.get("profile_image_url")
        return value if isinstance(value, str) and value else None

    # ------------------------------------------------------------------
    # Stream and clip actions
    # ------------------------------------------------------------------

    def start_stream(self, channel: Optional[str] = None, quality: Optional[str] = None) -> dict:
        target_channel = channel or self._selected_channel
        if not target_channel:
            return {"ok": False, "error": "No channel selected"}
        target_quality = quality or self._config.get("preferred_quality", "best")
        try:
            state = self._stream_service.start(target_channel, target_quality)
            self._selected_channel = state.get("channel") or target_channel
            return {"ok": True, "stream": state}
        except Exception as exc:
            logger.error("Failed to start stream", exc_info=True)
            self._add_activity("error", f"Stream error: {exc}", "STREAM")
            return {"ok": False, "error": str(exc), "stream": self._stream_service.get_state()}

    def stop_stream(self) -> dict:
        return {"ok": True, "stream": self._stream_service.stop()}

    def get_stream_state(self) -> dict:
        return self._stream_service.get_state()

    def get_recording_segments(self, channel: Optional[str] = None) -> dict:
        target_channel = channel or self._selected_channel
        if not target_channel:
            return {"ok": False, "error": "No channel selected"}
        try:
            segments = self._stream_service.get_recording_segments(target_channel)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "segments": segments}

    def create_clip(
        self, duration_seconds: Optional[int] = None, behind_live_seconds: float = 0.0
    ) -> dict:
        seconds = duration_seconds or self._int_setting("stream_manager_clip_duration_seconds", 30)
        if not self._config.set("stream_manager_clip_duration_seconds", seconds):
            return {"ok": False, "error": "Invalid clip duration"}
        result = self._stream_service.create_clip(seconds, behind_live_seconds)
        if not result.get("ok"):
            self._add_activity("error", result.get("error", "Clip failed"), "CLIP")
        return result

    def open_channel(self, channel: Optional[str] = None) -> dict:
        target = channel or self._selected_channel
        if not target:
            return {"ok": False, "error": "No channel selected"}
        webbrowser.open(f"https://www.twitch.tv/{target}")
        return {"ok": True}

    def open_chat(self, channel: Optional[str] = None) -> dict:
        target = channel or self._selected_channel
        if not target:
            return {"ok": False, "error": "No channel selected"}
        webbrowser.open(f"https://www.twitch.tv/popout/{target}/chat?popout=")
        return {"ok": True}

    def open_clips_folder(self) -> dict:
        open_path_in_explorer(Path(self._config.get("clip_directory", str(CLIPS_DIR))))
        return {"ok": True}

    # ------------------------------------------------------------------
    # Settings and UI state
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        return self._config.get_all()

    def validate_setting(self, key: str, value: Any) -> dict:
        failed_keys = self._config.validate_update({key: value})
        return {"ok": key not in failed_keys}

    def save_settings(self, patch: dict) -> dict:
        if not self._config.update(patch):
            failed_keys = self._config.validate_update(patch)
            return {"ok": False, "error": f"Invalid values for: {', '.join(failed_keys)}"}
        if not self._config.save_settings():
            return {"ok": False, "error": "Failed to write settings file"}
        reconfigure_logging_from_config(self._config)
        self._push("__onSettingsUpdated", self._config.get_all())
        return {"ok": True, "settings": self._config.get_all()}

    def reset_settings_to_defaults(self) -> dict:
        self._config.reset_to_defaults()
        self._config.save_settings()
        reconfigure_logging_from_config(self._config)
        self._push("__onSettingsUpdated", self._config.get_all())
        return {"ok": True, "settings": self._config.get_all()}

    def set_ui_state(self, key: str, value: Any) -> dict:
        if not self._config.set(key, value):
            return {"ok": False}
        self._config.save_settings()
        return {"ok": True}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _int_setting(self, key: str, default: int) -> int:
        value = self._config.get(key, default)
        return value if isinstance(value, int) else default

    def _normalize_optional_channel(self, channel: Optional[str]) -> Optional[str]:
        if not channel:
            return None
        try:
            return validate_channel_name(channel)
        except ValidationError:
            logger.warning("Ignoring invalid launch channel: %s", channel)
            return None

    def _datetime_payload(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
