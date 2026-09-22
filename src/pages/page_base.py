"""
Base Page Class
Base class for all pages (from gtk-python-dashboard-starter), extended with
the app context and card helpers.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from config.config_layout import Layout  # noqa: E402


class BasePage(Gtk.Box):
    """All pages inherit from this class and implement build_content()"""

    def __init__(self, ctx, spacing=None, margin=None):
        """Apply margins/spacing, keep the app context, then build_content()"""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=spacing or Layout.dimensions.CONTENT_SPACING,
        )
        self.ctx = ctx
        m = margin or Layout.dimensions.CONTENT_MARGIN
        for setter in (
            self.set_margin_start,
            self.set_margin_end,
            self.set_margin_top,
            self.set_margin_bottom,
        ):
            setter(m)
        self.build_content()

    def build_content(self):
        """Create the page's widgets (subclasses must implement)"""
        raise NotImplementedError("Subclasses must implement build_content()")

    def on_shown(self):
        """Called by the navigation manager when the page becomes visible"""

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def label(text, css=None, xalign=0, wrap=False, selectable=False):
        """Create a label with optional CSS classes, alignment and wrapping"""
        lbl = Gtk.Label(label=text)
        lbl.set_xalign(xalign)
        lbl.set_line_wrap(wrap)
        lbl.set_selectable(selectable)
        if css:
            for c in css.split():
                lbl.get_style_context().add_class(c)
        return lbl

    def add_title(self, text, subtitle=None):
        """Add the page title and an optional muted subtitle"""
        self.pack_start(self.label(text, "page-title"), False, False, 0)
        if subtitle:
            self.pack_start(self.label(subtitle, "muted", wrap=True), False, False, 0)

    def add_paragraph(self, text):
        """Add wrapped secondary text"""
        lbl = self.label(text, "secondary", wrap=True)
        self.pack_start(lbl, False, False, 0)
        return lbl

    def make_card(self, title=None):
        """A rounded card; returns (card, inner vertical box)"""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=Layout.spacing.MEDIUM)
        card.get_style_context().add_class("card")
        if title:
            card.pack_start(self.label(title, "card-title"), False, False, 0)
        return card, card

    def add_card(self, title=None, expand=False):
        """Add a card to the page and return its inner box"""
        card, inner = self.make_card(title)
        self.pack_start(card, expand, expand, 0)
        return inner

    @staticmethod
    def form_row(label_text, widget):
        """Label on the left, widget on the right"""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=Layout.spacing.LARGE)
        lbl = BasePage.label(label_text, "secondary")
        lbl.set_size_request(130, -1)
        row.pack_start(lbl, False, False, 0)
        row.pack_start(widget, True, True, 0)
        return row
