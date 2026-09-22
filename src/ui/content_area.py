"""
Content Area Component
Stack of pages, each in its own ScrolledWindow (keeps individual scroll states).
Pages are registered from a list, so adding a page is a one-line change.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from pages.page_about import AboutPage  # noqa: E402
from pages.page_preview import PreviewPage  # noqa: E402
from pages.page_print import PrintPage  # noqa: E402
from pages.page_printers import PrintersPage  # noqa: E402
from pages.page_queue import QueuePage  # noqa: E402
from pages.page_recent import RecentPage  # noqa: E402
from pages.page_settings import SettingsPage  # noqa: E402

PAGES = [
    ("print", PrintPage, True),
    ("preview", PreviewPage, True),  # scrolls only when the window is smaller than the page
    ("queue", QueuePage, False),  # has its own scrolling table
    ("recent", RecentPage, False),  # has its own scrolling table
    ("printers", PrintersPage, True),
    ("settings", SettingsPage, True),
    ("about", AboutPage, True),
]


class ContentArea(Gtk.Box):
    """Page stack registered with the navigation manager"""

    def __init__(self, ctx):
        """Create every page in PAGES, add to the stack, register for navigation"""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("content-area")
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
                widget.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
                widget.add(page)
            self.stack.add_named(widget, page_id)
            ctx.nav.register_page(page_id, page)
        ctx.nav.on_navigate(lambda pid: ctx.nav.get_page_widget(pid).on_shown())
