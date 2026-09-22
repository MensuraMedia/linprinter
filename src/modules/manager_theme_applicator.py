"""
Theme Applicator
Generates the application CSS from a ThemeDefinition and applies it to the
screen. Colours come only from the ThemeDefinition (default: the framework's
Default Blue). The current layout still uses rounded cards and pill buttons;
the flat, square framework layout is planned (see docs/HANDOFF.md).
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402


class ThemeApplicator:
    """Applies theme colours to the application"""

    def __init__(self):
        """Create the CSS provider (registered on first apply)"""
        self.css_provider = Gtk.CssProvider()
        self.current_theme = None
        self._registered = False

    def apply_theme(self, theme):
        """Generate and apply CSS for a theme; False if the CSS fails to load"""
        self.current_theme = theme
        from utils.util_icons import set_icon_color

        set_icon_color(theme.text_primary)  # icons follow the theme
        try:
            self.css_provider.load_from_data(self.generate_css(theme).encode())
        except Exception:  # malformed CSS must not stop the app
            from utils.util_logging import get_logger

            get_logger("ui").exception("theme %s could not be applied", theme.name)
            return False
        if not self._registered:
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            self._registered = True
        return True

    @staticmethod
    def generate_css(t):
        """Build the application stylesheet from a ThemeDefinition.

        Layout rules follow gtk-python-dashboard-starter's style.css: flat and
        square, full-width sidebar rows separated by 1px dark borders, the active
        row filled with the accent colour, 2px-radius flat buttons."""
        border = "#1a1a1a"  # framework BORDER_DARK
        border_mid = "#555555"  # framework BORDER_MEDIUM
        return f"""
* {{ font-family: Ubuntu, Cantarell, sans-serif; font-size: 11pt; }}
window, .content-area {{ background-color: {t.window_bg}; color: {t.text_primary}; }}
label {{ color: {t.text_primary}; }}
headerbar {{ background: {t.sidebar_bg}; border-bottom: 1px solid {border}; color: {t.text_primary}; }}

/* Sidebar: framework layout */
.sidebar {{ background-color: {t.sidebar_bg}; border-right: 1px solid {border}; }}
.logo-area {{ background-color: {t.sidebar_bg}; padding: 12px 0; }}
.logo-text {{ color: {t.text_primary}; font-size: 13pt; font-weight: bold; }}
.logo-subtext {{ color: {t.text_secondary}; font-size: 9pt; }}
.nav-button {{
    background: transparent; background-image: none; border: none; border-bottom: 1px solid {border};
    border-radius: 0; box-shadow: none; margin: 0; padding: 6px 15px; min-height: 28px;
}}
.nav-button label {{ color: {t.text_secondary}; font-size: 10pt; }}
.nav-button:hover {{ background-color: {t.raised_bg}; }}
.nav-button:hover label {{ color: #ffffff; }}
.nav-button-top {{ border-top: 1px solid {border}; }}
.nav-button-bottom {{ border-top: 1px solid {border}; border-bottom: none; }}
.nav-button.active, .nav-button.active:hover {{ background-color: {t.accent_color}; }}
.nav-button.active label {{ color: {t.accent_text}; font-weight: bold; }}

/* Pages: heading + text, sections instead of cards */
.page-title {{ font-size: 18pt; font-weight: bold; color: #ffffff; }}
.page-subtitle {{ font-size: 14pt; font-weight: 500; color: {t.text_secondary}; }}
.muted {{ color: {t.text_muted}; }}
.secondary {{ color: {t.text_secondary}; }}
.card {{ background: transparent; border: none; border-top: 1px solid {border}; padding: 12px 0 4px 0; }}
.card-title {{ font-size: 14pt; font-weight: 500; color: {t.text_secondary}; }}
.status-ok {{ color: {t.success}; }}
.status-error {{ color: {t.error}; }}
.status-busy {{ color: {t.accent_color}; }}
.info-key {{ color: {t.text_muted}; }}
.info-value {{ color: {t.text_primary}; }}

/* Inputs */
combobox box {{ border: none; background: transparent; }}
combobox button, entry, filechooserbutton button, spinbutton {{
    background: {t.card_bg}; background-image: none; color: {t.text_primary};
    border: 1px solid {border_mid}; border-radius: 2px; box-shadow: none; min-height: 28px;
}}
combobox window menu, menu {{ background: {t.card_bg}; color: {t.text_primary}; }}
menuitem:hover {{ background: {t.accent_color}; }}
checkbutton check {{ background-image: none; background-color: {t.card_bg}; border: 1px solid {border_mid}; border-radius: 2px; }}
checkbutton check:checked {{ background-image: none; background-color: {t.accent_color}; border-color: {t.accent_color}; color: #ffffff; }}
scale trough {{ background: {t.raised_bg}; border-radius: 0; min-height: 4px; }}
scale highlight {{ background: {t.accent_color}; }}
scale slider {{ background: {t.text_primary}; border-radius: 2px; min-width: 12px; min-height: 12px; }}

/* Buttons: flat, 2px radius */
button {{
    background: {t.raised_bg}; background-image: none; color: {t.text_primary};
    border: 1px solid {border_mid}; border-radius: 2px; box-shadow: none; padding: 2px 12px; min-height: 28px;
}}
button label {{ color: {t.text_primary}; font-size: 10pt; }}  /* never bigger than the sidebar labels (10pt) */
combobox button label, combobox button cellview {{ font-size: 10pt; }}
button:hover {{ background: {t.hover_color}; }}
button:disabled {{ background: {t.card_bg}; }}
button:disabled label {{ color: {t.text_muted}; }}
.primary-pill {{ background: {t.accent_color}; border: 1px solid {t.accent_color}; padding: 2px 16px; min-height: 28px; }}
.primary-pill label {{ color: {t.accent_text}; font-weight: bold; font-size: 10pt; }}
.primary-pill:hover {{ background: shade({t.accent_color}, 1.1); }}
.primary-pill:disabled {{ background: {t.raised_bg}; border-color: {border_mid}; }}

/* Segmented toggles: square, joined */
.segment {{ background: transparent; padding: 0; }}
.segment button {{ border-radius: 0; margin: 0; padding: 2px 12px; min-height: 28px; }}
.segment button label {{ color: {t.text_secondary}; font-size: 10pt; }}
.segment button:checked {{ background: {t.accent_color}; border-color: {t.accent_color}; }}
.segment button:checked label {{ color: {t.accent_text}; font-weight: bold; }}
list row:selected {{ background-color: {t.accent_color}; }}
list row:selected label {{ color: {t.accent_text}; }}

/* Icon buttons (Phosphor): square, as tall as the sidebar rows */
.icon-button {{ padding: 2px 5px; min-width: 28px; min-height: 28px; }}
.icon-flat {{ background: transparent; border-color: transparent; }}
.icon-flat:hover {{ background: {t.hover_color}; border-color: {border_mid}; }}

/* Tables (Recent) */
treeview.view {{ background-color: {t.card_bg}; color: {t.text_primary}; }}
treeview.view:selected {{ background-color: {t.accent_color}; color: {t.accent_text}; }}
treeview.view header button {{ background: {t.raised_bg}; border-radius: 0; padding: 2px 8px; min-height: 26px; }}
treeview.view header button label {{ color: {t.text_secondary}; font-weight: bold; }}

/* Progress */
progressbar trough {{ background: {t.card_bg}; border: 1px solid {border}; border-radius: 0; min-height: 6px; }}
progressbar progress {{ background: {t.accent_color}; border-radius: 0; min-height: 6px; }}

/* Preview */
.preview-frame {{ background-color: #1e1e1e; border: 1px solid {border}; }}
.thumb {{ background: {t.card_bg}; border: 2px solid {border}; border-radius: 0; padding: 3px; }}
.thumb.selected {{ border: 2px solid {t.accent_color}; }}
.thumb-label {{ color: {t.text_muted}; font-size: 9pt; }}
.toolbar-group {{ border-right: 1px solid {border}; padding-right: 6px; }}
scrollbar slider {{ background: {t.raised_bg}; border-radius: 0; }}
"""
