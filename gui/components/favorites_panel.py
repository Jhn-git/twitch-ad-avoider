"""
Favorites panel component for TwitchAdAvoider GUI.

This module provides the favorites list display and management interface,
extracted from the monolithic StreamGUI class to improve maintainability.

The :class:`FavoritesPanel` handles:
    - Favorites list display with status indicators
    - Channel selection and interaction
    - Add/remove favorites functionality
    - Status refresh controls
    - Theme-aware visual styling

Key Features:
    - Canvas-based status indicators with emoji support
    - Click and double-click interaction handling
    - Real-time status updates and visual feedback
    - Scrollable list with proper selection management
"""

import tkinter as tk
from tkinter import ttk, font, simpledialog
from typing import Optional, Dict, Any, List, Callable

from ..status_manager import StatusManager, StatusCategory
from ..favorites_manager import FavoritesManager, FavoriteChannelInfo
from ..themes import get_emoji_font
from src.logging_config import get_logger
from src.exceptions import ValidationError

logger = get_logger(__name__)


class FavoritesPanel:
    """
    Manages the favorites list display and interactions.
    
    This component handles the favorites section of the GUI, providing
    a clean interface for channel favorites management.
    """

    def __init__(self, 
                 parent: ttk.Frame,
                 favorites_manager: FavoritesManager,
                 status_manager: StatusManager,
                 current_theme: Dict[str, Any]):
        """
        Initialize the FavoritesPanel.

        Args:
            parent: Parent frame to contain the favorites section
            favorites_manager: Manager for favorites persistence
            status_manager: Status manager for user feedback
            current_theme: Current theme configuration
        """
        self.parent = parent
        self.favorites_manager = favorites_manager
        self.status_manager = status_manager
        self.current_theme = current_theme
        
        # Selection tracking
        self.selected_favorite_line: Optional[int] = None
        self.canvas_widgets: List[tk.Canvas] = []
        
        # Spinner state
        self._refresh_spinner_running = False
        self._refresh_spinner_index = 0
        
        # UI references
        self.favorites_listbox: Optional[tk.Text] = None
        self.refresh_btn: Optional[ttk.Button] = None
        self.cancel_btn: Optional[ttk.Button] = None
        
        # Callbacks (set by parent components)
        self.on_channel_selected: Optional[Callable[[str], None]] = None
        self.on_watch_favorite: Optional[Callable[[str], None]] = None
        self.on_refresh_status: Optional[Callable[[], None]] = None
        self.on_cancel_operation: Optional[Callable[[], bool]] = None
        
        # Create the favorites section
        self.main_frame = self._create_favorites_section()

    def set_callbacks(self,
                     on_channel_selected: Optional[Callable[[str], None]] = None,
                     on_watch_favorite: Optional[Callable[[str], None]] = None,
                     on_refresh_status: Optional[Callable[[], None]] = None,
                     on_cancel_operation: Optional[Callable[[], bool]] = None) -> None:
        """
        Set callback functions for user interactions.
        
        Args:
            on_channel_selected: Called when a channel is selected
            on_watch_favorite: Called when user wants to watch a favorite
            on_refresh_status: Called when user requests status refresh
            on_cancel_operation: Called when user wants to cancel current operation
        """
        self.on_channel_selected = on_channel_selected
        self.on_watch_favorite = on_watch_favorite
        self.on_refresh_status = on_refresh_status
        self.on_cancel_operation = on_cancel_operation

    def set_theme(self, theme: Dict[str, Any]) -> None:
        """
        Update the current theme.
        
        Args:
            theme: New theme configuration
        """
        self.current_theme = theme
        self._apply_theme_to_widgets()

    def _create_favorites_section(self) -> ttk.LabelFrame:
        """Create the complete favorites section"""
        fav_frame = ttk.LabelFrame(self.parent, text="Favorites", padding="10")
        fav_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Create favorites list
        self._create_favorites_list(fav_frame)
        
        # Create management buttons
        self._create_favorites_buttons(fav_frame)

        return fav_frame

    def _create_favorites_list(self, parent: ttk.LabelFrame) -> None:
        """Create the favorites list widget with scrollbar"""
        list_frame = ttk.Frame(parent)
        list_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure text widget with emoji-supporting font
        emoji_font_config = get_emoji_font()
        if emoji_font_config:
            family, size = emoji_font_config
            favorites_font = font.Font(family=family, size=size)
            self.favorites_listbox = tk.Text(
                list_frame,
                height=8,
                font=favorites_font,
                state=tk.DISABLED,
                cursor="arrow",
                wrap=tk.NONE,
            )
        else:
            self.favorites_listbox = tk.Text(
                list_frame, height=8, state=tk.DISABLED, cursor="arrow", wrap=tk.NONE
            )

        # Create scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.favorites_listbox.yview
        )
        self.favorites_listbox.configure(yscrollcommand=scrollbar.set)

        # Configure appearance
        self.favorites_listbox.configure(
            bg="white",
            relief=tk.SUNKEN,
            borderwidth=1,
            selectbackground="#0078d4",
            selectforeground="white",
        )

        self.favorites_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Configure grid weights
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Bind events
        self.favorites_listbox.bind("<Button-1>", self._on_favorite_click)
        self.favorites_listbox.bind("<Double-Button-1>", self._on_favorite_double_click)

    def _create_favorites_buttons(self, parent: ttk.LabelFrame) -> None:
        """Create the favorites management buttons"""
        fav_btn_frame = ttk.Frame(parent)
        fav_btn_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0))

        ttk.Button(fav_btn_frame, text="Add Current", command=self.add_current_favorite).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(fav_btn_frame, text="Add New", command=self.add_new_favorite).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(fav_btn_frame, text="Remove", command=self.remove_favorite).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.refresh_btn = ttk.Button(fav_btn_frame, text="🔄 Refresh", command=self.refresh_status)
        self.refresh_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        self.cancel_btn = ttk.Button(fav_btn_frame, text="⏹ Cancel", command=self.cancel_operation)
        self.cancel_btn.pack(side=tk.LEFT, padx=(5, 0))
        self.cancel_btn.config(state="disabled")  # Initially disabled

    def _on_favorite_click(self, event) -> None:
        """Handle click events in the favorites list"""
        if not self.favorites_listbox:
            return
            
        # Get clicked line
        click_index = self.favorites_listbox.index(f"@{event.x},{event.y}")
        line_start = click_index.split(".")[0] + ".0"
        line_end = click_index.split(".")[0] + ".end"

        # Clear previous selection
        self.favorites_listbox.configure(state=tk.NORMAL)
        if self.selected_favorite_line:
            old_start = f"{self.selected_favorite_line}.0"
            old_end = f"{self.selected_favorite_line}.end"
            self.favorites_listbox.tag_remove("selected", old_start, old_end)

        # Add selection to clicked line
        line_num = int(click_index.split(".")[0])
        self.selected_favorite_line = line_num
        self.favorites_listbox.tag_add("selected", line_start, line_end)
        self.favorites_listbox.tag_configure("selected", background="#0078d4", foreground="white")

        # Update canvas backgrounds
        self._update_canvas_backgrounds()
        self.favorites_listbox.configure(state=tk.DISABLED)

        # Extract channel name and notify callback
        display_text = self.favorites_listbox.get(line_start, line_end).strip()
        if display_text and self.on_channel_selected:
            channel = self._extract_channel_name(display_text)
            self.on_channel_selected(channel)

    def _on_favorite_double_click(self, event) -> None:
        """Handle double-click events to watch favorite"""
        self._on_favorite_click(event)  # First select the item
        self.watch_favorite()

    def watch_favorite(self) -> None:
        """Watch the selected favorite channel"""
        if not self.selected_favorite_line or not self.favorites_listbox:
            self.status_manager.add_warning("Please select a favorite channel", StatusCategory.FAVORITES)
            return

        # Extract channel name from selected line
        line_start = f"{self.selected_favorite_line}.0"
        line_end = f"{self.selected_favorite_line}.end"
        display_text = self.favorites_listbox.get(line_start, line_end).strip()

        if not display_text:
            self.status_manager.add_warning("No channel selected", StatusCategory.FAVORITES)
            return

        channel = self._extract_channel_name(display_text)
        if self.on_watch_favorite:
            self.on_watch_favorite(channel)

    def add_current_favorite(self) -> None:
        """Add current channel to favorites (requires callback setup)"""
        if self.on_channel_selected:
            # This method needs to be called with current channel
            # Implementation depends on getting current channel from parent
            logger.debug("Add current favorite requested - needs parent implementation")

    def add_new_favorite(self) -> None:
        """Prompt user to add a new favorite channel"""
        channel_name = simpledialog.askstring("Add Favorite", "Enter channel name:")
        if channel_name:
            self._add_channel_to_favorites(channel_name.strip())

    def remove_favorite(self) -> None:
        """Remove the selected favorite channel"""
        if not self.selected_favorite_line or not self.favorites_listbox:
            self.status_manager.add_warning("Please select a favorite to remove", StatusCategory.FAVORITES)
            return

        # Extract channel name
        line_start = f"{self.selected_favorite_line}.0"
        line_end = f"{self.selected_favorite_line}.end"
        display_text = self.favorites_listbox.get(line_start, line_end).strip()
        
        if display_text:
            channel = self._extract_channel_name(display_text)
            self.favorites_manager.remove_channel(channel)
            self.refresh_favorites_list()
            self.status_manager.add_favorites_message(f"Removed {channel} from favorites")
            self.selected_favorite_line = None

    def refresh_status(self) -> None:
        """Refresh favorites status with improved feedback"""
        if not self.on_refresh_status:
            return
            
        # Start spinner on refresh button
        if self.refresh_btn:
            self._start_refresh_spinner()
            
        # Add status message
        if self.status_manager:
            self.status_manager.add_status_message("Refreshing stream status...")
            
        # Execute refresh callback
        self.on_refresh_status()
        
        # Schedule spinner stop (will be overridden by actual completion)
        self._schedule_spinner_stop()
        
    def cancel_operation(self) -> None:
        """Cancel the current operation"""
        if self.on_cancel_operation:
            success = self.on_cancel_operation()
            if success:
                if self.status_manager:
                    self.status_manager.add_status_message("Operation cancelled")
                self._stop_refresh_spinner()
            else:
                if self.status_manager:
                    self.status_manager.add_warning("No operation to cancel")
        
    def _start_refresh_spinner(self) -> None:
        """Start spinner animation on refresh button"""
        if not self.refresh_btn:
            return
            
        self._refresh_spinner_running = True
        self._refresh_spinner_index = 0
        self.refresh_btn.config(state="disabled")
        
        # Enable cancel button
        if self.cancel_btn:
            self.cancel_btn.config(state="normal")
            
        self._update_refresh_spinner()
        
    def _update_refresh_spinner(self) -> None:
        """Update refresh spinner animation frame"""
        if not self._refresh_spinner_running or not self.refresh_btn:
            return
            
        # Use spinner characters for animation
        spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner_char = spinner_chars[self._refresh_spinner_index]
        self.refresh_btn.config(text=f"{spinner_char} Refreshing...")
        
        self._refresh_spinner_index = (self._refresh_spinner_index + 1) % len(spinner_chars)
        
        # Schedule next update
        if self.main_frame:
            self.main_frame.after(150, self._update_refresh_spinner)
            
    def _stop_refresh_spinner(self) -> None:
        """Stop refresh spinner animation"""
        self._refresh_spinner_running = False
        if self.refresh_btn:
            self.refresh_btn.config(state="normal", text="🔄 Refresh")
            
        # Disable cancel button
        if self.cancel_btn:
            self.cancel_btn.config(state="disabled")
            
    def _schedule_spinner_stop(self, delay: int = 3000) -> None:
        """Schedule spinner stop after delay"""
        if self.main_frame:
            self.main_frame.after(delay, self._stop_refresh_spinner)
            
    def on_refresh_completed(self) -> None:
        """Called when refresh operation is completed"""
        self._stop_refresh_spinner()
        if self.status_manager:
            self.status_manager.add_status_message("Status refresh completed")

    def _add_channel_to_favorites(self, channel_name: str) -> None:
        """
        Add a channel to favorites with validation.
        
        Args:
            channel_name: Channel name to add
        """
        if not channel_name:
            self.status_manager.add_error("Please enter a channel name", StatusCategory.FAVORITES)
            return

        try:
            # Validate and add channel
            from src.validators import validate_channel_name
            validated_channel = validate_channel_name(channel_name)
            
            if self.favorites_manager.add_channel(validated_channel):
                self.refresh_favorites_list()
                self.status_manager.add_favorites_message(f"Added {validated_channel} to favorites")
            else:
                self.status_manager.add_warning(
                    f"{validated_channel} is already in favorites", 
                    StatusCategory.FAVORITES
                )
                
        except ValidationError as e:
            self.status_manager.add_error(str(e), StatusCategory.FAVORITES)

    def _extract_channel_name(self, display_text: str) -> str:
        """Extract channel name from formatted display text"""
        # Format: " channel_name" (Canvas circle + space + channel name)
        return display_text.strip()

    def refresh_favorites_list(self) -> None:
        """Refresh the favorites list display"""
        if not self.favorites_listbox:
            return
            
        # Clear existing content
        self.favorites_listbox.configure(state=tk.NORMAL)
        self.favorites_listbox.delete(1.0, tk.END)
        self.canvas_widgets.clear()

        # Get favorites data
        favorites = self.favorites_manager.get_all_channels()
        
        if not favorites:
            self.favorites_listbox.insert(tk.END, "No favorites added yet")
            self.favorites_listbox.configure(state=tk.DISABLED)
            return

        # Add each favorite with status indicator
        for i, fav in enumerate(favorites):
            self._add_favorite_to_display(fav, i + 1)

        self.favorites_listbox.configure(state=tk.DISABLED)

    def _add_favorite_to_display(self, fav: FavoriteChannelInfo, line_num: int) -> None:
        """Add a favorite channel to the display"""
        if not self.favorites_listbox:
            return
            
        # Create status circle
        canvas = self._create_status_canvas(fav.status)
        self.canvas_widgets.append(canvas)
        
        # Insert canvas widget
        self.favorites_listbox.window_create(tk.END, window=canvas)
        
        # Add channel name with spacing
        self.favorites_listbox.insert(tk.END, f" {fav.channel}")
        
        # Add newline for next entry (except last)
        if line_num < len(self.favorites_manager.get_all_channels()):
            self.favorites_listbox.insert(tk.END, "\n")

    def _create_status_canvas(self, status: str) -> tk.Canvas:
        """Create a canvas widget for status circle"""
        canvas = tk.Canvas(
            self.favorites_listbox,
            width=16,
            height=16,
            highlightthickness=0,
            bd=0
        )
        
        # Determine circle color based on status
        if status == "online":
            color = "#28a745"  # Green
        elif status == "offline":
            color = "#dc3545"  # Red  
        else:
            color = "#6c757d"  # Gray for unknown
            
        # Draw status circle
        canvas.create_oval(3, 3, 13, 13, fill=color, outline="")
        
        return canvas

    def _update_canvas_backgrounds(self) -> None:
        """Update canvas widget backgrounds to match selection"""
        if not self.canvas_widgets:
            return
            
        for i, canvas in enumerate(self.canvas_widgets):
            line_num = i + 1
            if line_num == self.selected_favorite_line:
                canvas.configure(bg="#0078d4")  # Selected background
            else:
                canvas.configure(bg="white")  # Default background

    def _apply_theme_to_widgets(self) -> None:
        """Apply current theme to favorites widgets"""
        if self.favorites_listbox:
            # Update text widget colors based on theme
            bg_color = self.current_theme.get("bg", "white")
            fg_color = self.current_theme.get("fg", "black")
            
            self.favorites_listbox.configure(
                bg=bg_color,
                fg=fg_color,
                insertbackground=fg_color
            )

    def get_selected_channel(self) -> Optional[str]:
        """
        Get the currently selected channel name.
        
        Returns:
            Selected channel name or None if no selection
        """
        if not self.selected_favorite_line or not self.favorites_listbox:
            return None
            
        line_start = f"{self.selected_favorite_line}.0"
        line_end = f"{self.selected_favorite_line}.end"
        display_text = self.favorites_listbox.get(line_start, line_end).strip()
        
        if display_text:
            return self._extract_channel_name(display_text)
        return None

    def get_main_frame(self) -> ttk.LabelFrame:
        """Get the main favorites frame"""
        return self.main_frame

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.canvas_widgets.clear()
        self.selected_favorite_line = None