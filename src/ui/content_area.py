"""
Content Area Component
Stack of pages. Pages are registered from a list, so adding a page is a
one-line change (plus one line in ui/sidebar.NAV_ITEMS).
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from pages.page_activity import ActivityPage  # noqa: E402
from pages.page_print import PrintPage  # noqa: E402
from pages.page_printer import PrinterPage  # noqa: E402
from pages.page_settings import SettingsPage  # noqa: E402

# (page id, class, wrap in a vertical scroller)
PAGES = [
    ("print", PrintPage, False),  # its own scrolling options column; the action bar stays put
    ("activity", ActivityPage, True),
    ("printer", PrinterPage, True),
    ("settings", SettingsPage, True),
]


class ContentArea(Gtk.Box):
    """Page stack registered with the navigation manager"""

    def __init__(self, ctx):
        """Create every page in PAGES, add to the stack, register for navigation"""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        # size to the visible page only, so the window can be made small and snapped to screen halves/quarters
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        self.pack_start(self.stack, True, True, 0)
        ctx.nav.set_page_stack(self.stack)

        for page_id, page_class, scrolled in PAGES:
            page = page_class(ctx)
            widget = page
            if scrolled:
                widget = Gtk.ScrolledWindow()
                widget.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                widget.add(page)
            self.stack.add_named(widget, page_id)
            ctx.nav.register_page(page_id, page)
        ctx.nav.on_navigate(lambda pid: ctx.nav.get_page_widget(pid).on_shown())
