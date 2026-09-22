"""
Print Page
Choose a printer (or Print to PDF), a document and the options, then Print.
Laid out like LinScanner's Scan page: Detect Printer (Find, the printer list,
a power icon: green ready / red "Printer may be off"), Document, Print Options
(equal-width segmented buttons, half-width lists), a summary line, Print /
Cancel / Preview, progress and status.

Only options the printer reports are offered (IPP Everywhere capabilities);
page selection and rotation are done by LinPrinter itself.
"""

import logging
import os
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from backends.backend_base import type_label  # noqa: E402
from config.config_print import COLOR_MODES, PAGE_CHOICES, QUALITIES, SCALING, STATUS_EVERY  # noqa: E402
from modules.manager_render import OPENABLE, RenderError, select_pages  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from ui.components.component_segmented import SegmentedControl  # noqa: E402
from utils.util_icons import icon_image  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

OPTION_BUTTON_WIDTH = 150  # every option button the same width, so the choices line up in columns


def half(widget):
    """A box giving widget half the available width"""
    box = Gtk.Box(homogeneous=True)
    box.pack_start(widget, True, True, 0)
    box.pack_start(Gtk.Box(), True, True, 0)
    return box


class PrintPage(BasePage):
    """Printer, document, options and the Print button"""

    def build_content(self):
        """Detect Printer, Document, Print Options, actions, progress and status"""
        self.printers = []
        self.printer = None
        self.last_status = None
        self._loading = False
        self.add_title("Print", "Choose a document and the options, then press Print.")

        # -- Detect Printer
        card = self.add_card("Detect Printer")
        row = Gtk.Box(spacing=10)
        self.find_btn = Gtk.Button(label="Find")
        self.find_btn.set_tooltip_text("Search for printers (USB) again")
        self.find_btn.connect("clicked", lambda *_: self.refresh_printers())
        row.pack_start(self.find_btn, False, False, 0)
        box = Gtk.Box(spacing=10)
        self.printer_combo = Gtk.ComboBoxText()
        self.printer_combo.connect("changed", self.on_printer_changed)
        box.pack_start(self.printer_combo, True, True, 0)
        theme = getattr(self.ctx.theme, "current_theme", None)
        self.mark = Gtk.Stack()
        self.mark.set_size_request(24, 24)
        self.spinner = Gtk.Spinner()
        self.mark.add_named(self.spinner, "looking")
        self.power_icons = {
            "ok": icon_image("power", 22, getattr(theme, "success", None) or "#3fd059"),
            "warn": icon_image("power", 22, "#e0a020"),
            "error": icon_image("power", 22, getattr(theme, "error", None) or "#e8555d"),
        }
        for level, img in self.power_icons.items():
            self.mark.add_named(img, level)
        self.mark.add_named(Gtk.Box(), "none")
        box.pack_start(self.mark, False, False, 0)
        printers_btn = Gtk.Button(label="Printers")
        printers_btn.set_tooltip_text("Every printer found, with its connection, capabilities and ink levels")
        printers_btn.connect("clicked", lambda *_: self.ctx.nav.navigate_to("printers"))
        box.pack_start(printers_btn, False, False, 0)
        row.pack_start(half(box), True, True, 0)
        card.pack_start(row, False, False, 0)
        self.printer_message = self.label("", "status-error", wrap=True)
        self.printer_message.set_no_show_all(True)  # a problem with the printer, in plain words
        card.pack_start(self.printer_message, False, False, 0)
        self.power_state = "none"

        # -- Document
        card = self.add_card("Document")
        row = Gtk.Box(spacing=10)
        open_btn = Gtk.Button(label="Open…")
        open_btn.set_tooltip_text("PDF, image (PNG, JPEG, TIFF…) or plain text; or drop a file on this page")
        open_btn.connect("clicked", lambda *_: self.choose_document())
        row.pack_start(open_btn, False, False, 0)
        self.doc_label = self.label("No document yet. Open one, or drop a file here.", "muted", wrap=True)
        row.pack_start(self.doc_label, True, True, 0)
        card.pack_start(row, False, False, 0)
        self.drag_dest_set(
            Gtk.DestDefaults.ALL, [Gtk.TargetEntry.new("text/uri-list", 0, 0)], Gdk.DragAction.COPY
        )
        self.connect("drag-data-received", self.on_drop)

        # -- Print Options
        card = self.add_card("Print Options")
        self.options_card = card  # features (e.g. profiles) add rows here
        self.copies = Gtk.SpinButton.new_with_range(1, 99, 1)
        self.copies.set_value(1)
        self.copies.set_halign(Gtk.Align.START)
        self.copies.connect("value-changed", lambda *_: self.update_summary())
        card.pack_start(self.form_row("Copies", self.copies), False, False, 0)
        self.color = SegmentedControl(
            list(COLOR_MODES.items()),
            active=self.ctx.settings.get("color_mode"),
            on_changed=lambda k: self.remember("color_mode", k),
            button_width=OPTION_BUTTON_WIDTH,
        )
        self.color_row = self.form_row("Color", self.color)
        card.pack_start(self.color_row, False, False, 0)
        self.quality = SegmentedControl(
            list(QUALITIES.items()),
            active=self.ctx.settings.get("quality"),
            on_changed=lambda k: self.remember("quality", k),
            button_width=OPTION_BUTTON_WIDTH,
        )
        self.quality_row = self.form_row("Quality", self.quality)
        card.pack_start(self.quality_row, False, False, 0)
        self.pages = SegmentedControl(
            list(PAGE_CHOICES.items()),
            active="all",
            on_changed=lambda k: self.on_pages_choice(k),
            button_width=OPTION_BUTTON_WIDTH // 2 + 20,
        )
        pages_box = Gtk.Box(spacing=10)
        pages_box.pack_start(self.pages, False, False, 0)
        self.range_entry = Gtk.Entry()
        self.range_entry.set_placeholder_text("e.g. 1-3, 5")
        self.range_entry.set_width_chars(14)
        self.range_entry.set_no_show_all(True)
        self.range_entry.connect("changed", lambda *_: self.update_summary())
        pages_box.pack_start(self.range_entry, False, False, 0)
        card.pack_start(self.form_row("Pages", pages_box), False, False, 0)
        self.size_combo = Gtk.ComboBoxText()
        self.size_combo.set_row_separator_func(lambda model, it: (model[it][1] or "").startswith("-"))
        self.size_combo.connect("changed", lambda c: self.on_size_or_type())
        card.pack_start(self.form_row("Paper Size", half(self.size_combo)), False, False, 0)
        self.type_combo = Gtk.ComboBoxText()
        self.type_combo.connect("changed", lambda c: self.on_size_or_type())
        self.type_row = self.form_row("Paper Type", half(self.type_combo))
        card.pack_start(self.type_row, False, False, 0)
        self.borderless = SegmentedControl(
            [("off", "Off"), ("on", "On")],
            active="on" if self.ctx.settings.get("borderless") else "off",
            on_changed=lambda k: self.remember("borderless", k == "on"),
            button_width=OPTION_BUTTON_WIDTH,
        )
        self.borderless_note = self.label("", "muted")
        box = Gtk.Box(spacing=10)
        box.pack_start(self.borderless, False, False, 0)
        box.pack_start(self.borderless_note, False, False, 0)
        card.pack_start(self.form_row("Borderless", box), False, False, 0)
        self.scaling = SegmentedControl(
            list(SCALING.items()),
            active=self.ctx.settings.get("scaling"),
            on_changed=lambda k: self.remember("scaling", k),
            button_width=OPTION_BUTTON_WIDTH,
        )
        card.pack_start(self.form_row("Fit", self.scaling), False, False, 0)
        self.summary = self.label("", "muted", wrap=True)
        card.pack_start(self.summary, False, False, 0)

        # -- actions
        actions = Gtk.Box(spacing=12)
        self.print_btn = Gtk.Button(label="Print")
        self.print_btn.get_style_context().add_class("primary-pill")
        self.print_btn.connect("clicked", lambda *_: self.on_print())
        actions.pack_start(self.print_btn, False, False, 0)
        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.set_sensitive(False)
        self.cancel_btn.connect("clicked", lambda *_: self.ctx.printing.cancel())
        actions.pack_start(self.cancel_btn, False, False, 0)
        self.preview_btn = Gtk.Button(label="Preview")
        self.preview_btn.set_tooltip_text("See the pages exactly as they will print")
        self.preview_btn.connect("clicked", lambda *_: self.ctx.nav.navigate_to("preview"))
        actions.pack_start(self.preview_btn, False, False, 0)
        self.pack_start(actions, False, False, 4)
        self.progress = Gtk.ProgressBar()
        self.pack_start(self.progress, False, False, 0)
        self.status = self.label("", "muted", wrap=True, selectable=True)  # printing progress and results
        self.pack_start(self.status, False, False, 0)

        if self.ctx.features:
            self.ctx.features.extend("extend_print_page", self)
        self.ctx.on("request-printer-refresh", self.refresh_printers)
        self.ctx.on("open-document", self.open_document)
        self.set_busy(True)
        GLib.idle_add(self.startup)
        GLib.timeout_add_seconds(STATUS_EVERY, self.poll_status)

    # -- helpers -------------------------------------------------------------------
    def set_status(self, text, css="muted"):
        """Status line (printing progress, results, errors)"""
        level = {"status-error": logging.WARNING, "status-ok": logging.INFO}.get(css, logging.DEBUG)
        log.log(level, "print page: %s", text)
        ctx = self.status.get_style_context()
        for c in ("muted", "status-ok", "status-error", "status-busy"):
            ctx.remove_class(c)
        ctx.add_class(css)
        self.status.set_text(text)

    def set_busy(self, busy, printing=False):
        """Enable or disable controls while working; Cancel only while printing"""
        for w in (
            self.print_btn,
            self.find_btn,
            self.printer_combo,
            self.color,
            self.quality,
            self.pages,
            self.size_combo,
            self.type_combo,
            self.borderless,
            self.scaling,
            self.copies,
            self.range_entry,
        ):
            w.set_sensitive(not busy)
        self.cancel_btn.set_sensitive(printing)
        if not busy:
            self.update_availability()

    def remember(self, key, value):
        """Persist an option choice and refresh the summary"""
        if not self._loading:
            self.ctx.settings.set(key, value)
        self.update_summary()

    # -- printers ------------------------------------------------------------------
    def looking(self):
        """Spinner in place of the power icon while searching"""
        self.spinner.start()
        self.mark.set_visible_child_name("looking")
        self.printer_message.hide()

    def show_power(self, level, message):
        """Green / amber / red power icon; the message under the list unless all is well"""
        self.spinner.stop()
        self.power_state = level
        self.mark.set_visible_child_name(level)
        self.power_icons[level].set_tooltip_text(message)
        show = level != "ok"
        self.printer_message.set_text(message if show else "")
        self.printer_message.set_no_show_all(not show)
        self.printer_message.show() if show else self.printer_message.hide()
        ctx = self.printer_message.get_style_context()
        ctx.remove_class("status-error" if level == "warn" else "status-busy")
        ctx.add_class("status-busy" if level == "warn" else "status-error")

    def startup(self):
        """At start: reach the remembered printer directly; otherwise search"""
        info = self.ctx.settings.get("last_printer_info")
        if not info or not info.get("methods"):
            return self.refresh_printers()
        self.looking()

        def failed(message):
            log.info("remembered printer didn't answer (%s); searching", message)
            self.refresh_printers()

        self.ctx.printing.restore(self.printers_loaded, failed)
        return False

    def refresh_printers(self):
        """Search for printers in the background (not while printing)"""
        if self.ctx.printing.busy:
            return False
        self.set_busy(True)
        self.looking()
        self.ctx.printing.refresh_printers(self.printers_loaded, self.printers_failed)
        return False

    def printers_loaded(self, printers):
        """Fill the printer list; select the last used printer (else the first real one)"""
        self.printers = printers
        self.ctx.emit("printers-changed", printers)
        self.printer_combo.remove_all()
        for p in printers:
            self.printer_combo.append(p.id, p.label if p.methods else f"{p.name}  (can't print yet)")
        last = self.ctx.settings.get("last_printer")
        if not self.printer_combo.set_active_id(last):
            self.printer_combo.set_active(0)
        self.set_busy(False)

    def printers_failed(self, message):
        """A search error: plain words, the details in the log"""
        log.warning("printer search failed: %s", message)
        self.set_busy(False)
        self.show_power("error", "Printer may be off. Check power settings.")

    def current_printer(self):
        """The chosen PrinterDevice (or None)"""
        pid = self.printer_combo.get_active_id()
        return next((p for p in self.printers if p.id == pid), None)

    def on_printer_changed(self, _combo):
        """Offer the chosen printer's options; check its status"""
        printer = self.current_printer()
        if printer is None:
            return
        self.printer = printer
        self.ctx.settings.set("last_printer", printer.id)
        self.ctx.printing.remember(printer)
        self.fill_options(printer)
        self.check_status()
        self.ctx.emit("printer-selected", printer)

    def check_status(self):
        """Ask the printer how it is (in the background)"""
        printer = self.printer
        if printer is None:
            return
        if not printer.methods:
            self.show_power("error", printer.hint or "This printer can't be reached.")
            return

        def done(status):
            self.last_status = status
            level, message = status[0], status[1]
            if self.printer is printer:
                self.show_power(level, message)
            self.ctx.emit("printer-status", printer, status)

        self.ctx.printing.status_async(printer, done)

    def poll_status(self):
        """Every few seconds: refresh the power icon (not while printing, the job reports then)"""
        if self.printer is not None and not self.ctx.printing.busy and self.get_mapped():
            self.check_status()
        return True

    # -- options ---------------------------------------------------------------------
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
        self.copies.set_range(1, max(1, caps.copies_max))
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
        """Borderless only where the printer allows it for this size and type"""
        printer = self.printer
        if printer is None or printer.caps is None:
            return
        can = printer.caps.can_borderless(
            self.size_combo.get_active_id() or "", self.type_combo.get_active_id() or None
        )
        self.borderless.set_sensitive(can and not self.ctx.printing.busy)
        self.borderless_note.set_text("" if can else "Not available for this paper")

    def on_pages_choice(self, key):
        """Show the range box for Range…"""
        self.range_entry.set_visible(key == "range")
        if key == "range":
            self.range_entry.grab_focus()
        self.update_summary()

    def choices(self):
        """The current choices as a dict (also what profiles store)"""
        return {
            "size": self.size_combo.get_active_id(),
            "type": self.type_combo.get_active_id() or "",
            "borderless": self.borderless.get_active() == "on",
            "color": self.color.get_active(),
            "quality": self.quality.get_active(),
            "copies": int(self.copies.get_value()),
            "scaling": self.scaling.get_active(),
        }

    def apply_choices(self, choices):
        """Set the controls from a dict (profiles); unsupported choices are skipped"""
        caps = self.printer.caps if self.printer else None
        if "color" in choices:
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
            self.borderless.set_active("on" if choices["borderless"] else "off")
        self.update_availability()
        self.update_summary()

    def selected_pages(self):
        """1-based pages to print (RenderError for a bad range)"""
        doc = self.ctx.printing.document
        if not doc:
            return []
        return select_pages(
            self.pages.get_active(),
            doc["pages"],
            self.range_entry.get_text(),
            current=self.ctx.preview_page or 1,
        )

    def ticket(self):
        """The job ticket for the current choices"""
        return self.ctx.printing.ticket(self.printer, self.choices())

    def update_summary(self):
        """Show exactly what will print"""
        if self._loading or self.printer is None or self.printer.caps is None:
            self.summary.set_text("")
            return
        doc = self.ctx.printing.document
        try:
            pages = self.selected_pages() if doc else []
        except RenderError as e:
            self.summary.set_text(str(e))
            return
        ticket = self.ticket()
        text = self.ctx.printing.summary(ticket, pages or [1], self.printer)
        where = (
            f" → {self.ctx.settings.get('pdf_folder')}"
            if self.printer.virtual and self.printer.key == "pdf:"
            else ""
        )
        self.summary.set_text(
            f"Will print: {text}{where}" if doc else f"Will print: {text} (open a document first)"
        )
        self.ctx.emit("ticket-changed")

    # -- document --------------------------------------------------------------------
    def choose_document(self):
        """File dialog for a document"""
        dlg = Gtk.FileChooserDialog(
            title="Open a document to print", transient_for=self.ctx.window, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.ACCEPT)
        flt = Gtk.FileFilter()
        flt.set_name("Documents (PDF, images, text)")
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

    def open_document(self, path):
        """Prepare a document (in the background) and show it"""
        self.doc_label.set_text(f"Opening {os.path.basename(path)}…")

        def done(doc):
            self.doc_label.get_style_context().remove_class("muted")
            self.doc_label.set_text(f"{os.path.basename(doc['path'])} · {doc['pages']} page(s)")
            self.set_status("")
            self.update_summary()
            self.ctx.emit("document-changed", doc)

        def failed(message):
            self.doc_label.set_text("No document yet. Open one, or drop a file here.")
            self.set_status(message, "status-error")

        self.ctx.printing.open_async(path, done, failed)

    # -- printing --------------------------------------------------------------------
    def on_print(self):
        """Check, confirm warnings, and print"""
        printer, doc = self.printer, self.ctx.printing.document
        if printer is None:
            return
        if not doc:
            self.set_status("Open a document first (Open…, or drop a file on this page).", "status-error")
            return
        try:
            pages = self.selected_pages()
        except RenderError as e:
            self.set_status(str(e), "status-error")
            return
        ticket = self.ticket()
        warnings = (
            self.ctx.features.before_print(
                self.ctx, printer, ticket, self.last_status or ("ok", "", "idle", [], [])
            )
            if self.ctx.features
            else []
        )
        if warnings and not self._confirm("Print anyway?", " ".join(warnings)):
            return
        self.set_busy(True, printing=True)
        self.progress.pulse()
        self.set_status(f"Sending {len(pages)} page(s) to {printer.name}…", "status-busy")
        self._pulse = GLib.timeout_add(200, lambda: self.progress.pulse() or True)
        self.ctx.printing.print_async(
            printer,
            ticket,
            pages,
            lambda text: self.set_status(text, "status-busy"),
            lambda r: self.on_done(printer, ticket, r),
            self.on_error,
        )

    def _stop_pulse(self):
        """Stop the progress animation"""
        if getattr(self, "_pulse", None):
            GLib.source_remove(self._pulse)
            self._pulse = None

    def on_done(self, printer, ticket, result):
        """Report the result"""
        self._stop_pulse()
        self.set_busy(False)
        state = result.get("state")
        self.progress.set_fraction(1 if state == "completed" else 0)
        if result.get("file"):
            self.set_status(f"Saved as PDF: {result['file']}", "status-ok")
        elif state == "completed":
            self.set_status(f"Printed on {printer.name}.", "status-ok")
        elif state == "canceled":
            self.set_status("Cancelled.", "muted")
        elif state == "aborted":
            self.set_status(
                "The printer stopped the job. Check its display or lights, then try again.", "status-error"
            )
        else:
            self.set_status("Sent to the printer. See Queue for its progress.", "status-ok")
        if self.ctx.features:
            self.ctx.features.after_print(self.ctx, printer, ticket, result)
        self.ctx.emit("documents-changed")
        self.ctx.emit("jobs-changed")
        self.check_status()

    def on_error(self, message):
        """Show a print problem"""
        self._stop_pulse()
        self.set_busy(False)
        self.progress.set_fraction(0)
        self.set_status(message, "status-error")
        self.check_status()

    def _confirm(self, title, detail):
        """Modal OK/Cancel question"""
        dlg = Gtk.MessageDialog(
            transient_for=self.ctx.window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=title,
        )
        dlg.format_secondary_text(detail)
        ok = dlg.run() == Gtk.ResponseType.OK
        dlg.destroy()
        return ok

    def on_shown(self):
        """Refresh the status when the page is opened"""
        self.check_status()
