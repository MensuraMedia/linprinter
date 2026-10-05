"""
Sidebar (navigation rail)
The four destinations of the 2026 redesign, as lintheme's NavRail: Print,
Activity, Printer, and Settings at the bottom. Adding a page = one line here
and one line in ui/content_area.PAGES.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from lintheme.gtk3.components import NavRail  # noqa: E402

# (label, page id, icon, at the bottom)
NAV_ITEMS = [
    ("Print", "print", "printer", False),
    ("Activity", "activity", "clock-counter-clockwise", False),
    ("Printer", "printer", "usb", False),
    ("Settings", "settings", "gear-six", True),
]


class Sidebar(NavRail):
    """The rail, wired to the navigation manager"""

    def __init__(self, nav):
        super().__init__(on_select=nav.navigate_to)
        self.nav = nav
        for label, page_id, icon_name, bottom in NAV_ITEMS:
            self.add_item(page_id, label, icon_name, bottom=bottom)
        nav.on_navigate(self.set_active)
        self.set_vexpand(True)
        self.set_valign(Gtk.Align.FILL)
