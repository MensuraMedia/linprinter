"""
The dashboard shell for GTK 3 Lin* apps: header bar with the device status chip,
navigation rail, stacked pages. Every Lin* app is this shell plus its pages.

    win = DashboardWindow(app, "LinPrinter", "printer")
    win.add_page("print", "Print", "printer", PrintPage())
    win.add_page("activity", "Activity", "clock-counter-clockwise", ActivityPage())
    win.add_page("device", "Printer", "usb", DevicePage())
    win.add_page("settings", "Settings", "gear-six", SettingsPage(), bottom=True)
    win.chip.set_status("Canon TR150", "ok")
    win.show_all()

Keyboard: Alt+1…Alt+9 switch pages in rail order. Below LAYOUT['two_pane'] px the
rail goes compact and `on_layout(mode)` is called with 'wide' or 'compact', so a page
can fold its second pane (the Print page folds its preview).
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from lintheme import apply, tokens  # noqa: E402
from lintheme.gtk3.components import NavRail, StatusChip, css, icon, icon_button, text  # noqa: E402


class DashboardWindow(Gtk.ApplicationWindow):
    def __init__(self, application, app_name, app_icon="printer", on_chip=None, on_menu=None):
        super().__init__(application=application, title=app_name)
        self.set_default_size(1280, 860)
        self.set_size_request(tokens.LAYOUT["min_width"], tokens.LAYOUT["min_height"])
        apply.install(self)
        self._pages, self._order, self._listeners = {}, [], []
        self._mode = None

        header = css(Gtk.HeaderBar(), "lt-header")
        header.set_show_close_button(True)
        brand = Gtk.Box(spacing=10)
        brand.pack_start(icon(app_icon, 24, tokens.COLOR["accent"]), False, False, 0)
        brand.pack_start(text(app_name, "lt-brand"), False, False, 0)
        self._crumb = text("", "lt-crumb")
        brand.pack_start(self._crumb, False, False, 0)
        header.pack_start(brand)
        menu = icon_button("dots-three", "Main menu: shortcuts, help, about", on_menu)
        header.pack_end(menu)
        self.chip = StatusChip(
            on_click=on_chip or (lambda: self.show_page(self._order[min(2, len(self._order) - 1)]))
        )
        header.pack_end(self.chip)
        self.set_titlebar(header)

        body = Gtk.Box()
        self.rail = NavRail(on_select=self.show_page)
        body.pack_start(self.rail, False, False, 0)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(tokens.MOTION["panel_ms"] if apply.animations_enabled() else 0)
        body.pack_start(self.stack, True, True, 0)
        self.add(body)

        self.connect("key-press-event", self._on_key)
        self.connect("size-allocate", self._on_size)

    # -- pages
    def add_page(self, page_id, label, icon_name, widget, bottom=False, crumb=None):
        self._pages[page_id] = (label, crumb or label)
        self._order.append(page_id)
        self.rail.add_item(page_id, label, icon_name, bottom=bottom)
        self.stack.add_named(widget, page_id)
        if len(self._order) == 1:
            self.show_page(page_id)
        return widget

    def show_page(self, page_id):
        self.stack.set_visible_child_name(page_id)
        self.rail.set_active(page_id)
        self._crumb.set_text("/ " + self._pages[page_id][1])

    def current_page(self):
        return self.stack.get_visible_child_name()

    # -- layout
    def on_layout(self, callback):
        """callback(mode): 'wide' or 'compact', now and on every change"""
        self._listeners.append(callback)
        if self._mode:
            callback(self._mode)

    def _on_size(self, _w, alloc):
        mode = "wide" if alloc.width >= tokens.LAYOUT["two_pane"] else "compact"
        if mode != self._mode:
            self._mode = mode
            self.rail.set_compact(mode == "compact")
            for cb in self._listeners:
                cb(mode)

    # -- keyboard
    def _on_key(self, _w, event):
        if event.state & Gdk.ModifierType.MOD1_MASK:
            n = event.keyval - Gdk.KEY_1
            if 0 <= n < len(self._order):
                self.show_page(self._order[n])
                return True
        return False
