"""
Main Window
Sidebar + content area (layout from gtk-python-dashboard-starter).
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from config.config_layout import Layout  # noqa: E402
from ui.content_area import ContentArea  # noqa: E402
from ui.sidebar import Sidebar  # noqa: E402
from utils.util_paths import resource  # noqa: E402


ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def set_app_icon(window=None):
    """The LinPrinter icon in several sizes, for every window (panel, Alt+Tab, dialogs)"""
    from gi.repository import GdkPixbuf, GLib

    try:
        full = GdkPixbuf.Pixbuf.new_from_file(resource("images", "logo.png"))
    except GLib.Error:  # missing icon is cosmetic
        return
    icons = [full.scale_simple(s, s, GdkPixbuf.InterpType.BILINEAR) for s in ICON_SIZES]
    Gtk.Window.set_default_icon_list(icons)
    if window is not None:
        window.set_icon_list(icons)


class AppWindow(Gtk.Window):
    """Main application window"""

    def __init__(self, ctx):
        """Window with sidebar and content area; registers itself as dialog parent"""
        super().__init__(title="LinPrinter")
        ctx.window = self
        self.set_default_size(Layout.dimensions.WINDOW_DEFAULT_WIDTH, Layout.dimensions.WINDOW_DEFAULT_HEIGHT)
        self.set_position(Gtk.WindowPosition.CENTER)
        set_app_icon(self)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(box)
        self.sidebar = Sidebar(ctx.nav)  # registers its callback before pages navigate
        box.pack_start(self.sidebar, False, False, 0)
        box.pack_start(ContentArea(ctx), True, True, 0)
