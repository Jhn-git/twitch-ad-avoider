"""
Simple GUI for TwitchAdAvoider Stream Manager
Uses tkinter for a lightweight interface
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import subprocess
import sys
import os
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.twitch_viewer import TwitchViewer
from src.exceptions import TwitchStreamError, ValidationError
from src.config_manager import ConfigManager
from src.validators import validate_channel_name
from src.logging_config import get_logger, reconfigure_logging
from src.streamlink_status import StreamlinkStatusChecker
from src.status_monitor import StatusMonitor
from src.constants import GUI_GEOMETRY, GUI_MIN_SIZE
from gui.favorites_manager import FavoritesManager, FavoriteChannelInfo

logger = get_logger(__name__)

class StreamGUI:
    """
    Main GUI class for TwitchAdAvoider Stream Manager.
    
    Provides a user-friendly interface for watching Twitch streams with features including:
    - Real-time channel name validation
    - Favorites management
    - Quality selection
    - Status monitoring
    - Player configuration
    """
    
    def __init__(self, root: tk.Tk, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the Stream GUI.
        
        Args:
            root: The main tkinter window
            config_manager: Configuration manager instance
        """
        self.root = root
        self.root.title("TwitchAdAvoider - Stream Manager")
        self.root.geometry(GUI_GEOMETRY)
        self.root.resizable(True, True)
        self.root.minsize(*GUI_MIN_SIZE)
        self.root.maxsize(1200, 900)  # Set reasonable maximum size
        
        # Initialize managers
        self.config = config_manager or ConfigManager()
        self.viewer = TwitchViewer(self.config)
        self.favorites_manager = FavoritesManager()
        
        # Initialize status checker and monitor
        self.status_checker = StreamlinkStatusChecker()
        self.status_monitor = StatusMonitor(
            status_checker=self.status_checker,
            favorites_manager=self.favorites_manager,
            config_manager=self.config,
            status_callback=self._on_status_updated
        )
        
        # Current stream process and thread
        self.current_stream_thread = None
        self.current_stream_process = None
        
        # Create GUI components
        self.setup_gui()
        self.refresh_favorites_list()
        
        # Check streamlink availability and warn user if not available
        self._check_streamlink_dependency()
        
        # Start status monitoring if streamlink is available
        if self.status_checker.is_available():
            self.status_monitor.start_monitoring()
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_gui(self) -> None:
        """
        Setup the GUI layout and components.
        
        Creates the main interface including:
        - Stream input section with validation
        - Quality selection dropdown
        - Favorites management section
        - Status display
        - Player configuration
        """
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Stream input section
        input_frame = ttk.LabelFrame(main_frame, text="Watch Stream", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Channel input
        ttk.Label(input_frame, text="Channel:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.channel_var = tk.StringVar()
        self.channel_entry = ttk.Entry(input_frame, textvariable=self.channel_var, width=25)
        self.channel_entry.grid(row=0, column=1, padx=(10, 0), pady=(0, 5), sticky=(tk.W, tk.E))
        self.channel_entry.bind('<Return>', lambda e: self.watch_stream())
        
        # Add real-time validation for channel input
        self.channel_var.trace_add('write', self._validate_channel_input)
        
        # Validation feedback label
        self.validation_label = ttk.Label(input_frame, text="", foreground="red", font=("Arial", 8))
        self.validation_label.grid(row=0, column=2, padx=(5, 0), pady=(0, 5), sticky=tk.W)
        
        # Quality selection
        ttk.Label(input_frame, text="Quality:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(input_frame, textvariable=self.quality_var, width=22)
        quality_combo['values'] = ('best', 'worst', '720p', '480p', '360p')
        quality_combo.grid(row=1, column=1, padx=(10, 0), pady=(0, 5), sticky=(tk.W, tk.E))
        quality_combo.state(['readonly'])
        
        # Watch button
        self.watch_btn = ttk.Button(input_frame, text="Watch Stream", command=self.watch_stream)
        self.watch_btn.grid(row=2, column=0, columnspan=2, pady=(15, 5))
        
        # Favorites section
        fav_frame = ttk.LabelFrame(main_frame, text="Favorites", padding="10")
        fav_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Favorites listbox with scrollbar
        list_frame = ttk.Frame(fav_frame)
        list_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.favorites_listbox = tk.Listbox(list_frame, height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.favorites_listbox.yview)
        self.favorites_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.favorites_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Bind double-click to watch
        self.favorites_listbox.bind('<Double-1>', lambda e: self.watch_favorite())
        
        # Favorites buttons
        fav_btn_frame = ttk.Frame(fav_frame)
        fav_btn_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0))
        
        ttk.Button(fav_btn_frame, text="Add Current", command=self.add_favorite).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fav_btn_frame, text="Add New", command=self.add_new_favorite).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fav_btn_frame, text="Remove", command=self.remove_favorite).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fav_btn_frame, text="🔄 Refresh", command=self.refresh_status).pack(side=tk.LEFT)
        
        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Player selection
        ttk.Label(settings_frame, text="Player:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.player_var = tk.StringVar(value=self.config.get('player', 'vlc'))
        player_combo = ttk.Combobox(settings_frame, textvariable=self.player_var, width=12)
        player_combo['values'] = ('vlc', 'mpv', 'mpc-hc', 'auto')
        player_combo.grid(row=0, column=1, padx=(10, 20), pady=5, sticky=tk.W)
        player_combo.state(['readonly'])
        
        # Debug mode
        self.debug_var = tk.BooleanVar(value=self.config.get('debug', False))
        debug_check = ttk.Checkbutton(settings_frame, text="Debug Mode", 
                                    variable=self.debug_var, 
                                    command=self._on_debug_toggle)
        debug_check.grid(row=0, column=2, pady=5, sticky=tk.W)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Configure grid weights for responsive layout
        # Root window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Main frame
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=0)  # Input section - fixed size
        main_frame.rowconfigure(1, weight=1)  # Favorites section - expandable
        main_frame.rowconfigure(2, weight=0)  # Settings section - fixed size
        main_frame.rowconfigure(3, weight=0)  # Status bar - fixed size
        
        # Input frame
        input_frame.columnconfigure(1, weight=1)
        
        # Favorites frame
        fav_frame.columnconfigure(0, weight=1)
        fav_frame.rowconfigure(0, weight=1)  # List area expandable
        fav_frame.rowconfigure(1, weight=0)  # Button area fixed
        
        # List frame
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Settings frame
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(2, weight=1)
    
    def _check_streamlink_dependency(self) -> None:
        """
        Check if streamlink is available and warn user if not.
        
        Displays an error dialog and disables functionality if streamlink is not available.
        """
        if not self.viewer.is_streamlink_available():
            error_msg = (
                "Streamlink is not available or not working properly.\n\n"
                "Please ensure streamlink is installed:\n"
                "pip install streamlink\n\n"
                "The application may not function correctly without streamlink."
            )
            messagebox.showerror("Streamlink Not Available", error_msg)
            self.status_var.set("ERROR: Streamlink not available - install with 'pip install streamlink'")
            # Disable watch functionality
            self.watch_btn.config(state='disabled', text="Streamlink Required")
    
    def _disable_watch_buttons(self) -> None:
        """
        Disable watch button during stream.
        
        Prevents multiple concurrent streams from being started.
        """
        self.watch_btn.config(state='disabled')
    
    def _enable_watch_buttons(self) -> None:
        """
        Re-enable watch button after stream ends.
        
        Restores watch functionality after a stream process completes.
        """
        self.watch_btn.config(state='normal', text="Watch Stream")
    
    def refresh_favorites_list(self) -> None:
        """
        Refresh the favorites listbox with status information.
        
        Updates the display to show current live status for each favorite channel.
        Uses status icons: 🔴 for live channels, ⚫ for offline channels.
        """
        self.favorites_listbox.delete(0, tk.END)
        
        # Get favorites with status info
        favorites = self.favorites_manager.get_favorites_with_status()
        
        for fav in favorites:
            # Create simple display text with status indicator
            status_icon = "🔴" if fav.is_live else "⚫"
            display_text = f"{status_icon} {fav.channel_name}"
            self.favorites_listbox.insert(tk.END, display_text)
    
    def _validate_channel_input(self, *args) -> None:
        """
        Real-time validation for channel input with visual feedback.
        
        Args:
            *args: Tkinter trace callback arguments (unused)
            
        Provides immediate visual feedback on channel name validity:
        - Green checkmark for valid names
        - Red X with error message for invalid names
        - Enables/disables watch button based on validity
        """
        channel = self.channel_var.get().strip()
        
        if not channel:
            self.validation_label.config(text="", foreground="gray")
            self.watch_btn.config(state="disabled")
            return
        
        try:
            validate_channel_name(channel)
            self.validation_label.config(text="✓ Valid", foreground="green")
            self.watch_btn.config(state="normal")
        except ValidationError as e:
            self.validation_label.config(text=f"✗ {str(e)}", foreground="red")
            self.watch_btn.config(state="disabled")
        except Exception:
            self.validation_label.config(text="✗ Invalid format", foreground="red")
            self.watch_btn.config(state="disabled")

    def watch_stream(self) -> None:
        """
        Start watching a stream.
        
        Validates the channel name, updates configuration from GUI settings,
        and starts the stream in a separate thread to prevent GUI blocking.
        
        Handles:
        - Channel name validation
        - Concurrent stream prevention
        - Configuration updates
        - Debug mode changes
        - Thread management
        """
        channel = self.channel_var.get().strip()
        if not channel:
            messagebox.showerror("Error", "Please enter a channel name")
            return
        
        # Validate channel before proceeding
        try:
            validate_channel_name(channel)
        except ValidationError as e:
            messagebox.showerror("Validation Error", str(e))
            return
        
        # Prevent concurrent streams
        if self.current_stream_process and self.current_stream_process.poll() is None:
            messagebox.showwarning("Warning", "A stream is already running. Please close it first.")
            return
        
        # Update configuration
        self.config.set('player', self.player_var.get())
        self.config.set('preferred_quality', self.quality_var.get())
        
        # Set player choice in TwitchViewer (prioritizes GUI selection)
        self.viewer.set_player_choice(self.player_var.get())
        
        # Handle debug mode changes with logging reconfiguration
        old_debug = self.config.get('debug', False)
        new_debug = self.debug_var.get()
        self.config.set('debug', new_debug)
        
        if old_debug != new_debug:
            self._reconfigure_logging()
        
        # Start stream in separate thread - disable all watch buttons
        self._disable_watch_buttons()
        self.watch_btn.config(text="Starting...")
        self.status_var.set(f"Starting stream for {channel}...")
        
        def stream_worker():
            try:
                # Store the process object
                self.current_stream_process = self.viewer.watch_stream(channel)
                
                # Now, wait for the process to complete
                return_code = self.current_stream_process.wait()
                
                # After it's done, clean up
                self.current_stream_process = None
                
                if return_code == 0:
                    self.root.after(0, lambda: self.stream_finished(f"Stream for {channel} ended"))
                else:
                    self.root.after(0, lambda: self.stream_error(f"Streamlink exited with code {return_code}"))
                    
            except Exception as e:
                # Clean up process reference on error
                self.current_stream_process = None
                self.root.after(0, lambda: self.stream_error(f"Error: {str(e)}"))
        
        self.current_stream_thread = threading.Thread(target=stream_worker, daemon=True)
        self.current_stream_thread.start()
    
    def watch_favorite(self):
        """Watch selected favorite channel"""
        selection = self.favorites_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a favorite channel")
            return
        
        # Extract channel name from formatted display text
        display_text = self.favorites_listbox.get(selection[0])
        channel = self._extract_channel_name(display_text)
        self.channel_var.set(channel)
        self.watch_stream()
    
    def _extract_channel_name(self, display_text: str) -> str:
        """Extract channel name from formatted display text"""
        # Format is: "🔴 channel_name" or "⚫ channel_name"
        # Remove status icon and extract channel name
        parts = display_text.split(' ', 1)
        if len(parts) > 1:
            return parts[1].strip()
        return display_text
    
    def _add_channel_to_favorites(self, channel_name: str) -> None:
        """
        Helper method to add a channel to favorites with common validation and UI updates.
        
        Args:
            channel_name: Name of the channel to add to favorites
        """
        channel_name = channel_name.strip()
        if not channel_name:
            messagebox.showerror("Error", "Please enter a channel name")
            return
        
        # Validate channel name
        try:
            validated_channel = validate_channel_name(channel_name)
        except ValidationError as e:
            messagebox.showerror("Validation Error", str(e))
            return
        
        channel_name = validated_channel
        
        if self.favorites_manager.add_favorite(channel_name):
            # Add to status monitoring
            self.status_monitor.add_channel_to_monitoring(channel_name)
            self.refresh_favorites_list()
            self.status_var.set(f"Added {channel_name} to favorites")
            messagebox.showinfo("Success", f"Added {channel_name} to favorites")
        else:
            messagebox.showwarning("Warning", f"{channel_name} is already in favorites")
    
    def add_favorite(self):
        """Add current channel to favorites"""
        channel = self.channel_var.get()
        self._add_channel_to_favorites(channel)
    
    def add_new_favorite(self):
        """Add a new favorite channel via dialog"""
        channel = simpledialog.askstring("Add Favorite", "Enter channel name:")
        if channel:
            self._add_channel_to_favorites(channel)
    
    def remove_favorite(self):
        """Remove selected favorite"""
        selection = self.favorites_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a favorite to remove")
            return
        
        # Extract channel name from formatted display text
        display_text = self.favorites_listbox.get(selection[0])
        channel = self._extract_channel_name(display_text)
        
        if messagebox.askyesno("Confirm", f"Remove {channel} from favorites?"):
            self.favorites_manager.remove_favorite(channel)
            # Remove from status monitoring
            self.status_monitor.remove_channel_from_monitoring(channel)
            self.refresh_favorites_list()
            self.status_var.set(f"Removed {channel} from favorites")
    
    def stream_finished(self, message):
        """Handle stream finishing"""
        self._enable_watch_buttons()
        self.status_var.set(message)
    
    def stream_error(self, message):
        """Handle stream error"""
        self._enable_watch_buttons()
        self.status_var.set(message)
        messagebox.showerror("Stream Error", message)
    
    def refresh_status(self):
        """Manually refresh stream status"""
        self.status_var.set("Refreshing stream status...")
        self.status_monitor.force_refresh()
    
    def _on_status_updated(self, updated_channels):
        """Callback for when stream status is updated"""
        # Schedule GUI update on main thread
        self.root.after(0, self.refresh_favorites_list)
        
        # Update status message
        if len(updated_channels) == 1:
            self.root.after(0, lambda: self.status_var.set(f"Status updated for {updated_channels[0]}"))
        else:
            self.root.after(0, lambda: self.status_var.set(f"Status updated for {len(updated_channels)} channels"))
    
    def _on_debug_toggle(self):
        """Handle debug mode checkbox toggle"""
        new_debug = self.debug_var.get()
        old_debug = self.config.get('debug', False)
        
        if old_debug != new_debug:
            self.config.set('debug', new_debug)
            self._reconfigure_logging()
            
            if new_debug:
                self.status_var.set("Debug mode enabled - verbose logging active")
                logger.debug("Debug mode enabled via GUI checkbox")
            else:
                self.status_var.set("Debug mode disabled")
                logger.info("Debug mode disabled via GUI checkbox")
    
    def _reconfigure_logging(self):
        """Reconfigure logging based on current settings"""
        try:
            debug_enabled = self.config.get('debug', False)
            log_level = self.config.get('log_level', 'INFO')  # Don't override here, let setup_logging handle it
            log_to_file = self.config.get('log_to_file', False)
            
            # Use same logic as main.py - enable_debug parameter will override level
            reconfigure_logging(
                level=log_level,
                log_to_file=log_to_file,
                enable_debug=debug_enabled
            )
            
            # Update global logger reference
            global logger
            logger = get_logger(__name__)
            
            if debug_enabled:
                logger.debug("Logging reconfigured via GUI - debug mode enabled")
                logger.debug(f"Configuration: log_level={log_level}, log_to_file={log_to_file}")
                logger.debug("Debug logs will be saved to logs/twitch_ad_avoider.log")
            else:
                logger.info("Logging reconfigured via GUI - debug mode disabled")
                
        except Exception as e:
            print(f"Error reconfiguring logging: {e}")
    
    def on_closing(self):
        """Handle window closing with robust process termination."""
        # Stop status monitoring first
        self.status_monitor.stop_monitoring()

        # Check if a stream process is running
        if self.current_stream_process and self.current_stream_process.poll() is None:
            print("Closing active stream...")
            
            # 1. Ask it to terminate gracefully
            self.current_stream_process.terminate()
            
            try:
                # 2. Wait for a short period (e.g., 3 seconds) for it to comply
                self.current_stream_process.wait(timeout=3)
                print("Stream process terminated gracefully.")
            except subprocess.TimeoutExpired:
                # 3. If it doesn't close in time, force-kill it
                print("Process did not terminate in time, forcing shutdown...")
                self.current_stream_process.kill()
                print("Stream process killed.")
                
        # Finally, destroy the window
        self.root.destroy()

def main(config_manager=None):
    """Main GUI entry point"""
    root = tk.Tk()
    app = StreamGUI(root, config_manager)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()