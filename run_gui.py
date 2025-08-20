"""
GUI Launcher for TwitchAdAvoider
Launches the tkinter-based stream manager GUI
"""
import sys
import os
from pathlib import Path

# Add src directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """Launch the GUI application"""
    try:
        # Check if we're in the right directory
        if not os.path.exists("src/twitch_viewer.py"):
            print("Error: Please run this script from the TwitchAdAvoider root directory")
            return 1
        
        # Import and run GUI
        from gui.stream_gui import main as gui_main
        print("Starting TwitchAdAvoider GUI...")
        gui_main()
        return 0
        
    except ImportError as e:
        print(f"Import Error: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        return 1
    except KeyboardInterrupt:
        print("\nGUI closed by user")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())