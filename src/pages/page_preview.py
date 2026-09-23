"""
Preview Page
The chosen pages exactly as they will print: paper size, fitting (landscape
pages turned to portrait), colour or black & white, and the margins the
printer can't print on (shaded). Zoom, page navigation and 1 or 2 rows of
thumbnails, as in LinScanner's Preview. Re-rendered when the options change.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from modules.manager_render import RenderError  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from ui.components.component_preview import PagePreview  # noqa: E402
from ui.components.component_segmented import SegmentedControl  # noqa: E402
from utils.util_icons import icon_button  # noqa: E402

PREVIEW_DPI = 140  # previews are rendered at this resolution, so zooming in shows real detail


class PreviewPage(BasePage):
    """Print preview"""

    def build_content(self):
        """Toolbar (navigation, zoom, thumbnails, Print), preview and status"""
        self.add_title("Preview", "The pages as they will print. Change the options on the Print page.")
        bar = Gtk.Box(spacing=4)
        nav = Gtk.Box(spacing=4)
        nav.get_style_context().add_class("toolbar-group")
        for icon, tip, action in (
            ("caret-double-left", "First page (Home)", lambda: self.preview.select(0)),
            ("caret-left", "Previous page (Page Up)", lambda: self.step(-1)),
            ("caret-right", "Next page (Page Down)", lambda: self.step(1)),
            ("caret-double-right", "Last page (End)", lambda: self.preview.select(len(self.pages) - 1)),
        ):
            nav.pack_start(icon_button(icon, tip, action), False, False, 0)
        bar.pack_start(nav, False, False, 0)
        zoom = Gtk.Box(spacing=4)
        zoom.get_style_context().add_class("toolbar-group")
        zoom.pack_start(
            icon_button("magnifying-glass-minus", "Zoom out (Ctrl + wheel)", lambda: self.preview.zoom_out()),
            False,
            False,
            0,
        )
        self.zoom_label = Gtk.Label(label="Fit")
        self.zoom_label.set_width_chars(5)
        zoom.pack_start(self.zoom_label, False, False, 0)
        zoom.pack_start(
            icon_button(
                "magnifying-glass-plus",
                "Zoom in (Ctrl + wheel); drag the page to move around",
                lambda: self.preview.zoom_in(),
            ),
            False,
            False,
            0,
        )
        zoom.pack_start(
            icon_button("arrows-in", "Fit the whole page", lambda: self.preview.zoom_fit()), False, False, 0
        )
        zoom.pack_start(
            icon_button(
                "arrows-out-line-horizontal", "Fit the page width", lambda: self.preview.zoom_fit_width()
            ),
            False,
            False,
            0,
        )
        bar.pack_start(zoom, False, False, 6)
        self.spinner = Gtk.Spinner()
        bar.pack_start(self.spinner, False, False, 0)
        self.info = self.label("", "muted")
        self.info.set_ellipsize(3)
        bar.pack_start(self.info, True, True, 6)
        self.print_btn = Gtk.Button(label="Print")
        self.print_btn.get_style_context().add_class("primary-pill")
        self.print_btn.connect("clicked", lambda *_: self.ctx.nav.get_page_widget("print").on_print())
        bar.pack_end(self.print_btn, False, False, 0)
        rows = self.ctx.settings.get("thumbnail_rows")
        self.rows = SegmentedControl(
            [("1", "1 row"), ("2", "2 rows")], active=str(rows), on_changed=self.on_rows
        )
        bar.pack_end(self.rows, False, False, 6)
        self.pack_start(bar, False, False, 0)

        self.pages = []
        self.page_numbers = []
        self.preview = PagePreview(
            on_select=self.on_select,
            cache_dir=os.path.join(self.ctx.printing.session_dir, "display"),
            rows=rows,
            on_zoom=lambda z: self.zoom_label.set_text("Fit" if abs(z - 1) < 1e-6 else f"{z * 100:.0f}%"),
            label_for=lambda i, page: f"Page {self.page_numbers[i]}" if i < len(self.page_numbers) else "",
        )
        self.preview.empty.set_text("Open a document on the Print page to see it here.")
        self.pack_start(self.preview, True, True, 0)
        self.status = self.label("", "muted", wrap=True)
        self.pack_start(self.status, False, False, 0)
        self._pending = None
        self.ctx.on("ticket-changed", self.schedule)
        self.ctx.on("document-changed", lambda *_: self.schedule())

    def on_rows(self, key):
        """1 or 2 rows of thumbnails (remembered)"""
        self.ctx.settings.set("thumbnail_rows", int(key))
        self.preview.set_rows(int(key))

    def step(self, delta):
        """Previous / next page"""
        self.preview.select(self.preview.selected + delta)

    def on_select(self, index):
        """Remember the page shown (Pages → Current prints it)"""
        if 0 <= index < len(self.page_numbers):
            self.ctx.preview_page = self.page_numbers[index]
            self.update_info()

    def update_info(self):
        """ "Page 2 (of 5 printed) · A4 · Black & White" """
        i = self.preview.selected
        if not self.pages or i < 0:
            self.info.set_text("")
            return
        page = self.ctx.nav.get_page_widget("print")
        summary = page.summary.get_text().replace("Will print: ", "")
        self.info.set_text(f"Page {self.page_numbers[i]} ({i + 1} of {len(self.pages)} to print) · {summary}")

    def schedule(self, *_):
        """Re-render shortly after the options change (only while this page is shown)"""
        if self.ctx.nav.get_current_page() != "preview":
            return
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(350, self.render)

    def render(self):
        """Render the chosen pages in the background"""
        self._pending = None
        pm = self.ctx.printing
        print_page = self.ctx.nav.get_page_widget("print")
        if not pm.document or print_page.printer is None:
            self.preview.set_pages([])
            self.info.set_text("")
            return False
        try:
            pages = print_page.selected_pages()
        except RenderError as e:
            self.status.set_text(str(e))
            return False
        ticket = print_page.ticket()
        self.spinner.start()
        self.status.set_text("")

        def done(images):
            self.spinner.stop()
            self.page_numbers = pages
            self.pages = [
                {"path": p, "rotation": 0, "dpi": PREVIEW_DPI, "mode": ticket["color"]} for p in images
            ]
            self.preview.set_pages(self.pages, selected=0)
            self.update_info()

        def failed(message):
            self.spinner.stop()
            self.status.set_text(message)

        pm.preview_async(ticket, pages, done, failed)
        return False

    def on_shown(self):
        """Render when the page is opened"""
        self.schedule()
