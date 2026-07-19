from typing import Any, Dict, List, Optional

def create_card_html(
    title: str,
    icon: str,
    primary_val: str,
    secondary_val: str = "",
    status_label: Optional[str] = None,
    status_type: str = "success"
) -> str:
    """Generates styled HTML card structures.

    Args:
        title: Title string.
        icon: Emoji/icon prefix.
        primary_val: Main status text.
        secondary_val: Secondary descriptive details.
        status_label: Optional badge text.
        status_type: success, warning, error, or info.

    Returns:
        str: Output HTML code block.
    """
    badge_style = "apex-badge-active"
    if status_type in ["error", "warning"]:
        badge_style = "apex-badge-inactive"
    elif status_type == "info":
        badge_style = "apex-badge-info"

    badge_html = f"<span class='{badge_style}'>{status_label}</span>" if status_label else ""

    return f"""
    <div class="apex-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span class="apex-card-heading">{icon} {title}</span>
            {badge_html}
        </div>
        <div class="apex-metric-primary">{primary_val}</div>
        <div class="apex-metric-secondary">{secondary_val}</div>
    </div>
    """

def get_base_css(dark_mode: bool = True) -> str:
    """Gets total compiled CSS style blocks."""
    from runtime.ui.colors import get_theme_css
    from runtime.ui.typography import TYPOGRAPHY_STYLES
    from runtime.ui.spacing import SPACING_STYLES

    theme_vars = get_theme_css(dark_mode)

    return f"""
    <style>
        {theme_vars}
        {TYPOGRAPHY_STYLES}
        {SPACING_STYLES}

        .apex-app-container {{
            background-color: var(--apex-background);
            color: var(--apex-text-primary);
            font-family: 'Inter', sans-serif;
            display: flex;
            min-height: 500px;
        }}
        .apex-card {{
            background-color: var(--apex-surface);
            border: 1px solid var(--apex-border);
            border-radius: 8px;
            padding: 16px;
            margin: 8px;
            flex: 1;
            min-width: 200px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .apex-badge-active {{
            background-color: var(--apex-success);
            color: #FFFFFF;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }}
        .apex-badge-inactive {{
            background-color: var(--apex-error);
            color: #FFFFFF;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }}
        .apex-badge-info {{
            background-color: var(--apex-info);
            color: #FFFFFF;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }}
    </style>
    """
