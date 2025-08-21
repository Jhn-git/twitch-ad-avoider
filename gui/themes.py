"""
Theme definitions for TwitchAdAvoider GUI
Centralized color management for light and dark modes
"""

LIGHT_THEME = {
    # Root window and frames
    "root_bg": "#F0F0F0",
    "frame_bg": "#F0F0F0",
    
    # Text widgets and input fields
    "text_bg": "#FFFFFF",
    "text_fg": "#000000",
    "text_select_bg": "#0078D4",
    "text_select_fg": "#FFFFFF",
    "text_disabled_bg": "#F5F5F5",
    
    # Status bar and message levels
    "status_bg": "#F0F0F0",
    "status_info": "#000000",
    "status_warning": "#FF8C00",
    "status_error": "#DC143C", 
    "status_system": "#0000FF",
    
    # Validation feedback colors
    "validation_valid": "#008000",
    "validation_invalid": "#FF0000", 
    "validation_neutral": "#808080",
    
    # Canvas status circles
    "circle_live_fill": "#E74C3C",
    "circle_live_outline": "#C0392B",
    "circle_offline_fill": "#95A5A6", 
    "circle_offline_outline": "#7F8C8D",
    "canvas_bg": "#FFFFFF",
    "canvas_selected_bg": "#0078D4",
    
    # TTK widget theming
    "button_bg": "#E1E1E1",
    "button_fg": "#000000",
    "button_active_bg": "#CCCCCC",
    "entry_bg": "#FFFFFF",
    "entry_fg": "#000000",
    "entry_select_bg": "#0078D4",
    "combobox_bg": "#FFFFFF",
    "combobox_fg": "#000000",
    "label_bg": "#F0F0F0",
    "label_fg": "#000000",
    "labelframe_bg": "#F0F0F0",
    "labelframe_fg": "#000000"
}

DARK_THEME = {
    # Root window and frames
    "root_bg": "#2E2E2E",
    "frame_bg": "#2E2E2E",
    
    # Text widgets and input fields  
    "text_bg": "#3C3C3C",
    "text_fg": "#FFFFFF",
    "text_select_bg": "#5A90D8",
    "text_select_fg": "#000000",
    "text_disabled_bg": "#404040",
    
    # Status bar and message levels
    "status_bg": "#2E2E2E",
    "status_info": "#FFFFFF",
    "status_warning": "#FFA500",
    "status_error": "#FF6B6B",
    "status_system": "#87CEEB",
    
    # Validation feedback colors
    "validation_valid": "#90EE90",
    "validation_invalid": "#FF6B6B",
    "validation_neutral": "#C0C0C0",
    
    # Canvas status circles (brighter for dark background)
    "circle_live_fill": "#FF4C4C",
    "circle_live_outline": "#FF6B6B", 
    "circle_offline_fill": "#A0A0A0",
    "circle_offline_outline": "#BEBEBE",
    "canvas_bg": "#3C3C3C",
    "canvas_selected_bg": "#5A90D8",
    
    # TTK widget theming
    "button_bg": "#505050",
    "button_fg": "#FFFFFF",
    "button_active_bg": "#606060",
    "entry_bg": "#3C3C3C",
    "entry_fg": "#FFFFFF", 
    "entry_select_bg": "#5A90D8",
    "combobox_bg": "#3C3C3C",
    "combobox_fg": "#FFFFFF",
    "label_bg": "#2E2E2E",
    "label_fg": "#FFFFFF",
    "labelframe_bg": "#2E2E2E",
    "labelframe_fg": "#FFFFFF"
}

# Theme registry
THEMES = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME
}

def get_theme(theme_name: str) -> dict:
    """
    Get theme dictionary by name.
    
    Args:
        theme_name: Name of the theme ("light" or "dark")
        
    Returns:
        Dictionary containing theme colors
        
    Raises:
        KeyError: If theme name is not found
    """
    if theme_name not in THEMES:
        raise KeyError(f"Theme '{theme_name}' not found. Available themes: {list(THEMES.keys())}")
    
    return THEMES[theme_name]

def get_available_themes() -> list:
    """
    Get list of available theme names.
    
    Returns:
        List of theme names
    """
    return list(THEMES.keys())

def is_valid_theme(theme_name: str) -> bool:
    """
    Check if theme name is valid.
    
    Args:
        theme_name: Theme name to validate
        
    Returns:
        True if theme name is valid, False otherwise
    """
    return theme_name in THEMES