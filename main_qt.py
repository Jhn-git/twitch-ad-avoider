#!/usr/bin/env python3
"""
TwitchAdAvoider - Qt GUI Application Launcher

Modern PySide6-based interface for watching Twitch streams while avoiding ads.
This launcher initializes the Qt application with improved layout, spacing,
and visual polish.

Usage:
    python main_qt.py [--debug]

Options:
    --debug     Enable debug logging
"""

import sys
import argparse
from pathlib import Path

# Ensure src directory is in path
sys.path.insert(0, str(Path(__file__).parent))

from src.logging_config import setup_logging, get_logger
from src.config_manager import ConfigManager
from gui_qt.stream_gui import StreamGUI

from PySide6.QtWidgets import QApplication


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="TwitchAdAvoider - Watch Twitch streams while avoiding ads (Qt GUI)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    return parser.parse_args()


def main():
    """Main entry point for Qt application."""
    # Parse arguments
    args = parse_arguments()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)
    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("TwitchAdAvoider Qt GUI Starting")
    logger.info("=" * 60)

    try:
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("TwitchAdAvoider")
        app.setOrganizationName("TwitchAdAvoider")
        app.setApplicationDisplayName("TwitchAdAvoider - Stream Manager")

        # Set application style
        app.setStyle("Fusion")  # Use Fusion style for consistent cross-platform appearance

        # Load configuration
        logger.info("Loading configuration...")
        config = ConfigManager()

        # Create and show GUI
        logger.info("Initializing GUI...")
        gui = StreamGUI(config)
        gui.show()

        logger.info("Application ready - entering event loop")

        # Run application
        exit_code = app.exec()

        logger.info(f"Application exiting with code: {exit_code}")
        return exit_code

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0

    except Exception as e:
        logger.exception(f"Fatal error during application startup: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
