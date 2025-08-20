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

from src.twitch_viewer import TwitchViewer, TwitchStreamError
from gui.favorites_manager import FavoritesManager

class StreamGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TwitchAdAvoider - Stream Manager")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        
        # Initialize managers
        self.viewer = TwitchViewer()
        self.favorites_manager = FavoritesManager()
        
        # Current stream process
        self.current_stream_thread = None
        
        # Create GUI components
        self.setup_gui()
        self.refresh_favorites_list()
        
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
        ttk.Button(fav_btn_frame, text="▶ Watch", command=self.watch_favorite).pack(side=tk.LEFT)
        
        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Player selection
        ttk.Label(settings_frame, text="Player:").grid(row=0, column=0, sticky=tk.W)
        self.player_var = tk.StringVar(value=self.viewer.settings.get('player', 'vlc'))
        player_combo = ttk.Combobox(settings_frame, textvariable=self.player_var, width=10)
        player_combo['values'] = ('vlc', 'mpv', 'mpc-hc', 'auto')
        player_combo.grid(row=0, column=1, padx=(5, 0))
        player_combo.state(['readonly'])
        
        # Debug mode
        self.debug_var = tk.BooleanVar(value=self.viewer.settings.get('debug', False))
        debug_check = ttk.Checkbutton(settings_frame, text="Debug Mode", variable=self.debug_var)
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
        """Refresh the favorites listbox"""
        self.favorites_listbox.delete(0, tk.END)
        for favorite in self.favorites_manager.get_favorites():
            self.favorites_listbox.insert(tk.END, favorite)
    
    def watch_stream(self):
        """Start watching a stream"""
        channel = self.channel_var.get().strip()
        if not channel:
            messagebox.showerror("Error", "Please enter a channel name")
            return
        
        # Update viewer settings
        self.viewer.settings['player'] = self.player_var.get()
        self.viewer.settings['preferred_quality'] = self.quality_var.get()
        self.viewer.settings['debug'] = self.debug_var.get()
        
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
        
        channel = self.favorites_listbox.get(selection[0])
        self.channel_var.set(channel)
        self.watch_stream()
    
    def add_favorite(self):
        """Add current channel to favorites"""
        channel = self.channel_var.get().strip()
        if not channel:
            messagebox.showerror("Error", "Please enter a channel name")
            return
        
        if self.favorites_manager.add_favorite(channel):
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
        
        channel = self.favorites_listbox.get(selection[0])
        if messagebox.askyesno("Confirm", f"Remove {channel} from favorites?"):
            self.favorites_manager.remove_favorite(channel)
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

def main():
    """Main GUI entry point"""
    root = tk.Tk()
    app = StreamGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()