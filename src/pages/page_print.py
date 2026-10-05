"""
Print Page (2026 redesign)
The home view: options on the left in four cards (Printer, Document, Paper,
Output, with "More options"), the live preview on the right, and a sticky
action bar with the summary and the one main action, Print.

Behaviour kept from 0.2.x: the remembered printer is reached first, status is
checked every few seconds, a quiet search runs when the printer stops
answering, only options the printer reports are offered, page selection and
fitting are done by LinPrinter, and features hook in (profiles add a row to
More options; ink alerts are asked before printing).

Status follows the shared vocabulary (Ready · Busy · Needs you · Can't reach)
with its fix in place; Print is disabled with the reason beside it; nothing
is ever re-sent another way without telling the user.
"""

import logging
import os
import re
import time
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from backends.backend_base import type_label  # noqa: E402
from config.config_print import (  # noqa: E402
    COLOR_MODES,
    PAGE_CHOICES,
    PAGES_MAIN,
    PAGES_WHICH,
    PDF_PRINTER_ID,
    QUALITIES,
    SCALING,
    STATUS_EVERY,
)
from backends import usb_link  # noqa: E402
from lintheme import status as lt_status  # noqa: E402
from lintheme import tokens  # noqa: E402
from lintheme.gtk3 import components as ui  # noqa: E402
from modules.manager_documents import add_recent  # noqa: E402
from modules.manager_print import ticket_choices  # noqa: E402
from modules.manager_render import OPENABLE, RenderError, select_pages  # noqa: E402
from modules.manager_status import needs_you_words, user_must_act  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from modules.manager_status import chip_key  # noqa: E402
from ui.components.component_preview import PagePreview  # noqa: E402
from ui.components.component_segmented import SegmentedControl  # noqa: E402
from utils.util_files import show_in_file_manager, tilde  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

PREVIEW_DPI = 140  # previews are rendered at this resolution, so zooming in shows real detail
NO_DOC = "No document yet"


class PrintPage(BasePage):
    """Printer, document, options, live preview and the Print bar"""

    def __init__(self, ctx):
        super().__init__(ctx, spacing=1, margin=1)
        for setter in (
            self.set_margin_start,
            self.set_margin_end,
            self.set_margin_top,
            self.set_margin_bottom,
        ):
            setter(0)
        self.set_spacing(0)

    def build_content(self):
        self.printers = []
        self.printer = None
        self.last_status = None
        self.misses = 0  # failed status checks in a row (quiet re-search)
        self.last_reconnect = 0.0
        self.power_state = "none"  # ok | warn | error | none (tests and tools read it)
        self._loading = False
        self._pulse = None
        self._started = 0.0
        self._preview_pending = None
        self.page_numbers = []

        panes = Gtk.Box()
        self.pack_start(panes, True, True, 0)

        # -- left: the options column (scrolls; the action bar stays put)
        self.options = ui.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), "lt-pane")
        self.options.set_size_request(tokens.LAYOUT["options_max"], -1)
        self.notice = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)  # print results and errors
        self.notice.set_no_show_all(True)
        self.options.pack_start(self.notice, False, False, 0)
        self.options.pack_start(self._printer_card(), False, False, 0)
        self.options.pack_start(self._document_card(), False, False, 0)
        self.options.pack_start(self._paper_card(), False, False, 0)
        self.options.pack_start(self._output_card(), False, False, 0)
        self.compact_preview = ui.Card("Preview")
        self.compact_preview.add_row(
            ui.text("At this window size the preview opens in place of the options.", "lt-muted", wrap=True)
        )
        show = ui.button("Show preview", lambda: self.set_preview_mode(True), small=True)
        show.set_halign(Gtk.Align.START)
        self.compact_preview.add_row(show)
        self.compact_preview.show_all()
        self.compact_preview.set_no_show_all(True)
        self.compact_preview.hide()
        self.options.pack_start(self.compact_preview, False, False, 0)
        self.left = ui.scrolled(self.options)
        self.left.set_propagate_natural_width(
            False
        )  # a fixed column, as in the mockup: banners wrap inside it
        self.left.set_min_content_width(tokens.LAYOUT["options_max"])
        self.left.set_hexpand(False)  # explicit: a child's hexpand must not widen the column (layout jumps)
        panes.pack_start(self.left, False, False, 0)

        # -- right: the live preview
        right = self._preview_pane()
        right.set_hexpand(True)
        panes.pack_start(right, True, True, 0)

        # -- the action bar
        self.bar = ui.ActionBar()
        self.why_not = ui.text("", "lt-muted")
        self.cancel_btn = ui.button("Cancel print", self.on_cancel, kind="danger")
        self.cancel_btn.set_no_show_all(True)
        self.secondary_btn = ui.button("", None)
        self.secondary_btn.set_no_show_all(True)
        self._secondary_action = None
        self.secondary_btn.connect("clicked", lambda *_: self._secondary_action and self._secondary_action())
        self.print_btn = ui.with_shortcut(ui.button("Print", kind="primary", big=True), "Ctrl+P")
        self.print_btn.connect("clicked", lambda *_: self.on_print())
        ui.name(self.print_btn, "Print")
        for w in (self.why_not, self.cancel_btn, self.secondary_btn, self.print_btn):
            self.bar.add_action(w)
        self.pack_start(self.bar, False, False, 0)

        self.drag_dest_set(
            Gtk.DestDefaults.ALL, [Gtk.TargetEntry.new("text/uri-list", 0, 0)], Gdk.DragAction.COPY
        )
        self.connect("drag-data-received", self.on_drop)
        if self.ctx.features:
            self.ctx.features.extend("extend_print_page", self)
        self.ctx.on("request-printer-refresh", self.refresh_printers)
        self.ctx.on("open-document", self.open_document)
        self.ctx.on("ticket-changed", self.schedule_preview)
        self.ctx.on("layout", self.on_layout)
        self.set_busy(True)
        self.update_summary()
        GLib.idle_add(self.startup)
        GLib.timeout_add_seconds(STATUS_EVERY, self.poll_status)

    # -- cards -------------------------------------------------------------------------
    def _card_head(self, title, extra=None):
        head = Gtk.Box(spacing=8)
        head.pack_start(ui.text(title, "lt-heading"), True, True, 0)
        if extra is not None:
            head.pack_end(extra, False, False, 0)
        return head

    def _printer_card(self):
        card = ui.Card()
        self.change_btn = ui.css(Gtk.MenuButton(), "lt-link")
        self.change_btn.add(Gtk.Label(label="Change"))
        ui.name(self.change_btn, "Change printer")
        self.change_btn.set_tooltip_text("Choose another printer, Print to PDF, or search again")
        self.printer_menu = Gtk.Popover()
        self.change_btn.set_popover(self.printer_menu)
        card.add_row(self._card_head("Printer", self.change_btn))
        row = Gtk.Box(spacing=12)
        self.printer_tile = ui.icon_tile("printer")
        row.pack_start(self.printer_tile, False, False, 0)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.printer_name = ui.text("Looking for printers…", "lt-strong")
        info.pack_start(self.printer_name, False, False, 0)
        self.status_line = Gtk.Box(spacing=6)
        info.pack_start(self.status_line, False, False, 0)
        row.pack_start(info, True, True, 0)
        card.add_row(row)
        self.printer_banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_row(self.printer_banner)
        self._set_status_line("none", "Checking…")
        return card

    def _document_card(self):
        card = ui.Card()
        self.replace_btn = ui.button("Replace…", self.choose_document, kind="link")
        self.replace_btn.set_no_show_all(True)
        card.add_row(self._card_head("Document", self.replace_btn))
        self.doc_stack = Gtk.Stack()
        self.doc_stack.set_vhomogeneous(False)
        drop = ui.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), "lt-dropzone")
        drop_icon = ui.icon("upload-simple", 28, tokens.COLOR["text_muted"])
        drop.pack_start(drop_icon, False, False, 0)
        self.doc_hint = ui.text("Drop a PDF, picture or text file here", xalign=0.5)
        drop.pack_start(self.doc_hint, False, False, 0)
        self.open_btn = open_btn = ui.with_shortcut(
            ui.button("Open…", self.choose_document, kind="primary", small=True), "Ctrl+O"
        )
        open_btn.set_halign(Gtk.Align.CENTER)
        ui.name(open_btn, "Open a document")
        drop.pack_start(open_btn, False, False, 0)
        drop.show_all()
        self.doc_stack.add_named(drop, "empty")
        doc_row = Gtk.Box(spacing=12)
        doc_row.pack_start(ui.icon_tile("file-text"), False, False, 0)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.doc_name = ui.text("", "lt-strong")
        self.doc_name.set_ellipsize(3)
        self.doc_detail = ui.text("", "lt-muted")
        words.pack_start(self.doc_name, False, False, 0)
        words.pack_start(self.doc_detail, False, False, 0)
        doc_row.pack_start(words, True, True, 0)
        doc_row.show_all()
        self.doc_stack.add_named(doc_row, "doc")
        card.add_row(self.doc_stack)
        return card

    def _paper_card(self):
        card = ui.Card("Paper")
        self.size_combo = ui.no_wheel(ui.css(Gtk.ComboBoxText(), "lt-select"))  # the wheel scrolls the page
        self.size_combo.set_row_separator_func(lambda model, it: (model[it][1] or "").startswith("-"))
        self.size_combo.connect("changed", lambda c: self.on_size_or_type())
        ui.name(self.size_combo, "Paper size")
        card.add_row(ui.field_row("Size", self.size_combo))
        self.type_combo = ui.no_wheel(ui.css(Gtk.ComboBoxText(), "lt-select"))
        self.type_combo.connect("changed", lambda c: self.on_size_or_type())
        ui.name(self.type_combo, "Paper type")
        self.type_row = ui.field_row("Type", self.type_combo)
        card.add_row(self.type_row)
        self.borderless = Gtk.Switch(active=bool(self.ctx.settings.get("borderless")))
        self.borderless.set_valign(Gtk.Align.CENTER)
        self.borderless.connect("notify::active", lambda s, _p: self.remember("borderless", s.get_active()))
        ui.name(self.borderless, "Borderless")
        self.borderless_note = ui.text("", "lt-muted")
        card.add_row(ui.field_row("Borderless", ui.hbox(self.borderless, self.borderless_note)))
        return card

    def _output_card(self):
        card = ui.Card("Output")
        self.copies = ui.Stepper(
            1, 1, 99, on_change=lambda v: self.update_summary(), accessible_name="Copies"
        )
        # the hint sits under the label, so the stepper keeps the shared width (mockup: "up to 99")
        self.copies_hint = ui.text("up to 99", "lt-caption")
        self.copies.set_tooltip_text("Copies: up to 99")
        self._fill(self.copies, stepper=True)
        card.add_row(self._labelled_row("Copies", self.copies, self.copies_hint))
        self.color = SegmentedControl(
            list(COLOR_MODES.items()),
            active=self.ctx.settings.get("color_mode"),
            on_changed=lambda k: self.remember("color_mode", k),
        )
        ui.name(self.color, "Colour")
        self.color_row = self._uniform_row("Colour", self.color)
        card.add_row(self.color_row)
        self.quality = SegmentedControl(
            list(QUALITIES.items()),
            active=self.ctx.settings.get("quality"),
            on_changed=lambda k: self.remember("quality", k),
        )
        ui.name(self.quality, "Quality")
        self.quality_row = self._uniform_row("Quality", self.quality)
        card.add_row(self.quality_row)
        self.pages = SegmentedControl(
            [(k, PAGE_CHOICES[k]) for k in PAGES_MAIN], active="all", on_changed=self.on_pages_choice
        )
        ui.name(self.pages, "Pages")
        card.add_row(self._uniform_row("Pages", self.pages))
        self.range_entry = ui.entry("", "e.g. 2 or 1-3, 5", "Pages to print", width_chars=14)
        self.range_entry.set_tooltip_text("One page (2), a run (1-3), or both (1-3, 5, 8-10)")
        self.range_entry.connect("changed", lambda *_: self.update_summary())
        # the count sits under the label (as Copies' hint does), so the box spans the shared width
        self.range_hint = ui.text("", "lt-caption")
        self.range_hint.set_max_width_chars(12)  # never wider than the label column
        self.range_hint.set_ellipsize(3)
        self.range_row = self._labelled_row("Page list", self.range_entry, self.range_hint)
        self.range_row.show_all()  # children visible now; the row itself is shown/hidden later
        self.range_row.set_no_show_all(True)
        self.range_row.hide()
        card.add_row(self.range_row)

        # More options: which pages, fitting, and whatever features add (profiles)
        self.more = Gtk.Revealer()
        self.more.set_transition_duration(tokens.MOTION["panel_ms"])
        self.options_card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10
        )  # features add rows here
        self.options_card.pack_start(ui.css(Gtk.Box(), "lt-divider"), False, False, 0)
        self.which = SegmentedControl(
            [(k, PAGE_CHOICES[k]) for k in PAGES_WHICH],
            active="all",
            on_changed=lambda k: self.update_summary(),
        )
        ui.name(self.which, "Which pages")
        self.which_row = self._uniform_row("Which", self.which)
        self.options_card.pack_start(self.which_row, False, False, 0)
        self.scaling = SegmentedControl(
            list(SCALING.items()),
            active=self.ctx.settings.get("scaling"),
            on_changed=lambda k: self.remember("scaling", k),
        )
        ui.name(self.scaling, "Fit")
        self.options_card.pack_start(self._uniform_row("Fit", self.scaling), False, False, 0)
        self.more.add(self.options_card)
        card.add_row(self.more)
        self.more_btn = ui.button("More options: odd/even, fit, profiles", self.toggle_more, kind="link")
        self.more_btn.set_halign(Gtk.Align.START)
        self.more_btn.set_tooltip_text("Show or hide the less common options")
        card.add_row(self.more_btn)
        return card

    @staticmethod
    def _fill(control, stepper=False):
        """Make a segmented control (or the stepper) fill the field column with equal segments"""
        control.set_halign(Gtk.Align.FILL)  # SegmentedControl hugs its labels (START) by default
        if stepper:  # − and + stay compact; the value takes the rest (it is a value, not a choice)
            minus, value, plus = control.get_children()
            for b in (minus, plus):
                b.set_size_request(48, -1)
            control.child_set_property(value, "expand", True)
            control.child_set_property(value, "fill", True)
        else:
            control.set_homogeneous(True)
            for child in control.get_children():
                control.child_set_property(child, "expand", True)
                control.child_set_property(child, "fill", True)
        return control

    def _uniform_row(self, label, control):
        """A field row whose control fills the column, as the Paper selects do: every Output control
        has the same width and every segment its share of it"""
        row = ui.field_row(label, self._fill(control))
        row.child_set_property(control, "expand", True)
        row.child_set_property(control, "fill", True)
        return row

    @staticmethod
    def _labelled_row(label, control, caption):
        """A uniform row with a small caption under its label (the control keeps the full width)"""
        words = ui.vbox(ui.text(label, "lt-field-label"), caption, spacing=0)
        words.set_size_request(84, -1)
        words.set_valign(Gtk.Align.CENTER)
        row = Gtk.Box(spacing=12)
        row.pack_start(words, False, False, 0)
        control.set_halign(Gtk.Align.FILL)
        row.pack_start(control, True, True, 0)
        return row

    def form_row(self, label_text, widget):
        """Rows that features add to More options (profiles): the kit's field row"""
        return ui.field_row(label_text, widget)

    def toggle_more(self):
        """Show or hide More options (remembered)"""
        show = not self.more.get_reveal_child()
        self.more.set_reveal_child(show)
        self.more_btn.get_child().set_text(
            "Fewer options" if show else "More options: odd/even, fit, profiles"
        )
        self.more_btn.set_tooltip_text(
            "Hide the less common options" if show else "Show odd/even pages, fitting and profiles"
        )
        self.ctx.settings.set("more_options", show)

    def _preview_pane(self):
        pane = ui.css(
            Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12),
            "lt-pane",
            "lt-pane-divider",
            "lt-preview-pane",
        )
        head = Gtk.Box(spacing=12)
        self.back_btn = ui.button("Back to options", lambda: self.set_preview_mode(False), small=True)
        self.back_btn.set_no_show_all(True)
        head.pack_start(self.back_btn, False, False, 0)
        head.pack_start(ui.text("Preview", "lt-heading"), False, False, 0)
        self.preview_info = ui.text("", "lt-muted")
        self.preview_info.set_ellipsize(3)
        head.pack_start(self.preview_info, True, True, 0)
        self.preview_spinner = Gtk.Spinner()
        head.pack_start(self.preview_spinner, False, False, 0)
        zoom = ui.css(Gtk.Box(), "lt-seg")
        minus = Gtk.Button(label="−")
        ui.name(minus, "Zoom out")
        minus.set_tooltip_text("Zoom out (Ctrl −, Ctrl + wheel)")
        minus.connect("clicked", lambda *_: self.preview.zoom_out())
        self.zoom_label = ui.css(Gtk.Label(label="100%"), "lt-value")
        self.zoom_label.set_tooltip_text("100% fits the whole page; Ctrl+0 goes back to it")
        self.zoom_label.set_width_chars(5)
        plus = Gtk.Button(label="+")
        ui.name(plus, "Zoom in")
        plus.set_tooltip_text("Zoom in (Ctrl +, Ctrl + wheel); drag the page to move around")
        plus.connect("clicked", lambda *_: self.preview.zoom_in())
        for w in (minus, self.zoom_label, plus):
            zoom.pack_start(w, False, False, 0)
        self.zoom = zoom
        zoom.set_sensitive(False)  # until there are pages to zoom
        head.pack_end(zoom, False, False, 0)
        pane.pack_start(head, False, False, 0)
        self.preview = PagePreview(
            on_select=self.on_preview_select,
            cache_dir=os.path.join(self.ctx.printing.session_dir, "display"),
            rows=1,
            on_zoom=lambda z: self.zoom_label.set_text(f"{z * 100:.0f}%"),
            label_for=lambda i, page: f"Page {self.page_numbers[i]}" if i < len(self.page_numbers) else "",
        )
        pane.pack_start(self.preview, True, True, 0)
        self.preview_pane = pane
        self.preview.connect("key-press-event", self._preview_keys)
        return pane

    # -- layout ------------------------------------------------------------------------
    def on_layout(self, mode):
        """Wide: two panes. Compact (< 960 px): options only, the preview on request."""
        self.compact = mode == "compact"
        self.compact_preview.set_visible(self.compact)
        self.set_preview_mode(False)

    def set_preview_mode(self, preview):
        """In a compact window, show the preview in place of the options (or back)"""
        compact = getattr(self, "compact", False)
        self.left.set_visible(not (compact and preview))
        self.preview_pane.set_visible(not compact or preview)
        self.back_btn.set_visible(compact and preview)
        if preview or not compact:
            self.schedule_preview()

    def _preview_keys(self, _w, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        if ctrl and event.keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.preview.zoom_in()
        elif ctrl and event.keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.preview.zoom_out()
        elif ctrl and event.keyval in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self.preview.zoom_fit()
        else:
            return False
        return True

    # -- helpers -------------------------------------------------------------------------
    def set_notice(self, kind=None, message="", actions=()):
        """A message above the cards (print results and problems); kind None clears it"""
        for child in self.notice.get_children():
            self.notice.remove(child)
        self.notice.set_visible(bool(kind))
        if kind:
            level = {"error": logging.WARNING, "ok": logging.INFO}.get(kind, logging.DEBUG)
            log.log(level, "print page: %s", message)
            banner = ui.Banner(kind, GLib.markup_escape_text(message), actions)
            self.notice.pack_start(banner, False, False, 0)
            banner.show_all()

    def set_status(self, text, css="muted"):
        """0.2.x API (features, tools): a notice in the house style"""
        kind = {"status-error": "error", "status-ok": "ok", "status-busy": "busy"}.get(css)
        self.set_notice(kind if text else None, text)

    def set_busy(self, busy, printing=False):
        """Lock the controls while searching or printing; Cancel only while printing"""
        for w in (
            self.change_btn,
            self.color,
            self.quality,
            self.pages,
            self.which,
            self.size_combo,
            self.type_combo,
            self.borderless,
            self.scaling,
            self.copies,
            self.range_entry,
        ):
            w.set_sensitive(not busy)
        self.which.set_sensitive(not busy and self.pages.get_active() == "all")
        self.replace_btn.set_sensitive(not printing)
        self.open_btn.set_sensitive(not printing)
        self.cancel_btn.set_visible(printing)
        if printing != getattr(self, "_printing", False):
            self._printing = printing
            self.ctx.emit("printing", printing)
            if printing:
                self.status_key = "busy"
                self._set_status_line("busy", "Busy · printing your document")
        if not busy:
            self.update_availability()
        self.update_print_button()

    def remember(self, key, value):
        """Persist an option choice and refresh the summary"""
        if not self._loading:
            self.ctx.settings.set(key, value)
        self.update_summary()

    # -- printer ---------------------------------------------------------------------------
    def _set_status_line(self, key, words):
        for child in self.status_line.get_children():
            self.status_line.remove(child)
        self.status_line.pack_start(ui.status_line(key, words), False, False, 0)
        self.status_line.show_all()

    def _set_printer_banner(self, kind=None, message="", actions=()):
        for child in self.printer_banner.get_children():
            self.printer_banner.remove(child)
        if kind:
            banner = ui.Banner(kind, GLib.markup_escape_text(message), actions)
            banner.set_margin_bottom(2)
            self.printer_banner.pack_start(banner, False, False, 0)
            self.printer_banner.show_all()

    def _ready_words(self, status):
        """'Ready · Letter loaded · ink 60% / 80%' from what the printer reports"""
        parts = ["Ready"]
        caps = self.printer.caps if self.printer else None
        ready = caps.raw.get("media-ready") if caps else None
        if isinstance(ready, list):
            ready = ready[0] if ready else None
        if ready and caps.size(ready):
            parts.append(f"{caps.size(ready).label.split(' (')[0]} loaded")
        markers = status[4] if status and len(status) > 4 else []
        levels = [f"{m['level']}%" for m in markers if m.get("level", -1) >= 0]
        if levels:
            parts.append("ink " + " / ".join(levels))
        if self.printer and self.printer.virtual and self.printer.key == PDF_PRINTER_ID:
            return f"Ready · saves into {tilde(self.ctx.settings.get('pdf_folder'))}"
        return " · ".join(parts)

    def show_power(self, level, message, state=None, reasons=()):
        """The printer's state in the shared vocabulary, with its fix in place"""
        self.power_state = level
        key = chip_key(level, state, reasons)
        printing = getattr(self, "_printing", False) or self.ctx.printing.busy  # test pages are jobs too
        if printing and not (key == "attention" and user_must_act(reasons)):  # low ink doesn't stop a job
            # the job reports while it runs (a real failure arrives through on_error); a slow status
            # answer mid-job must never offer Reconnect under a running job. Needs you still shows.
            key = "busy"
        self.status_key = key
        if key == "error":
            words, message = self._cant_reach(message)
        else:
            words = {
                "ok": None,
                "busy": "Busy · printing your document",
                "attention": f"Needs you · {message}",
            }[key]
        self._set_status_line(key, words or self._ready_words(self.last_status))
        known_usb = bool(self.ctx.printing.remembered_usb()) or bool(self.printer and self.printer.usb)
        if key == "attention" and printing:
            self._set_printer_banner("attention", f"{message} The print continues when that is done.")
        elif key == "attention":
            self._set_printer_banner(
                "attention",
                f"{message} LinPrinter checks again by itself, then you can print.",
                [("Check now", self.check_status, None)],
            )
        elif key == "error":
            actions = [("Troubleshoot", self.open_troubleshooter, "primary")]
            if self.printer is not None and any(m.code in ("P1", "T") for m in self.printer.methods):
                actions.append(("Test connection", self.test_connection, None))
            if known_usb:
                actions.append(("Reconnect…", self.on_reconnect, None))
            self._set_printer_banner("error", message, actions)
        else:
            self._set_printer_banner(None)
        self.update_print_button()

    def _cant_reach(self, message):
        """(status words, banner message) for Can't reach: the evidence first, then the cable"""
        p = self.printer
        remembered = self.ctx.printing.remembered_usb() or {}
        usb_id = p.usb.usb_id if p is not None and p.usb else remembered.get("id", "")
        port = p.usb.port_path if p is not None and p.usb else remembered.get("port", "")
        stats = usb_link.cached()
        failing = usb_link.failing_ports(stats, usb_id, port) or usb_link.unidentified_failing_ports(stats)
        if failing:
            return "Can't reach · USB link failing", usb_link.advice(failing[-1], stats)
        if p is not None and not p.methods and p.hint:
            return "Can't reach · not answering", p.hint
        return "Can't reach · not answering", f"The printer doesn't answer. {lt_status.CABLE_FIRST}"

    def test_connection(self):
        """Run the link test on the Printer page (it shows the result)"""
        self.ctx.nav.navigate_to("printer")
        page = self.ctx.nav.get_page_widget("printer")
        if hasattr(page, "run_test"):
            page.run_test()

    def open_troubleshooter(self):
        self.ctx.nav.navigate_to("printer")
        page = self.ctx.nav.get_page_widget("printer")
        if hasattr(page, "start_troubleshooter"):
            page.start_troubleshooter()

    def looking(self):
        """While searching"""
        self.printer_name.set_text("Looking for printers…")
        self._set_status_line("busy", "Searching on USB")
        self._set_printer_banner(None)

    def on_reconnect(self):
        """Re-attach the printer's USB device (asks first; the system asks for the password)"""
        usb = self.printer.usb if self.printer and self.printer.usb else None
        port = usb.port_path if usb else (self.ctx.printing.remembered_usb() or {}).get("port", "?")
        name = self.printer.name if self.printer else "the printer"
        if not ui.confirm(
            self.ctx.window,
            "Reconnect the printer?",
            f"LinPrinter re-attaches {name} on USB port {port}. Nothing else is touched. "
            "Your system asks for your password in its own window.",
            "Reconnect",
        ):
            return
        self.set_notice("busy", "Re-attaching the printer…")

        def done(result):
            ok, text = result
            self.set_notice("ok" if ok else "error", text)
            if ok:
                self.misses = 0
                self.refresh_printers()

        self.ctx.printing._in_thread(
            lambda: self.ctx.printing.reconnect_usb(self.printer), done, lambda m: self.set_notice("error", m)
        )

    def startup(self):
        """At start: reach the remembered printer directly; otherwise search"""
        if self.ctx.settings.get("more_options"):
            self.toggle_more()
        info = self.ctx.settings.get("last_printer_info")
        if not info or not info.get("methods") or self.ctx.settings.get("search_at_start"):
            return self.refresh_printers()
        self.looking()

        def failed(message):
            log.info("remembered printer didn't answer (%s); searching", message)
            self.refresh_printers()

        self.ctx.printing.restore(self.printers_loaded, failed)
        return False

    def refresh_printers(self, *_):
        """Search for printers in the background (not while printing)"""
        if self.ctx.printing.busy:
            return False
        self.set_busy(True)
        self.looking()
        self.ctx.printing.refresh_printers(self.printers_loaded, self.printers_failed)
        return False

    def printers_loaded(self, printers):
        """Keep the list; select the last used printer (else the first real one)"""
        self.printers = printers
        self.ctx.emit("printers-changed", printers)
        last = self.ctx.settings.get("last_printer")
        chosen = next((p for p in printers if p.id == last), None) or (printers[0] if printers else None)
        self.select_printer(chosen)
        self._build_printer_menu()
        self.set_busy(False)

    def printers_failed(self, message):
        """A search error: plain words, the details in the log"""
        log.warning("printer search failed: %s", message)
        self.set_busy(False)
        self.printer_name.set_text("No printer answered")
        self.show_power(
            "error", "Nothing answered on USB. Check that the printer is on, then try another USB cable."
        )

    def _build_printer_menu(self):
        """The Change popover: every printer (with why it can't print yet), search again, manage"""
        if self.printer_menu.get_child():
            self.printer_menu.remove(self.printer_menu.get_child())
        col = ui.css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2), "lt-printer-menu")
        group = self._menu_leader = (
            Gtk.RadioButton()
        )  # hidden leader: a group can't have none active, so it holds "none"
        for p in self.printers:
            label = p.label if p.methods else f"{p.name} (can't print yet)"
            radio = Gtk.RadioButton.new_with_label_from_widget(group, label)
            group = group or radio
            radio.set_active(self.printer is not None and p.id == self.printer.id)
            radio.connect("toggled", lambda r, p=p: r.get_active() and self._choose(p))
            col.pack_start(radio, False, False, 0)
        col.pack_start(ui.css(Gtk.Box(), "lt-divider"), False, False, 4)
        for label, action in (
            ("Search for printers again (F5)", lambda: self.ctx.emit("request-printer-refresh")),
            ("Printer details and upkeep", lambda: self.ctx.nav.navigate_to("printer")),
        ):
            b = Gtk.ModelButton(text=label)
            b.connect("clicked", lambda _b, a=action: a())
            col.pack_start(b, False, False, 0)
        col.show_all()
        self.printer_menu.add(col)

    def _choose(self, printer):
        self.printer_menu.popdown()
        if self.printer is None or printer.id != self.printer.id:
            self.select_printer(printer)

    def current_printer(self):
        """The chosen PrinterDevice (or None)"""
        return self.printer

    def select_printer(self, printer):
        """Offer the chosen printer's options; check its status"""
        self.printer = printer
        self.last_status = None  # never another printer's reasons or ink
        self.ctx.emit("printer-selected", printer)
        if printer is None:
            self.printer_name.set_text("No printer found yet")
            self.show_power("error", "No printer found. Check the cable and power, then search again.")
            return
        self.printer_name.set_text(printer.name)
        self.ctx.settings.set("last_printer", printer.id)
        self.ctx.printing.remember(printer)
        self.fill_options(printer)
        self.check_status()

    def check_status(self):
        """Ask the printer how it is (in the background)"""
        printer = self.printer
        if printer is None:
            return

        def done(status):  # a printer without methods answers ("error", its hint) from the worker too
            level, message = status[0], status[1]
            if self.printer is printer:
                self.last_status = status
                self.show_power(level, message, status[2], status[3])
                if not self.ctx.printing.busy:  # a slow answer mid-job isn't a lost printer
                    self.misses = self.misses + 1 if level == "error" else 0
                self.maybe_reconnect(printer)
            self.ctx.emit("printer-status", printer, status)

        self.ctx.printing.status_async(printer, done)

    def maybe_reconnect(self, printer):
        """The printer stopped answering: look for it again, quietly, now and then"""
        if not self.ctx.printing.should_reconnect(
            "error" if self.misses else "ok",
            self.misses,
            time.monotonic() - self.last_reconnect,
            self.ctx.printing.busy,
            virtual=printer.virtual,
        ):
            return
        self.last_reconnect = time.monotonic()
        log.info("%s stopped answering (%d checks); searching again", printer.name, self.misses)
        self.ctx.printing.refresh_printers(self.reconnected, lambda e: log.info("search failed: %s", e))

    def reconnected(self, printers):
        """A quiet search finished: keep the chosen printer; say so if it is back"""
        chosen = self.printer.id if self.printer else None
        was_missing = self.printer is not None and not self.printer.methods
        self.printers = printers
        self.ctx.emit("printers-changed", printers)
        found = next((p for p in printers if p.id == chosen), None)
        if found is not None and found is not self.printer:
            self.select_printer(found)
        self._build_printer_menu()
        if found is not None and found.methods and (was_missing or self.misses):
            self.misses = 0
            self.set_notice("ok", f"{found.name} is back.")
            self.check_status()

    def poll_status(self):
        """Every few seconds; while printing only every third time (paper out mid-job must show, but
        the job's own traffic comes first on a USB link)"""
        window = self.ctx.window
        self._polls = getattr(self, "_polls", 0) + 1
        if self.ctx.printing.busy and self._polls % 3:
            return True
        if self.printer is not None and window is not None and window.get_mapped():
            self.check_status()
        return True

    # -- options -----------------------------------------------------------------------------
    def fill_options(self, printer):
        """Paper sizes (grouped), types, colours, qualities for this printer"""
        caps = printer.caps
        if caps is None:
            return
        s = self.ctx.settings
        self._loading = True
        self.size_combo.remove_all()
        group = None
        for size in sorted(
            caps.sizes, key=lambda z: ["Documents", "Photos", "Envelopes", "Cards", "Other"].index(z.group)
        ):
            if group is not None and size.group != group:
                self.size_combo.append(f"-{size.group}", "")
            group = size.group
            self.size_combo.append(size.keyword, size.label)
        if not self.size_combo.set_active_id(s.get("paper")):
            self.size_combo.set_active_id(self.ctx.printing.default_size(caps))
        self.type_combo.remove_all()
        for t in caps.types:
            self.type_combo.append(t, type_label(t))
        if not self.type_combo.set_active_id(s.get("paper_type")):
            self.type_combo.set_active_id(
                caps.default_type
                if caps.default_type in caps.types
                else (caps.types[0] if caps.types else "")
            )
        self.type_row.set_visible(bool(caps.types))
        top = max(1, caps.copies_max)
        self.copies.set_range(1, top)
        self.copies_hint.set_text(f"up to {top}" if top > 1 else "one copy only")
        self.copies.set_tooltip_text(f"Copies: {self.copies_hint.get_text()}")
        for key, btn in self.color.buttons.items():
            btn.set_visible(key in caps.colors)
        if self.color.get_active() not in caps.colors:
            self.color.set_active(caps.colors[0])
        for key, btn in self.quality.buttons.items():
            btn.set_visible(key in caps.qualities)
        self.quality_row.set_visible(len(caps.qualities) > 1)
        if self.quality.get_active() not in caps.qualities:
            self.quality.set_active("normal" if "normal" in caps.qualities else caps.qualities[0])
        self._loading = False
        self.on_size_or_type()

    def on_size_or_type(self):
        """Paper size or type changed: remember it and update Borderless"""
        if self._loading:
            return
        if self.size_combo.get_active_id():
            self.ctx.settings.set("paper", self.size_combo.get_active_id())
        if self.type_combo.get_active_id():
            self.ctx.settings.set("paper_type", self.type_combo.get_active_id())
        self.update_availability()
        self.update_summary()

    def update_availability(self):
        """Borderless only where the printer allows it for this size and type (the reason beside it)"""
        printer = self.printer
        if printer is None or printer.caps is None:
            return
        can = printer.caps.can_borderless(
            self.size_combo.get_active_id() or "", self.type_combo.get_active_id() or None
        )
        self.borderless.set_sensitive(can and not self.ctx.printing.busy)
        if not can and self.borderless.get_active():
            self._loading = True
            self.borderless.set_active(False)
            self._loading = False
        reason = "Needs photo paper" if printer.caps.borderless else "Not available on this printer"
        self.borderless_note.set_text("Prints to the edge; may crop slightly" if can else reason)
        ui.name(self.borderless, "Borderless" if can else f"Borderless, {reason.lower()}")

    def on_pages_choice(self, key):
        """Show the page box for Custom; Which (odd/even) applies to All"""
        self.range_row.set_visible(key == "range")
        if key == "range":
            self.range_entry.grab_focus()
        self.which.set_sensitive(key == "all" and not self.ctx.printing.busy)
        self.which_row.set_tooltip_text(None if key == "all" else "Odd and even apply when Pages is All")
        self.update_summary()

    def page_choice(self):
        """The select_pages() choice from Pages and Which"""
        main = self.pages.get_active()
        if main == "all" and self.which.get_active() in ("odd", "even"):
            return self.which.get_active()
        return main

    def choices(self):
        """The current choices as a dict (also what profiles store)"""
        return {
            "size": self.size_combo.get_active_id(),
            "type": self.type_combo.get_active_id() or "",
            "borderless": self.borderless.get_active(),
            "color": self.color.get_active(),
            "quality": self.quality.get_active(),
            "copies": int(self.copies.get_value()),
            "scaling": self.scaling.get_active(),
        }

    def apply_choices(self, choices):
        """Set the controls from a dict (profiles, printer defaults); unsupported choices are skipped"""
        caps = self.printer.caps if self.printer else None
        if "color" in choices and (caps is None or choices["color"] in caps.colors):
            self.color.set_active(choices["color"])
        if "quality" in choices and caps and choices["quality"] in caps.qualities:
            self.quality.set_active(choices["quality"])
        if "type" in choices:
            self.type_combo.set_active_id(choices["type"])
        if "size" in choices:
            self.size_combo.set_active_id(choices["size"])
        if "size_stem" in choices and caps:
            kw = next(
                (z.keyword for z in caps.sizes if z.keyword.startswith(choices["size_stem"] + "_")), None
            )
            if kw:
                self.size_combo.set_active_id(kw)
        if "scaling" in choices:
            self.scaling.set_active(choices["scaling"])
        if "borderless" in choices:
            self.borderless.set_active(bool(choices["borderless"]))
        if "copies" in choices:
            self.copies.set_value(int(choices["copies"]))
        self.update_availability()
        self.update_summary()

    def selected_pages(self):
        """1-based pages to print (RenderError for a bad range)"""
        doc = self.ctx.printing.document
        if not doc:
            return []
        return select_pages(
            self.page_choice(), doc["pages"], self.range_entry.get_text(), current=self.ctx.preview_page or 1
        )

    def ticket(self):
        """The job ticket for the current choices"""
        return self.ctx.printing.ticket(self.printer, self.choices())

    def update_summary(self):
        """The action bar says exactly what will print"""
        if self._loading:
            return
        doc = self.ctx.printing.document
        ui.set_invalid(self.range_entry, False, self.range_hint)  # the hint is set again below
        self._pages_wrong = False
        if self.printer is None or self.printer.caps is None:
            self.bar.idle("Nothing to print yet", "Open a document and connect a printer")
            self.update_print_button()
            return
        try:
            pages = self.selected_pages() if doc else []
        except RenderError as e:
            # a short caption keeps the label column (and the box) in line; the bar has the full words
            ui.set_invalid(self.range_entry, True, self.range_hint, "Check it")
            self._pages_wrong = True
            self.schedule_preview()  # clears it: no pages from an earlier list on show
            self.bar.idle("Check the pages to print", str(e))
            self.update_print_button()
            return
        if self.pages.get_active() == "range":
            n = len(pages)
            self.range_hint.set_text(
                f"{n} page{'s' if n != 1 else ''}" if doc else ""
            )  # example: placeholder
        ticket = self.ticket()
        detail = self.ctx.printing.settings_summary(ticket, self.printer)
        if self.printer.virtual and self.printer.key == PDF_PRINTER_ID:
            detail += f" → {tilde(self.ctx.settings.get('pdf_folder'))}"
        copies = int(self.copies.get_value())
        head = (
            f"{copies} cop{'ies' if copies != 1 else 'y'} · {len(pages)} page{'s' if len(pages) != 1 else ''}"
            if doc
            else NO_DOC
        )
        if self.bar.state() != "busy":
            self.bar.idle(head, detail if doc else "Open a document (Ctrl+O) or drop a file on this page")
            self.secondary_btn.hide()
        self.update_print_button()
        self.ctx.emit("ticket-changed")

    def update_print_button(self):
        """Print is enabled only when it can work; otherwise the reason sits beside it"""
        reason = ""
        status = self.last_status
        printing = getattr(self, "_printing", False) or self.ctx.printing.busy
        key = getattr(self, "status_key", "")
        if printing:
            reason = ""
        elif self.printer is None:
            reason = "Connect a printer first"
        elif not self.ctx.printing.document:
            reason = "Open a document first"
        elif getattr(self, "_pages_wrong", False):
            reason = "Fix the page list first"  # the bar's headline already says what to check
        elif key == "attention" and status and (user_must_act(status[3]) or status[2] == "stopped"):
            reason = needs_you_words(status[3])
        elif key == "error" or not self.printer.methods:
            reason = "Fix the connection first"
        self.print_btn.set_sensitive(not reason and not printing)
        self.why_not.set_text(reason)
        self.why_not.set_visible(bool(reason))
        label = "Printing…" if printing else ("Print again" if self.bar.state() == "done" else "Print")
        box = self.print_btn.get_child()
        if isinstance(box, Gtk.Box):
            box.get_children()[0].set_text(label)
            box.get_children()[1].set_visible(not printing)

    # -- preview ---------------------------------------------------------------------------
    def schedule_preview(self, *_):
        """Re-render shortly after the options change (only while the preview is on screen)"""
        if not self.preview_pane.get_visible() or self.ctx.nav.get_current_page() not in (None, "print"):
            return
        if self._preview_pending:
            GLib.source_remove(self._preview_pending)
        self._preview_pending = GLib.timeout_add(350, self.render_preview)

    def render_preview(self):
        """Render the chosen pages in the background (page 1 first)"""
        self._preview_pending = None
        self._render_id = getattr(self, "_render_id", 0) + 1  # any render still running is now stale
        mine = self._render_id
        pm = self.ctx.printing
        if not pm.document or self.printer is None or self.printer.caps is None:
            self.preview_spinner.stop()
            self.zoom.set_sensitive(False)
            self.preview.set_pages([])
            self.preview_info.set_text("")
            return False
        try:
            pages = self.selected_pages()
        except RenderError as e:
            self.preview_spinner.stop()
            self.zoom.set_sensitive(False)
            self.preview.show_message("Nothing to show: fix the page list.")
            self.preview_info.set_text(str(e))
            return False
        ticket = self.ticket()
        self.preview_spinner.start()

        def done(images):
            if mine != self._render_id:
                return  # an older render finished after a newer one started
            self.preview_spinner.stop()
            self.page_numbers = pages
            shown = [{"path": p, "rotation": 0, "dpi": PREVIEW_DPI, "mode": ticket["color"]} for p in images]
            self.preview.set_pages(shown, selected=0)
            self.zoom.set_sensitive(bool(shown))
            self.update_preview_info()

        def failed(message):
            if mine != self._render_id:
                return
            self.preview_spinner.stop()
            self.zoom.set_sensitive(False)
            self.preview.set_pages([])
            self.preview_info.set_text(message)

        pm.preview_async(ticket, pages, done, failed)
        return False

    def on_preview_select(self, index):
        """Remember the page shown (Pages → Current prints it)"""
        if 0 <= index < len(self.page_numbers):
            self.ctx.preview_page = self.page_numbers[index]
            self.update_preview_info()

    def update_preview_info(self):
        i = self.preview.selected
        if not self.page_numbers or i < 0:
            self.preview_info.set_text("")
            return
        size = (
            self.printer.caps.size(self.size_combo.get_active_id() or "")
            if self.printer and self.printer.caps
            else None
        )
        paper = size.label.split(" (")[0] if size else ""
        self.preview_info.set_text(
            f"Page {self.page_numbers[i]} ({i + 1} of {len(self.page_numbers)} to print) · {paper}"
            + (" · margins shaded" if any(self.ticket().get("margins_mm") or ()) else "")
        )

    # -- document ------------------------------------------------------------------------------
    def choose_document(self):
        """File dialog for a document"""
        dlg = Gtk.FileChooserDialog(
            title="Open a document to print", transient_for=self.ctx.window, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.ACCEPT)
        flt = Gtk.FileFilter()
        flt.set_name("Documents (PDF, pictures, text)")
        for ext in OPENABLE:
            flt.add_pattern(f"*{ext}")
            flt.add_pattern(f"*{ext.upper()}")
        dlg.add_filter(flt)
        path = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if path:
            self.open_document(path)

    def on_drop(self, _widget, _ctx, _x, _y, data, _info, _time):
        """A file dropped on the page"""
        uris = data.get_uris() or []
        if uris:
            self.open_document(unquote(urlparse(uris[0]).path))

    def reprint(self, path, choices=None):
        """Activity → Print again: the document with the options it was printed with (still editable)"""
        self.ctx.nav.navigate_to("print")
        self.open_document(path, choices)

    def open_document(self, path, choices=None):
        """Prepare a document (in the background) and show it"""
        if getattr(self, "_printing", False) or self.ctx.printing.busy:
            self.set_notice("attention", "Wait for this print to finish, then open the next document.")
            return
        self.doc_hint.set_text(f"Opening {os.path.basename(path)}…")

        def done(doc):
            size = os.path.getsize(doc["path"]) if os.path.exists(doc["path"]) else 0
            n = doc["pages"]
            self.doc_name.set_text(os.path.basename(doc["path"]))
            self.doc_detail.set_text(
                f"{n} page{'s' if n != 1 else ''} · {size / 1048576:.1f} MB · {tilde(os.path.dirname(doc['path']))}"
                if size >= 104858
                else f"{n} page{'s' if n != 1 else ''} · {max(1, size // 1024)} KB · {tilde(os.path.dirname(doc['path']))}"
            )
            self.doc_stack.set_visible_child_name("doc")
            self.replace_btn.show()
            self.set_notice(None)
            self.bar.idle("", "")  # the last job's result belongs to the last document
            if choices:
                self.apply_choices(choices)
            self.update_summary()
            self.ctx.emit("document-changed", doc)
            self.schedule_preview()

        def failed(message):
            self.doc_hint.set_text("Drop a PDF, picture or text file here")
            self.set_notice("error", message)

        self.ctx.printing.open_async(path, done, failed)

    # -- printing ------------------------------------------------------------------------------
    def on_print(self):
        """Check, confirm warnings, and print"""
        printer, doc = self.printer, self.ctx.printing.document
        if printer is None or self.ctx.printing.busy:
            return
        if not doc:
            self.set_notice(
                "attention", "Open a document first: Open… (Ctrl+O), or drop a file on this page."
            )
            return
        if not self.print_btn.get_sensitive():
            return
        try:
            pages = self.selected_pages()
        except RenderError as e:
            self.set_notice("error", str(e))
            return
        ticket = self.ticket()
        warnings = (
            self.ctx.features.before_print(
                self.ctx, printer, ticket, self.last_status or ("ok", "", "idle", [], [])
            )
            if self.ctx.features
            else []
        )
        if warnings and not ui.confirm(
            self.ctx.window,
            warnings[0].split(":")[0] if len(warnings) == 1 else "Ink is low",
            " ".join(warnings) + " You can still print.",
            "Print anyway",
        ):
            return
        self.set_notice(None)
        self._job_doc = doc
        self._progress_fraction = 0.0  # determinate from the start: the page count is known
        self._started = time.monotonic()
        self._job_pages = len(pages) * int(ticket.get("copies", 1))
        self.set_busy(True, printing=True)
        self._progress_text = f"Sending {len(pages)} page{'s' if len(pages) != 1 else ''} to {printer.name}…"
        self.bar.busy(self._progress_text, 0.0)
        self._pulse = GLib.timeout_add(200, self._tick)
        self.ctx.printing.print_async(
            printer,
            ticket,
            pages,
            self._on_progress,
            lambda r: self.on_done(printer, ticket, r),
            lambda m: self.on_error(m, printer, ticket, pages),
        )

    def _on_progress(self, text):
        self._progress_text = text.rstrip("…")
        m = re.search(r"page (\d+) of (\d+)", text)
        if m:
            self._progress_fraction = (int(m.group(1)) - 1) / max(1, int(m.group(2)))

    def _tick(self):
        secs = int(time.monotonic() - self._started)
        words = f"{self._progress_text} · {secs} s"
        st = self.last_status
        if getattr(self, "status_key", "") == "attention" and st and user_must_act(st[3]):
            words = f"Waiting for you: {st[1].rstrip('.')} · {secs} s"  # the job is paused
        if self._progress_fraction is None:
            self.bar.pulse(words)
        else:
            self.bar.busy(words, self._progress_fraction)
        return True

    def _stop_pulse(self):
        if self._pulse:
            GLib.source_remove(self._pulse)
            self._pulse = None

    def on_cancel(self):
        """Ask, then cancel the running job"""
        if ui.confirm(
            self.ctx.window,
            "Cancel this print?",
            "The printer finishes the sheet it is on, then stops.",
            "Cancel print",
            destructive=True,
            cancel_label="Keep printing",
        ):
            self.ctx.printing.cancel()

    def _show_secondary(self, label, action):
        self.secondary_btn.set_label(label)
        self._secondary_action = action
        self.secondary_btn.show()

    def on_done(self, printer, ticket, result):
        """The end moment: what happened, how long it took, and what next"""
        self._stop_pulse()
        self.set_busy(False)
        state = result.get("state")
        secs = int(time.monotonic() - self._started)
        pages = getattr(self, "_job_pages", 0)
        words = f"{pages} page{'s' if pages != 1 else ''}"
        if result.get("file"):
            path = result["file"]
            self.bar.done("Saved as PDF", tilde(path))
            self._show_secondary("Show in folder", lambda: show_in_file_manager(path, self.ctx.window))
        elif state == "completed":
            self.bar.done(
                f"Printed {words} on {printer.name} · {secs} s",
                "Saved in Activity with these settings, ready to print again.",
            )
            self._show_secondary("Show in Activity", lambda: self.ctx.nav.navigate_to("activity"))
        elif state == "canceled":
            self.bar.idle("Cancelled", "Nothing more will print.")
            self.set_notice(None)
        elif state == "aborted":
            self.bar.idle("The printer stopped the job", "Check its display or lights, then print again.")
            self.set_notice(
                "error", "The printer stopped the job. Check its display or lights, then print again."
            )
        else:
            self.bar.done(f"Sent {words} to {printer.name}", "Follow its progress in Activity.")
            self._show_secondary("Show in Activity", lambda: self.ctx.nav.navigate_to("activity"))
        self.update_print_button()
        if self.ctx.features:
            self.ctx.features.after_print(self.ctx, printer, ticket, result)
        self.ctx.emit("documents-changed")
        self.ctx.emit("jobs-changed")
        self.check_status()

    def on_error(self, message, printer=None, ticket=None, pages=None):
        """A print problem: said where it happened, with the next step; kept in Activity"""
        self._stop_pulse()
        self.set_busy(False)
        if message.strip() == "Cancelled.":  # cancelled before the printer took it: nothing to fix
            self.bar.idle("Cancelled", "Nothing was printed.")
            self.set_notice(None)
            self.check_status()
            return
        link = "USB" in message or "cable" in message or "connection" in message.lower()
        actions = [("Troubleshoot", self.open_troubleshooter, "primary")] if link else []
        self.set_notice("error", message, actions)
        self.bar.idle("Didn't print", message.split(".")[0] + ".")
        doc = getattr(self, "_job_doc", None)
        if doc and printer is not None and ticket is not None:
            try:
                reason = "Stopped: USB link dropped" if link else "Stopped: " + message.split(".")[0][:60]
                add_recent(
                    doc["path"],
                    printer.name,
                    len(pages or []),
                    self.ctx.printing.settings_summary(ticket, printer),
                    result=reason,
                    choices=ticket_choices(ticket),
                )
                self.ctx.emit("documents-changed")
            except OSError as e:
                log.info("could not record the failed print: %s", e)
        self.check_status()

    def on_shown(self):
        """Refresh the status and the preview when the page is opened"""
        self.check_status()
        self.schedule_preview()
