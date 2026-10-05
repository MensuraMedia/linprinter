"""
Main Window
The 2026 redesign shell (lintheme, Graphite Night): a header bar with the brand,
the current page, the printer status chip and the menu; the navigation rail;
the page stack.

The status chip shows the chosen printer in the shared vocabulary (Ready ·
Busy · Needs you · Can't reach) on every page and opens the Printer page.
Keyboard: Alt+1…4 pages, Ctrl+P print, Ctrl+O open, F5 check the printer again.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from lintheme import apply, tokens  # noqa: E402
from modules.manager_status import chip_key, user_must_act  # noqa: E402
from lintheme.gtk3 import components as ui  # noqa: E402
from ui import app_css  # noqa: E402
from ui.content_area import ContentArea  # noqa: E402
from ui.sidebar import NAV_ITEMS, Sidebar  # noqa: E402
from utils.util_icons import set_icon_color  # noqa: E402
from utils.util_paths import resource  # noqa: E402

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
TITLES = {page_id: label for label, page_id, _i, _b in NAV_ITEMS}


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
        """Header bar, rail and content area; registers itself as dialog parent"""
        super().__init__(title="LinPrinter")
        self.ctx = ctx
        ctx.window = self
        apply.install(self)
        app_css.install()
        set_icon_color(tokens.COLOR["text"])
        self.set_default_size(1280, 860)
        self.set_size_request(tokens.LAYOUT["min_width"], tokens.LAYOUT["min_height"])
        self.set_position(Gtk.WindowPosition.CENTER)
        set_app_icon(self)

        header = ui.css(Gtk.HeaderBar(), "lt-header")
        header.set_show_close_button(True)
        brand = Gtk.Box(spacing=10)
        brand.pack_start(ui.icon("printer", 24, tokens.COLOR["accent"]), False, False, 0)
        brand.pack_start(ui.text("LinPrinter", "lt-brand"), False, False, 0)
        self.crumb = ui.text("", "lt-crumb")
        brand.pack_start(self.crumb, False, False, 0)
        header.pack_start(brand)
        self.menu_button = self._menu()
        header.pack_end(self.menu_button)
        self.chip = ui.StatusChip("", "none", on_click=lambda: ctx.nav.navigate_to("printer"))
        header.pack_end(self.chip)
        self.set_titlebar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(box)
        self.sidebar = Sidebar(ctx.nav)  # registers its callback before pages navigate
        box.pack_start(self.sidebar, False, False, 0)
        box.pack_start(ContentArea(ctx), True, True, 0)
        ctx.nav.on_navigate(lambda pid: self.crumb.set_text("/ " + TITLES.get(pid, "")))

        self._printer = None
        self._printing = False
        ctx.on("printer-selected", self._on_printer)
        ctx.on("printer-status", self._on_status)
        ctx.on("printing", self._on_printing)
        self.connect("key-press-event", self._on_key)
        self.connect("size-allocate", self._on_size)
        self._compact = None

    # -- status chip ---------------------------------------------------------------
    def _on_printer(self, printer):
        self._printer = printer
        if printer is None:
            self.chip.set_status("", "none")
        elif not printer.methods:
            self.chip.set_status(printer.name, "error", printer.hint)
        else:
            self.chip.set_status(printer.name, "busy", "Checking the printer…")  # until it answers

    def _on_status(self, printer, status):
        if printer is not self._printer:
            return
        level, message, state, reasons = status[0], status[1], status[2], status[3]
        key = chip_key(level, state, reasons)
        if self._printing and not (key == "attention" and user_must_act(reasons)):
            # the job reports while it runs; only "Needs you" (paper out…) breaks in, and goes again
            self.chip.set_status(printer.name, "busy", "Printing")
            return
        self.chip.set_status(printer.name, key, message)

    def _on_printing(self, busy):
        """A job started or finished: chip and Activity badge"""
        self._printing = busy
        name = self._printer.name if self._printer else ""
        if busy:
            self.chip.set_status(name, "busy", "Printing")
            self.sidebar.set_badge("activity", 1, "1 job printing")
        else:
            self.sidebar.set_badge("activity", None)

    # -- header menu -----------------------------------------------------------------
    def _menu(self):
        button = ui.css(Gtk.MenuButton(), "lt-icon-btn")
        button.add(ui.icon("dots-three", 20))
        button.set_tooltip_text("Keyboard shortcuts, About")
        ui.name(button, "Menu: keyboard shortcuts and About")
        pop = Gtk.Popover()
        col = ui.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2), "lt-printer-menu")
        for label, action in (
            ("Keyboard shortcuts", self.show_shortcuts),
            ("About LinPrinter", lambda: self._settings_section("about")),
        ):
            item = Gtk.ModelButton(text=label)
            item.connect("clicked", lambda _b, a=action: a())
            col.pack_start(item, False, False, 0)
        col.show_all()
        pop.add(col)
        button.set_popover(pop)
        return button

    def _settings_section(self, section):
        self.ctx.nav.navigate_to("settings")
        page = self.ctx.nav.get_page_widget("settings")
        if hasattr(page, "show_section"):
            page.show_section(section)

    def show_shortcuts(self):
        """The keyboard shortcuts, in a small dialog"""
        dialog = Gtk.Dialog(title="Keyboard shortcuts", transient_for=self, modal=True)
        ui.css(dialog, "lt-root", "lt-dialog")
        area = dialog.get_content_area()
        area.set_border_width(20)
        area.set_spacing(10)
        area.pack_start(ui.text("Keyboard shortcuts", "lt-heading"), False, False, 0)
        grid = Gtk.Grid(column_spacing=16, row_spacing=8)
        for i, (keys, what) in enumerate(
            (
                ("Ctrl+O", "Open a document"),
                ("Ctrl+P", "Print"),
                ("F5", "Check the printer again"),
                ("Alt+1 … Alt+4", "Print, Activity, Printer, Settings"),
                ("Ctrl + / Ctrl −", "Zoom the preview"),
                ("Ctrl+0", "Fit the preview"),
                ("Esc", "Close a dialog"),
            )
        ):
            grid.attach(ui.text(keys, "lt-kbd"), 0, i, 1, 1)
            grid.attach(ui.text(what), 1, i, 1, 1)
        area.pack_start(grid, False, False, 0)
        close = ui.css(dialog.add_button("Close", Gtk.ResponseType.CLOSE), "lt-btn")
        close.grab_focus()
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    # -- keyboard and layout ------------------------------------------------------------
    def _on_key(self, _w, event):
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        nav = self.ctx.nav
        if state == Gdk.ModifierType.MOD1_MASK:
            n = event.keyval - Gdk.KEY_1
            if 0 <= n < len(NAV_ITEMS):
                nav.navigate_to(NAV_ITEMS[n][1])
                return True
        print_page = nav.get_page_widget("print")
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_p, Gdk.KEY_P):
            nav.navigate_to("print")
            print_page.on_print()
            return True
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_o, Gdk.KEY_O):
            nav.navigate_to("print")
            print_page.choose_document()
            return True
        if event.keyval == Gdk.KEY_F5:
            self.ctx.emit("request-printer-refresh")
            return True
        return False

    def _on_size(self, _w, alloc):
        compact = alloc.width < tokens.LAYOUT["two_pane"]
        if compact != self._compact:
            self._compact = compact
            self.sidebar.set_compact(compact)
            self.ctx.emit("layout", "compact" if compact else "wide")
