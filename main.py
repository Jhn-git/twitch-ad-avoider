#!/usr/bin/env python3
"""TwitchAdAvoider desktop entry point."""

import sys
import argparse
from pathlib import Path

from src.logging_config import (
    setup_logging,
    get_logger,
    configure_logging_from_config,
)
from src.config_manager import ConfigManager  # noqa: E402


def get_resource_path(relative_path: str) -> Path:
    """Return a bundled or source-tree resource path."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path


def main():
    """Launch the pywebview Stream Manager."""
    parser = argparse.ArgumentParser(
        description="TwitchAdAvoider - Watch Twitch streams while avoiding ads"
    )
    parser.add_argument("--channel", "-c", help="Preselect a channel in the Stream Manager")
    parser.add_argument("--quality", "-q", default="best", help="Stream quality (default: best)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    try:
        import webview

        from runtime_check import verify_compatible
        from webapi import TwitchViewerAPI

        config = ConfigManager()

        if args.debug:
            config.set("debug", True)
            log_level = "DEBUG"
        else:
            log_level = config.get("log_level", "INFO")

        # Configure logging
        if config.get("log_to_file"):
            configure_logging_from_config(config)
        else:
            setup_logging(level=log_level)

        logger = get_logger(__name__)
        logger.info("TwitchAdAvoider application starting")

        verify_compatible()
        logger.info("Starting TwitchAdAvoider web GUI")

        api = TwitchViewerAPI(
            config,
            launch_channel=args.channel,
            launch_quality=args.quality,
        )
        gui_path = get_resource_path("gui_web/index.html")
        window = webview.create_window(
            title="TwitchAdAvoider - Stream Manager",
            url=str(gui_path),
            js_api=api,
            width=int(config.get("window_width", 1440)),
            height=int(config.get("window_height", 850)),
            min_size=(1000, 650),
            text_select=False,
        )
        api.set_window(window)
        try:
            window.events.closing += api.shutdown
        except Exception:
            logger.debug("pywebview closing hook not available", exc_info=True)

        logger.info("Application ready - entering event loop")
        webview.start(debug=args.debug)
        return 0

    except ImportError as e:
        print(f"Import Error: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install -e .")
        return 1
    except KeyboardInterrupt:
        print("\nApplication closed by user")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
