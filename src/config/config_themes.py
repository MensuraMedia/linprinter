"""
Theme Definitions
The seven dark themes of gtk-python-dashboard-starter. The default is the
framework's standard "Default Blue" (as in its dashboard.png), completed with
the framework's own palette from its config_theme.py. Nord is completed from the
official Nord palette.
"""


class ThemeDefinition:
    """Single theme definition (colours used to generate the app CSS)"""

    def __init__(
        self,
        name,
        accent_color,
        sidebar_bg,
        window_bg,
        hover_color,
        card_bg=None,
        raised_bg=None,
        accent_text="#ffffff",
        text_primary="#eeeeee",
        text_secondary="#d0d0d0",
        text_muted="#9a9a9a",
        success="#27ae60",
        error="#cc3333",
    ):
        """Store theme colours; optional ones default from the core four"""
        self.name = name
        self.accent_color = accent_color
        self.sidebar_bg = sidebar_bg
        self.window_bg = window_bg
        self.hover_color = hover_color
        self.card_bg = card_bg or sidebar_bg
        self.raised_bg = raised_bg or hover_color
        self.accent_text = accent_text
        self.text_primary = text_primary
        self.text_secondary = text_secondary
        self.text_muted = text_muted
        self.success = success
        self.error = error


DEFAULT_THEME_ID = "default"

DARK_THEMES = {
    "default": ThemeDefinition(
        name="Default Blue",
        accent_color="#0078D7",  # framework PRIMARY_ACCENT / NAV_BUTTON_ACTIVE
        sidebar_bg="#353535",  # SIDEBAR_BG
        window_bg="#2d2d2d",  # WINDOW_BG / CONTENT_BG
        hover_color="#4a4a4a",  # BUTTON_HOVER
        card_bg="#353535",  # SIDEBAR_BG (panels)
        raised_bg="#404040",  # BUTTON_BG / NAV_BUTTON_HOVER
        accent_text="#ffffff",
        text_primary="#eeeeee",  # TEXT_PRIMARY
        text_secondary="#d0d0d0",  # TEXT_SECONDARY
        text_muted="#9a9a9a",  # between TEXT_DISABLED (#808080) and secondary: readable on #353535
        success="#27ae60",  # SUCCESS
        error="#cc3333",  # ERROR
    ),
    "adapta": ThemeDefinition(
        name="Adapta",
        accent_color="#00bcd4",
        sidebar_bg="#222d32",
        window_bg="#263238",
        hover_color="#2e3c43",
    ),
    "materia": ThemeDefinition(
        name="Materia",
        accent_color="#8ab4f8",
        sidebar_bg="#1e1e1e",
        window_bg="#212121",
        hover_color="#292929",
    ),
    "dracula": ThemeDefinition(
        name="Dracula",
        accent_color="#bd93f9",
        sidebar_bg="#282a36",
        window_bg="#1e1f29",
        hover_color="#383a4a",
    ),
    "nord": ThemeDefinition(
        name="Nord",
        accent_color="#88c0d0",  # nord8 (frost)
        sidebar_bg="#2e3440",  # nord0 (polar night)
        window_bg="#2e3440",  # nord0
        hover_color="#4c566a",  # nord3
        card_bg="#3b4252",  # nord1
        raised_bg="#434c5e",  # nord2
        accent_text="#2e3440",  # dark text on the frost accent
        text_primary="#eceff4",  # nord6 (snow storm)
        text_secondary="#d8dee9",  # nord4
        text_muted="#8f9bb3",  # between nord3 and nord4: readable on nord1
        success="#a3be8c",  # nord14 (aurora green)
        error="#bf616a",  # nord11 (aurora red)
    ),
    "gruvbox": ThemeDefinition(
        name="Gruvbox",
        accent_color="#fe8019",
        sidebar_bg="#282828",
        window_bg="#1d2021",
        hover_color="#3c3836",
    ),
    "monokai": ThemeDefinition(
        name="Monokai",
        accent_color="#f92672",
        sidebar_bg="#272822",
        window_bg="#1e1f1c",
        hover_color="#3e3d32",
        accent_text="#ffffff",
    ),
}


def get_theme(theme_id):
    """Get theme by ID (falls back to the default theme)"""
    return DARK_THEMES.get(theme_id, DARK_THEMES[DEFAULT_THEME_ID])


def get_all_themes():
    """Get all available themes"""
    return DARK_THEMES
