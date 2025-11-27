#!/usr/bin/env python3
"""
TwitchAdAvoider - Main Application Entry Point
A Python implementation for watching Twitch streams while avoiding ads.
"""
import sys
import argparse
from pathlib import Path

# Add src directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from src.logging_config import setup_logging, get_logger, configure_logging_from_config
from src.config_manager import ConfigManager

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description='TwitchAdAvoider - Watch Twitch streams while avoiding ads'
    )
    parser.add_argument(
        '--channel', '-c',
        help='Channel to watch (launches directly to stream)'
    )
    parser.add_argument(
        '--quality', '-q',
        default='best',
        help='Stream quality (default: best)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = ConfigManager()

        # Setup logging
        if args.debug:
            config.set('debug', True)
            log_level = "DEBUG"
        else:
            log_level = config.get('log_level', 'INFO')

        # Configure logging
        if config.get('log_to_file'):
            configure_logging_from_config(config)
        else:
            setup_logging(level=log_level)

        logger = get_logger(__name__)
        logger.info("TwitchAdAvoider application starting")

        # If channel provided, start stream directly (CLI mode)
        if args.channel:
            from src.twitch_viewer import TwitchViewer
            viewer = TwitchViewer(config)
            config.set('preferred_quality', args.quality)
            viewer.watch_stream(args.channel)
            return 0

        # Otherwise launch Qt GUI
        from PySide6.QtWidgets import QApplication
        from gui_qt.stream_gui import StreamGUI

        logger.info("Starting TwitchAdAvoider Qt GUI")

        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("TwitchAdAvoider")
        app.setOrganizationName("TwitchAdAvoider")
        app.setApplicationDisplayName("TwitchAdAvoider - Stream Manager")

        # Use Fusion style for consistent cross-platform appearance
        app.setStyle("Fusion")

        # Create and show GUI
        gui = StreamGUI(config)
        gui.show()

        logger.info("Application ready - entering event loop")

        # Run application
        return app.exec()

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