"""
Theme management controller for TwitchAdAvoider GUI.

This module provides centralized theme handling and animation functionality,
extracted from the monolithic StreamGUI class to improve maintainability.

The :class:`ThemeController` handles:
    - Theme application to widgets and styles
    - Smooth theme transition animations
    - Widget registration for theme management
    - TTK style configuration
    - Theme state management

Key Features:
    - Animated theme transitions with overlays
    - Centralized widget theming
    - TTK style management
    - Theme persistence integration
    - Callback-based theme change notifications
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional, Callable

from ..themes import get_theme
from ..status_manager import StatusManager
from src.logging_config import get_logger

logger = get_logger(__name__)


class ThemeController:
    """
    Manages theme application and animations for the GUI application.
    
    This controller extracts theme management logic from the main GUI class,
    providing a clean separation between UI presentation and theme handling.
    """

    def __init__(self, root: tk.Tk, initial_theme_name: str = "light"):
        """
        Initialize the ThemeController.

        Args:
            root: Root tkinter window
            initial_theme_name: Initial theme to apply
        """
        self.root = root
        self.current_theme_name = initial_theme_name
        self.current_theme = get_theme(initial_theme_name)
        
        # Widget management
        self.themed_widgets: List[Any] = []
        self.canvas_widgets: List[tk.Canvas] = []
        
        # Animation state
        self.theme_animation_active = False
        
        # Status manager integration (set by parent)
        self.status_manager: Optional[StatusManager] = None
        
        # Callbacks for theme changes
        self.on_theme_changed: Optional[Callable[[str, Dict[str, Any]], None]] = None

    def set_status_manager(self, status_manager: StatusManager) -> None:
        """
        Set the status manager for theme integration.
        
        Args:
            status_manager: Status manager instance
        """
        self.status_manager = status_manager

    def set_theme_change_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Set callback for theme change notifications.
        
        Args:
            callback: Function called when theme changes (theme_name, theme_dict)
        """
        self.on_theme_changed = callback

    def register_themed_widgets(self, *widgets) -> None:
        """
        Register widgets for automatic theme application.
        
        Args:
            *widgets: Widgets to register for theming
        """
        for widget in widgets:
            if widget not in self.themed_widgets:
                self.themed_widgets.append(widget)

    def register_canvas_widgets(self, *canvases) -> None:
        """
        Register canvas widgets for theme-aware background updates.
        
        Args:
            *canvases: Canvas widgets to register
        """
        for canvas in canvases:
            if canvas not in self.canvas_widgets:
                self.canvas_widgets.append(canvas)

    def get_current_theme(self) -> Dict[str, Any]:
        """
        Get the current theme dictionary.
        
        Returns:
            Current theme configuration
        """
        return self.current_theme

    def get_current_theme_name(self) -> str:
        """
        Get the current theme name.
        
        Returns:
            Current theme name
        """
        return self.current_theme_name

    def change_theme(self, theme_name: str, animate: bool = False, animation_duration: int = 250) -> bool:
        """
        Change to a different theme.
        
        Args:
            theme_name: Name of theme to apply
            animate: Whether to use animation transition
            animation_duration: Animation duration in milliseconds
            
        Returns:
            True if theme was changed, False if already current
        """
        if self.current_theme_name == theme_name:
            return False
            
        # Update theme
        self.current_theme_name = theme_name
        self.current_theme = get_theme(theme_name)
        
        # Apply theme
        if animate:
            self.apply_theme_with_animation(animation_duration)
        else:
            self.apply_theme()
            
        # Notify callback
        if self.on_theme_changed:
            self.on_theme_changed(theme_name, self.current_theme)
            
        logger.info(f"Theme changed to: {theme_name}")
        return True

    def toggle_theme(self, animate: bool = True) -> str:
        """
        Toggle between light and dark themes.
        
        Args:
            animate: Whether to use animation transition
            
        Returns:
            New theme name after toggle
        """
        new_theme = "dark" if self.current_theme_name == "light" else "light"
        self.change_theme(new_theme, animate)
        return new_theme

    def apply_theme(self) -> None:
        """Apply the current theme to all registered widgets and styles"""
        theme = self.current_theme
        
        # Apply theme to specific widgets that need direct configuration
        self._apply_theme_to_text_widgets(theme)
        
        # Configure TTK styles
        self._configure_ttk_styles(theme)
        
        # Update canvas backgrounds
        self._update_canvas_backgrounds(theme)
        
        # Update status manager theme
        if self.status_manager:
            self.status_manager.update_theme(theme)
            
        logger.debug(f"Applied theme: {self.current_theme_name}")

    def apply_theme_with_animation(self, duration_ms: int = 250) -> None:
        """
        Apply theme with smooth transition animation.
        
        Args:
            duration_ms: Duration of transition in milliseconds
        """
        if self.theme_animation_active:
            logger.debug("Theme animation already active, skipping")
            return
            
        self.theme_animation_active = True
        
        # Create transition overlay
        overlay = self._create_transition_overlay()
        if not overlay:
            # Fallback to direct theme application
            self.apply_theme()
            self.theme_animation_active = False
            return
            
        # Apply theme after brief delay
        self.root.after(duration_ms // 4, lambda: self._apply_theme_with_fade(overlay, duration_ms // 2))

    def _create_transition_overlay(self) -> Optional[tk.Toplevel]:
        """Create semi-transparent overlay for theme transition"""
        try:
            overlay = tk.Toplevel(self.root)
            overlay.withdraw()  # Hide initially
            overlay.overrideredirect(True)  # Remove decorations
            overlay.attributes('-topmost', True)  # Keep on top
            
            # Position over main window
            self.root.update_idletasks()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            
            overlay.geometry(f"{width}x{height}+{x}+{y}")
            overlay.configure(bg="white")
            
            # Show with transparency
            overlay.deiconify()
            overlay.attributes('-alpha', 0.6)
            
            return overlay
            
        except tk.TclError as e:
            logger.warning(f"Could not create transition overlay: {e}")
            return None

    def _apply_theme_with_fade(self, overlay: tk.Toplevel, fade_duration: int) -> None:
        """Apply theme and fade out overlay"""
        self.apply_theme()
        self._fade_out_overlay(overlay, fade_duration)

    def _fade_out_overlay(self, overlay: tk.Toplevel, duration_ms: int) -> None:
        """Fade out transition overlay with steps"""
        steps = 10
        step_delay = duration_ms // steps
        alpha_step = 0.6 / steps
        current_alpha = 0.6
        
        def fade_step():
            nonlocal current_alpha
            current_alpha -= alpha_step
            
            if current_alpha <= 0:
                try:
                    overlay.destroy()
                except tk.TclError:
                    pass  # Already destroyed
                self.theme_animation_active = False
            else:
                try:
                    overlay.attributes('-alpha', current_alpha)
                    self.root.after(step_delay, fade_step)
                except tk.TclError:
                    # Overlay destroyed, stop animation
                    self.theme_animation_active = False
                    
        fade_step()

    def _apply_theme_to_text_widgets(self, theme: Dict[str, Any]) -> None:
        """Apply theme to text widgets that need direct configuration"""
        # This method can be extended to handle specific text widgets
        # Currently, most theming is handled through TTK styles
        pass

    def _configure_ttk_styles(self, theme: Dict[str, Any]) -> None:
        """Configure TTK widget styles based on theme"""
        style = ttk.Style()
        
        try:
            style.theme_use("clam")  # Use clam as base theme
        except tk.TclError:
            pass  # Use default if clam unavailable
            
        # Configure widget styles
        style.configure("TFrame", background=theme["frame_bg"])
        style.configure(
            "TLabelFrame", 
            background=theme["frame_bg"], 
            foreground=theme["labelframe_fg"]
        )
        style.configure(
            "TLabelFrame.Label", 
            background=theme["frame_bg"], 
            foreground=theme["labelframe_fg"]
        )
        style.configure(
            "TLabel", 
            background=theme["label_bg"], 
            foreground=theme["label_fg"]
        )
        style.configure(
            "TButton", 
            background=theme["button_bg"], 
            foreground=theme["button_fg"]
        )
        style.map("TButton", background=[("active", theme["button_active_bg"])])
        style.configure(
            "TEntry", 
            fieldbackground=theme["entry_bg"], 
            foreground=theme["entry_fg"]
        )
        style.configure(
            "TCombobox", 
            fieldbackground=theme["combobox_bg"], 
            foreground=theme["combobox_fg"]
        )

    def _update_canvas_backgrounds(self, theme: Dict[str, Any]) -> None:
        """Update canvas widget backgrounds based on theme"""
        bg_color = theme.get("canvas_bg", "white")
        
        for canvas in self.canvas_widgets:
            try:
                canvas.configure(bg=bg_color)
            except tk.TclError:
                # Canvas may have been destroyed
                pass

    def update_validation_colors(self, validation_label: ttk.Label) -> None:
        """
        Update validation label colors based on current theme.
        
        Args:
            validation_label: Label widget to update
        """
        # This allows other components to request theme-aware color updates
        # The actual color setting should be done by the validation controller
        pass

    def get_theme_color(self, color_key: str, default: str = "#000000") -> str:
        """
        Get a specific color from the current theme.
        
        Args:
            color_key: Key for the color in theme dictionary
            default: Default color if key not found
            
        Returns:
            Color value from theme or default
        """
        return self.current_theme.get(color_key, default)

    def cleanup(self) -> None:
        """Clean up theme controller resources"""
        self.themed_widgets.clear()
        self.canvas_widgets.clear()
        self.theme_animation_active = False
        logger.debug("Theme controller cleaned up")