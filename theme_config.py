"""
Theme configuration for customizable colors and fonts
"""

import copy
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Default theme (Anki-style dark)
DEFAULT_THEME = {
    'colors': {
        'bg_primary': '#1e2024',      # Main background
        'bg_secondary': '#2a2d32',    # Cards, panels
        'bg_tertiary': '#35393f',     # Hover states, borders
        'bg_input': '#3d4148',        # Input fields
        'accent': '#5294e2',          # Primary accent (blue)
        'accent_hover': '#6ba3eb',    # Accent hover
        'accent_dim': '#3d6a99',      # Muted accent
        'text_primary': '#e8e9eb',    # Main text
        'text_secondary': '#9ba0a8',  # Muted text
        'text_dim': '#828a95',        # Very muted (4.7:1 on bg_primary — keep >=4.5)
        'border': '#404552',          # Borders
        'success': '#5cb85c',         # Green
        'warning': '#f0ad4e',         # Orange
        'danger': '#d9534f',          # Red
        'card_slot': '#292c31',       # Empty card slot
    },
    'fonts': {
        'family_display': 'SF Pro Display',
        'family_text': 'SF Pro Text', 
        'family_mono': 'SF Mono',
        'size_title': 22,
        'size_heading': 14,
        'size_body': 13,
        'size_small': 11,
    }
}


class ThemeConfig:
    """Manages theme configuration with persistence"""
    
    def __init__(self, config_file: str = None):
        if config_file is None:
            self.config_file = Path(os.path.dirname(os.path.abspath(__file__))) / 'theme_config.json'
        else:
            self.config_file = Path(config_file)
        
        self.theme = self._load_theme()
    
    # Old preset text_dim values that fail WCAG contrast (< 4.5:1 on
    # their preset's background), mapped to their fixed replacements.
    # Applied on load so themes saved before the July 2026 contrast
    # pass pick up the readable value; users who chose a custom dim
    # color are untouched (their value won't match any old default).
    _CONTRAST_FIXUPS = {
        '#6b7280': '#828a95',  # Dark (Default)
        '#9ca3af': '#697180',  # Light
        '#8878a8': '#9184b1',  # Midnight Purple
    }

    def _load_theme(self) -> Dict[str, Any]:
        """Load theme from file or return default"""
        saved = {}
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    saved = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load JSON from {self.config_file}: {e}")
        if saved:
            # Each saved section overrides the defaults key by key, so
            # colors/fonts added in later versions still get a value.
            theme = copy.deepcopy(DEFAULT_THEME)
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(theme.get(k), dict):
                    theme[k] = {**theme[k], **v}
                else:
                    theme[k] = v
            colors = theme.get('colors', {})
            old_dim = colors.get('text_dim')
            if old_dim in self._CONTRAST_FIXUPS:
                colors['text_dim'] = self._CONTRAST_FIXUPS[old_dim]
            return theme
        return copy.deepcopy(DEFAULT_THEME)
    
    def save_theme(self):
        """Save current theme to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.theme, f, indent=2)
        except (IOError, OSError) as e:
            logger.error(f"Error saving theme: {e}")
    
    def get_colors(self) -> Dict[str, str]:
        """Get current color scheme"""
        return self.theme['colors']
    
    def get_fonts(self) -> Dict[str, Any]:
        """Get current font settings"""
        return self.theme['fonts']
    
    def set_color(self, key: str, value: str):
        """Set a single color value"""
        if key in self.theme['colors']:
            self.theme['colors'][key] = value
    
    def set_font(self, key: str, value: Any):
        """Set a single font value"""
        if key in self.theme['fonts']:
            self.theme['fonts'][key] = value


# Global instance
_theme_instance = None


def get_theme() -> ThemeConfig:
    """Get the global theme config instance"""
    global _theme_instance
    if _theme_instance is None:
        _theme_instance = ThemeConfig()
    return _theme_instance

