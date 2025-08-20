"""
Simple GUI for TwitchAdAvoider Stream Manager
Uses tkinter for a lightweight interface
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.twitch_viewer import TwitchViewer
from src.exceptions import TwitchStreamError, ValidationError
from src.config_manager import ConfigManager
from src.logging_config import get_logger, reconfigure_logging
from src.twitch_api import TwitchAPIClient
from src.status_monitor import StatusMonitor
from gui.favorites_manager import FavoritesManager, FavoriteChannelInfo

logger = get_logger(__name__)

class StreamGUI:
    def __init__(self, root, config_manager=None):
        self.root = root
        self.root.title("TwitchAdAvoider - Stream Manager")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        
        # Initialize managers
        self.config = config_manager or ConfigManager()
        self.viewer = TwitchViewer(self.config)
        self.favorites_manager = FavoritesManager()
        
        # Initialize API client and status monitor
        self.api_client = TwitchAPIClient(
            client_id=self.config.get('twitch_client_id'),
            client_secret=self.config.get('twitch_client_secret')
        )
        self.status_monitor = StatusMonitor(
            api_client=self.api_client,
            favorites_manager=self.favorites_manager,
            config_manager=self.config,
            status_callback=self._on_status_updated
        )
        
        # Current stream process
        self.current_stream_thread = None
        
        # Create GUI components
        self.setup_gui()
        self.refresh_favorites_list()
        
        # Start status monitoring if configured
        if self.api_client.is_configured():
            self.status_monitor.start_monitoring()
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_gui(self):
        """Setup the GUI layout"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Stream input section
        input_frame = ttk.LabelFrame(main_frame, text="Watch Stream", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Channel input
        ttk.Label(input_frame, text="Channel:").grid(row=0, column=0, sticky=tk.W)
        self.channel_var = tk.StringVar()
        self.channel_entry = ttk.Entry(input_frame, textvariable=self.channel_var, width=25)
        self.channel_entry.grid(row=0, column=1, padx=(5, 0))
        self.channel_entry.bind('<Return>', lambda e: self.watch_stream())
        
        # Quality selection
        ttk.Label(input_frame, text="Quality:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(input_frame, textvariable=self.quality_var, width=22)
        quality_combo['values'] = ('best', 'worst', '720p', '480p', '360p')
        quality_combo.grid(row=1, column=1, padx=(5, 0), pady=(5, 0))
        quality_combo.state(['readonly'])
        
        # Watch button
        self.watch_btn = ttk.Button(input_frame, text="Watch Stream", command=self.watch_stream)
        self.watch_btn.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
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
        ttk.Button(fav_btn_frame, text="🔄 Refresh", command=self.refresh_status).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fav_btn_frame, text="▶ Watch", command=self.watch_favorite).pack(side=tk.LEFT)
        
        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Player selection
        ttk.Label(settings_frame, text="Player:").grid(row=0, column=0, sticky=tk.W)
        self.player_var = tk.StringVar(value=self.config.get('player', 'vlc'))
        player_combo = ttk.Combobox(settings_frame, textvariable=self.player_var, width=10)
        player_combo['values'] = ('vlc', 'mpv', 'mpc-hc', 'auto')
        player_combo.grid(row=0, column=1, padx=(5, 0))
        player_combo.state(['readonly'])
        
        # Debug mode
        self.debug_var = tk.BooleanVar(value=self.config.get('debug', False))
        debug_check = ttk.Checkbutton(settings_frame, text="Debug Mode", 
                                    variable=self.debug_var, 
                                    command=self._on_debug_toggle)
        debug_check.grid(row=0, column=2, padx=(20, 0))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 0))
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        fav_frame.columnconfigure(0, weight=1)
        fav_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
    
    def refresh_favorites_list(self):
        """Refresh the favorites listbox with status information"""
        self.favorites_listbox.delete(0, tk.END)
        
        # Get favorites with status info
        favorites = self.favorites_manager.get_favorites_with_status()
        
        for fav in favorites:
            # Create display text with status indicator
            status_icon = "🔴" if fav.is_live else "⚫"
            display_text = f"{status_icon} {fav.channel_name}"
            
            # Add additional info if available and enabled
            if fav.is_live:
                info_parts = []
                
                if fav.viewer_count is not None and self.config.get('show_viewer_count', True):
                    viewer_text = self._format_viewer_count(fav.viewer_count)
                    info_parts.append(f"👥 {viewer_text}")
                
                if fav.game_name and self.config.get('show_game_name', True):
                    info_parts.append(f"🎮 {fav.game_name}")
                
                if info_parts:
                    display_text += f" ({', '.join(info_parts)})"
            
            self.favorites_listbox.insert(tk.END, display_text)
    
    def _format_viewer_count(self, count: int) -> str:
        """Format viewer count for display"""
        if count >= 1000000:
            return f"{count/1000000:.1f}M"
        elif count >= 1000:
            return f"{count/1000:.1f}k"
        else:
            return str(count)
    
    def watch_stream(self):
        """Start watching a stream"""
        channel = self.channel_var.get().strip()
        if not channel:
            messagebox.showerror("Error", "Please enter a channel name")
            return
        
        # Update configuration
        self.config.set('player', self.player_var.get())
        self.config.set('preferred_quality', self.quality_var.get())
        
        # Handle debug mode changes with logging reconfiguration
        old_debug = self.config.get('debug', False)
        new_debug = self.debug_var.get()
        self.config.set('debug', new_debug)
        
        if old_debug != new_debug:
            self._reconfigure_logging()
        
        # Start stream in separate thread
        self.watch_btn.config(state='disabled', text="Starting...")
        self.status_var.set(f"Starting stream for {channel}...")
        
        def stream_worker():
            try:
                self.viewer.watch_stream(channel)
                self.root.after(0, lambda: self.stream_finished(f"Stream for {channel} ended"))
            except Exception as e:
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
        # Format is: "🔴 channel_name (additional info)" or "⚫ channel_name"
        # Remove status icon and extract channel name
        parts = display_text.split(' ', 1)
        if len(parts) > 1:
            channel_part = parts[1]
            # Remove additional info in parentheses if present
            if '(' in channel_part:
                channel_part = channel_part.split('(')[0].strip()
            return channel_part
        return display_text
    
    def add_favorite(self):
        """Add current channel to favorites"""
        channel = self.channel_var.get().strip()
        if not channel:
            messagebox.showerror("Error", "Please enter a channel name")
            return
        
        if self.favorites_manager.add_favorite(channel):
            # Add to status monitoring
            self.status_monitor.add_channel_to_monitoring(channel)
            self.refresh_favorites_list()
            self.status_var.set(f"Added {channel} to favorites")
            messagebox.showinfo("Success", f"Added {channel} to favorites")
        else:
            messagebox.showwarning("Warning", f"{channel} is already in favorites")
    
    def add_new_favorite(self):
        """Add a new favorite channel via dialog"""
        channel = simpledialog.askstring("Add Favorite", "Enter channel name:")
        if channel:
            if self.favorites_manager.add_favorite(channel):
                # Add to status monitoring
                self.status_monitor.add_channel_to_monitoring(channel)
                self.refresh_favorites_list()
                self.status_var.set(f"Added {channel} to favorites")
                messagebox.showinfo("Success", f"Added {channel} to favorites")
            else:
                messagebox.showwarning("Warning", f"{channel} is already in favorites")
    
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
        self.watch_btn.config(state='normal', text="Watch Stream")
        self.status_var.set(message)
    
    def stream_error(self, message):
        """Handle stream error"""
        self.watch_btn.config(state='normal', text="Watch Stream")
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
        """Handle window closing"""
        # Stop status monitoring
        self.status_monitor.stop_monitoring()
        # Destroy window
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