"""
TwitchAdAvoider - Main Application Entry Point
A Python implementation for watching Twitch streams while avoiding ads.
"""
import sys
import os
import argparse
from pathlib import Path

# Add src directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def setup_application():
    """Setup logging and configuration for the application."""
    from src.logging_config import setup_logging
    from src.config_manager import ConfigManager
    
    # Load configuration
    config = ConfigManager()
    
    # Setup logging with debug information
    debug_enabled = config.get('debug', False)
    log_level = config.get('log_level', 'INFO')
    log_to_file = config.get('log_to_file', False)
    
    logger = setup_logging(
        level=log_level,
        log_to_file=log_to_file,
        enable_debug=debug_enabled
    )
    
    logger.info("TwitchAdAvoider application starting")
    if debug_enabled:
        logger.debug(f"Debug mode enabled via config (debug={debug_enabled})")
        logger.debug(f"Configuration: log_level={log_level}, log_to_file={log_to_file}")
    
    return config, logger

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
        # Setup application
        config, logger = setup_application()
        
        # Override config with command line arguments
        if args.debug:
            config.set('debug', True)
        
        # If channel provided, start stream directly
        if args.channel:
            from src.twitch_viewer import TwitchViewer
            viewer = TwitchViewer(config)
            config.set('preferred_quality', args.quality)
            viewer.watch_stream(args.channel)
            return 0
        
        # Otherwise launch GUI
        from gui.stream_gui import main as gui_main
        logger.info("Starting TwitchAdAvoider GUI")
        gui_main(config)
        return 0
        
    except ImportError as e:
        print(f"Import Error: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        return 1
    except KeyboardInterrupt:
        print("\nApplication closed by user")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())