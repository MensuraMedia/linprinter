"""
App CSS
LinPrinter's own classes on top of lintheme (Graphite Night): the few class
names the preview component and the optional features still use. Colours come
only from lintheme.tokens, so there is still exactly one theme.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from lintheme import tokens  # noqa: E402

C = tokens.COLOR


def css():
    """The stylesheet text"""
    return f"""
.muted, .secondary, .info-key, .page-subtitle {{ color: {C['text_muted']}; }}
.page-title {{ font-size: 20px; font-weight: 500; }}
.card {{ background-color: {C['surface']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 14px 16px; }}
.card-title {{ font-size: 16px; font-weight: 500; }}
.status-ok {{ color: {C['ok']}; }}
.status-busy {{ color: {C['attention']}; }}
.status-error {{ color: {C['error']}; }}
.toolbar-group {{ border: 1px solid {C['border_strong']}; border-radius: 6px; padding: 0 2px; }}
.icon-button, .icon-flat {{
  background-image: none; background-color: transparent; border: none; box-shadow: none;
  min-width: 32px; min-height: 32px; border-radius: 6px; color: {C['text']};
}}
.icon-button:hover, .icon-flat:hover {{ background-color: {C['surface_hover']}; }}
.preview-frame {{ background-color: {C['bg']}; border: none; }}
.lt-preview-pane scrolledwindow, .lt-preview-pane viewport {{ background-color: {C['bg']}; }}
.thumb {{
  background-image: none; background-color: {C['surface']}; border: 1px solid {C['border']};
  border-radius: 4px; padding: 3px; box-shadow: none;
}}
.thumb.selected {{ border: 2px solid {C['accent']}; background-color: {C['accent_soft']}; }}
.thumb-label {{ color: {C['text_muted']}; font-size: 12px; }}
.lt-tab {{
  background-image: none; background-color: transparent; border: none; box-shadow: none;
  min-height: 40px; padding: 0 14px; border-radius: 6px; color: {C['text_muted']};
}}
.lt-tab label {{ font-weight: 400; }}
.lt-tab:hover {{ background-color: {C['surface']}; color: {C['text']}; }}
.lt-tab:checked {{ background-color: {C['accent_soft']}; color: {C['text']}; box-shadow: inset 0 0 0 2px {C['accent']}; }}
.lt-tab:checked label {{ font-weight: 500; }}
.lt-printer-menu {{ padding: 8px; }}
.lt-printer-menu button {{
  background-image: none; background-color: transparent; border: none; box-shadow: none;
  min-height: 36px; padding: 0 10px; color: {C['text']};
}}
.lt-printer-menu button:hover {{ background-color: {C['surface_hover']}; }}
.lt-printer-menu radiobutton {{ min-height: 36px; padding: 0 6px; }}
"""


def install():
    """Load the app CSS above lintheme's"""
    provider = Gtk.CssProvider()
    provider.load_from_data(css().encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1
    )
    return provider
