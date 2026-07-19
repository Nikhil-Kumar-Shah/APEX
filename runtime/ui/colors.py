"""Color tokens and theme utility configurations."""

import sys

# Light Theme Color Tokens
LIGHT_THEME = {
    "primary": "#4F46E5",        # Indigo 600
    "primary_hover": "#4338CA",  # Indigo 700
    "secondary": "#4B5563",      # Gray 600
    "background": "#F9FAFB",     # Gray 50
    "surface": "#FFFFFF",        # White
    "surface_elevated": "#F3F4F6", # Gray 100
    "border": "#E5E7EB",         # Gray 200
    "text_primary": "#111827",   # Gray 900
    "text_secondary": "#4B5563", # Gray 600
    "success": "#059669",        # Emerald 600
    "warning": "#D97706",        # Amber 600
    "error": "#DC2626",          # Red 600
    "info": "#2563EB",           # Blue 600
    "gpu": "#10B981",            # Green 500
    "runtime": "#8B5CF6",        # Violet 500
    "memory": "#EC4899",         # Pink 500
    "api": "#3B82F6",            # Blue 500
}

# Dark Theme Color Tokens
DARK_THEME = {
    "primary": "#6366F1",        # Indigo 500
    "primary_hover": "#4F46E5",  # Indigo 600
    "secondary": "#9CA3AF",      # Gray 400
    "background": "#111827",     # Gray 900
    "surface": "#1F2937",        # Gray 800
    "surface_elevated": "#374151", # Gray 700
    "border": "#4B5563",         # Gray 600
    "text_primary": "#F3F4F6",   # Gray 100
    "text_secondary": "#9CA3AF", # Gray 400
    "success": "#34D399",        # Emerald 400
    "warning": "#F59E0B",        # Amber 500
    "error": "#F87171",          # Red 400
    "info": "#60A5FA",           # Blue 400
    "gpu": "#10B981",            # Green 500
    "runtime": "#A78BFA",        # Violet 400
    "memory": "#F472B6",         # Pink 400
    "api": "#60A5FA",            # Blue 400
}

def get_theme_css(dark_mode: bool = True) -> str:
    """Compiles color tokens into CSS custom properties.

    Args:
        dark_mode: If True, uses dark mode theme tokens.

    Returns:
        str: Styled CSS variables block.
    """
    tokens = DARK_THEME if dark_mode else LIGHT_THEME
    return f"""
    :root {{
        --apex-primary: {tokens['primary']};
        --apex-primary-hover: {tokens['primary_hover']};
        --apex-secondary: {tokens['secondary']};
        --apex-background: {tokens['background']};
        --apex-surface: {tokens['surface']};
        --apex-surface-elevated: {tokens['surface_elevated']};
        --apex-border: {tokens['border']};
        --apex-text-primary: {tokens['text_primary']};
        --apex-text-secondary: {tokens['text_secondary']};
        --apex-success: {tokens['success']};
        --apex-warning: {tokens['warning']};
        --apex-error: {tokens['error']};
        --apex-info: {tokens['info']};
        --apex-gpu: {tokens['gpu']};
        --apex-runtime: {tokens['runtime']};
        --apex-memory: {tokens['memory']};
        --apex-api: {tokens['api']};
    }}
    """
