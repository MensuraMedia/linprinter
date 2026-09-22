"""
Printers Found Page (sidebar: Printers)
Every printer LinPrinter can see: identity, how it is reached (methods in
fallback order), USB connection, what it can do, its state in plain words,
ink levels drawn in the cartridges' own colours, firmware, Identify (the
printer flashes) and a link to the printer's own page. Check for printers
again re-runs the search. Setup and test: the printer's own defaults (use them
in LinPrinter), built-in test pages, and the printer's maintenance pages.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from backends.backend_base import type_label  # noqa: E402
from backends.usb_probe import speed_label  # noqa: E402
from config.config_print import COLOR_MODES, PDF_PRINTER_ID, QUALITIES, SCALING  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")


def tilde(text):
    """Text with the home folder shown as ~"""
    home = os.path.expanduser("~")
    return text.replace(home, "~", 1) if home and home != "/" else text


LEVEL_CSS = {"ok": "status-ok", "warn": "status-busy", "error": "status-error"}


class InkGauge(Gtk.DrawingArea):
    """One cartridge: a bar filled to its level in the cartridge's colours"""

    def __init__(self, marker):
        super().__init__()
        self.marker = marker
        self.set_size_request(220, 22)
        self.connect("draw", self.on_draw)
        level = marker.get("level", -1)
        self.set_tooltip_text(
            f"{marker['name']}: {level} %" if level >= 0 else f"{marker['name']}: level unknown"
        )

    def on_draw(self, _widget, cr):
        """Frame, then one stripe per colour up to the level"""
        w, h = self.get_allocated_width(), self.get_allocated_height()
        level = max(0, min(100, self.marker.get("level", 0)))
        colours = (
            [c for c in self.marker.get("colors", []) if c.lower() != "#000000"]
            or self.marker.get("colors", [])
            or ["#808080"]
        )
        fill = (w - 2) * level / 100
        stripe = h / len(colours)
        for n, hexc in enumerate(colours):
            rgba = Gdk.RGBA()
            rgba.parse(hexc)
            cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1)
            cr.rectangle(1, n * stripe + 1, fill, stripe - (1 if n == len(colours) - 1 else 0))
            cr.fill()
        cr.set_source_rgba(0.55, 0.55, 0.55, 1)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, w - 1, h - 1)
        cr.stroke()


class PrintersPage(BasePage):
    """Printers Found"""

    def build_content(self):
        """Title, check-again button, summary and one section per printer"""
        self.add_title(
            "Printers Found",
            "Printers LinPrinter can see, how it reaches each one, what they can do, and their ink.",
        )
        row = Gtk.Box(spacing=10)
        self.check_btn = Gtk.Button(label="Check for printers again")
        self.check_btn.get_style_context().add_class("primary-pill")
        self.check_btn.connect("clicked", lambda *_: self.ctx.emit("request-printer-refresh"))
        row.pack_start(self.check_btn, False, False, 0)
        self.summary = self.label("", "muted")
        row.pack_start(self.summary, False, False, 6)
        self.pack_start(row, False, False, 0)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.pack_start(self.list_box, False, False, 0)
        self.status_labels = {}
        self.ink_boxes = {}
        self.test_labels = {}
        self.ctx.on("printers-changed", self.show_printers)
        self.ctx.on("printer-status", self.on_status)

    def show_printers(self, printers=None):
        """One section per printer"""
        printers = printers if printers is not None else self.ctx.printing.printers
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        self.status_labels, self.ink_boxes, self.test_labels = {}, {}, {}
        real = [p for p in printers if p.key != PDF_PRINTER_ID and p.methods]
        self.summary.set_text(
            f"{len(real)} printer(s) ready to print, plus Print to PDF."
            if real
            else "No printer found. Check the cable and power. Print to PDF is always available."
        )
        for p in printers:
            self.list_box.pack_start(self.section(p), False, False, 0)
            if p.methods:
                self.ctx.printing.status_async(p, lambda st, p=p: self.on_status(p, st))
        self.list_box.show_all()

    def section(self, p):
        """Card for one printer"""
        box, inner = self.make_card(p.name)
        row = Gtk.Box(spacing=10)
        status = self.label(
            "Checking…" if p.methods else p.hint, "muted" if p.methods else "status-error", wrap=True
        )
        self.status_labels[p.id] = status
        if p.caps and p.caps.identify:
            ident = Gtk.Button(label="Identify")
            ident.set_tooltip_text("Make the printer flash so you can see which one it is")
            ident.connect("clicked", lambda *_: self.identify(p, status))
            row.pack_start(ident, False, False, 0)
        row.pack_start(status, True, True, 0)
        inner.pack_start(row, False, False, 0)
        if p.caps and p.caps.alert:
            inner.pack_start(
                self.label(f"Printer says: {p.caps.alert}", "status-busy", wrap=True), False, False, 0
            )

        grid = Gtk.Grid(column_spacing=18, row_spacing=3)
        rows = self.rows(p)
        n = 0
        for title, items in rows:
            head = self.label(title, "secondary")
            head.set_margin_top(8)
            grid.attach(head, 0, n, 2, 1)
            n += 1
            for key, value in items:
                grid.attach(self.label(key, "info-key"), 0, n, 1, 1)
                val = self.label(value, "info-value", wrap=True, selectable=True)
                val.set_hexpand(True)
                grid.attach(val, 1, n, 1, 1)
                n += 1
        inner.pack_start(grid, False, False, 0)
        ink = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.ink_boxes[p.id] = ink
        inner.pack_start(ink, False, False, 0)
        if p.methods and p.key != PDF_PRINTER_ID:
            inner.pack_start(self.setup_section(p), False, False, 0)
        return box

    def setup_section(self, p):
        """Setup and test: the printer's defaults, test pages, maintenance links"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        head = self.label("Setup and test", "secondary")
        head.set_margin_top(10)
        box.pack_start(head, False, False, 0)

        defaults = self.ctx.printing.printer_defaults(p)
        row = Gtk.Box(spacing=10)
        key = self.label("Printer's defaults", "info-key")
        key.set_size_request(120, -1)
        row.pack_start(key, False, False, 0)
        row.pack_start(
            self.label(self.describe_defaults(p, defaults) or "not reported", "info-value", wrap=True),
            False,
            False,
            0,
        )
        use = Gtk.Button(label="Use in LinPrinter")
        use.set_tooltip_text(
            "Start the Print page with the printer's own defaults (you can still change them for each job)"
        )
        use.set_sensitive(bool(defaults))
        use.connect("clicked", lambda *_: self.use_defaults(p))
        row.pack_end(use, False, False, 0)
        box.pack_start(row, False, False, 0)

        row = Gtk.Box(spacing=8)
        key = self.label("Test the printer", "info-key")
        key.set_size_request(120, -1)
        row.pack_start(key, False, False, 0)
        for kind, text, tip in (
            (
                "quality",
                "Print quality page",
                "Colour and grey blocks, fine lines, a gradient and text: shows streaks, gaps, colour casts and margins",
            ),
            (
                "lines",
                "Print line page",
                "Line fields for each ink and alignment crosses: shows blocked nozzles and misalignment",
            ),
        ):
            btn = Gtk.Button(label=text)
            btn.set_tooltip_text(tip + ". Uses one sheet of plain paper.")
            btn.connect("clicked", lambda _b, k=kind: self.print_test(p, k))
            row.pack_start(btn, False, False, 0)
        look = Gtk.Button(label="Look first")
        look.set_tooltip_text(
            "Open the quality page on the Print page, so you can preview it or change the options first"
        )
        look.connect("clicked", lambda *_: self.open_test(p))
        row.pack_start(look, False, False, 0)
        box.pack_start(row, False, False, 0)
        test_status = self.label("", "muted", wrap=True)
        test_status.set_no_show_all(True)  # only takes space once it has something to say
        test_status.connect("notify::label", lambda lbl, _p: lbl.set_visible(bool(lbl.get_text())))
        self.test_labels[p.id] = test_status
        box.pack_start(test_status, False, False, 0)

        caps = p.caps
        links = caps.links if caps else {}
        row = Gtk.Box(spacing=8)
        key = self.label("Maintenance", "info-key")
        key.set_size_request(120, -1)
        row.pack_start(key, False, False, 0)
        for link, text in (("settings", "Printer settings and maintenance"), ("ink", "Ink details")):
            btn = Gtk.Button(label=text)
            uri = links.get(link)
            if p.virtual:
                btn.set_sensitive(False)
                btn.set_tooltip_text("Not available on the test printer")
            elif uri:
                btn.set_tooltip_text(
                    "The printer's own page, served on this computer over the USB cable (ipp-usb); nothing goes on the network"
                )
                btn.connect("clicked", lambda _b, u=uri: Gio.AppInfo.launch_default_for_uri(u, None))
            else:
                btn.set_sensitive(False)
                btn.set_tooltip_text("This printer has no page of its own")
            row.pack_start(btn, False, False, 0)
        box.pack_start(row, False, False, 0)
        if links or p.virtual:
            box.pack_start(
                self.label(
                    "Cleaning, nozzle check, head alignment, quiet mode, the power-off timer and the printer's other "
                    "settings are on the printer's own page. The printer doesn't let other programs change them directly.",
                    "muted",
                    wrap=True,
                ),
                False,
                False,
                0,
            )
        return box

    @staticmethod
    def describe_defaults(p, d):
        """Printer defaults in words"""
        parts = []
        if d.get("color"):
            parts.append(COLOR_MODES.get(d["color"], d["color"]))
        if d.get("quality"):
            parts.append(QUALITIES.get(d["quality"], d["quality"]))
        if d.get("size") and p.caps.size(d["size"]):
            parts.append(p.caps.size(d["size"]).label)
        if d.get("type"):
            parts.append(type_label(d["type"]))
        if d.get("scaling"):
            parts.append(SCALING.get(d["scaling"], d["scaling"]))
        return " · ".join(parts)

    def use_defaults(self, p):
        """Make the printer's defaults LinPrinter's starting choices"""
        choices = self.ctx.printing.use_printer_defaults(p)
        page = self.ctx.nav.get_page_widget("print")
        if page.printer is p:
            page.apply_choices(choices)
        self.ctx.emit("settings-changed", "printer-defaults")
        self.test_labels[p.id].set_text("The Print page now starts with the printer's defaults.")

    def print_test(self, p, kind):
        """Confirm, then print a test page"""
        from modules.manager_testpage import KINDS

        label = self.test_labels[p.id]
        if self.ctx.printing.busy:
            label.set_text("Wait for the current job to finish first.")
            return
        ticket = self.ctx.printing.test_ticket(p, kind)
        size = p.caps.size(ticket["size"]) if p.caps else None
        dlg = Gtk.MessageDialog(
            transient_for=self.ctx.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Print the {KINDS[kind].lower()} on {p.name}?",
        )
        dlg.format_secondary_text(
            f"It uses one sheet of {size.label if size else ticket['size']} plain paper and a little ink. Load paper first."
        )
        ok = dlg.run() == Gtk.ResponseType.OK
        dlg.destroy()
        if not ok:
            return
        label.get_style_context().remove_class("status-error")
        label.set_text("Preparing the test page…")

        def done(result):
            ok = result.get("state") in ("completed", "processing")
            label.set_text(
                f"Test page {'printed' if result.get('state') == 'completed' else 'sent'}. Compare it with the notes on the page."
                if ok
                else "The printer stopped the test page. Check its display or lights."
            )
            self.ctx.emit("jobs-changed")

        def failed(message):
            label.get_style_context().add_class("status-error")
            label.set_text(message)

        self.ctx.printing.print_test_page(p, kind, lambda t: label.set_text(t), done, failed, ticket=ticket)

    def open_test(self, p):
        """Put the quality test page on the Print page"""
        from modules.manager_testpage import make_test_page

        ticket = self.ctx.printing.test_ticket(p)
        path = make_test_page(
            "quality",
            os.path.join(self.ctx.printing.session_dir, "tests", "linprinter-test-page.pdf"),
            ticket["size_mm"],
            ticket["margins_mm"],
            p.name,
            ticket,
            p.firmware,
        )
        page = self.ctx.nav.get_page_widget("print")
        self.ctx.nav.navigate_to("print")
        page.open_document(path)

    def rows(self, p):
        """(section, [(key, value)]) for a printer"""
        out = [
            (
                "Connection",
                [
                    (f"{n + 1}.", tilde(m.label) if m.code == "PDF" else m.label)
                    for n, m in enumerate(p.methods)
                ]
                or [("Methods", "none yet")],
            )
        ]
        if p.usb:
            u = p.usb
            out[0][1].extend(
                [
                    ("USB", f"{u.usb_id} · port {u.port_path} · {speed_label(u.speed_mbps)}"),
                    ("Printer class", ", ".join(u.kinds) or "—"),
                    ("Kernel driver", ", ".join(u.drivers) or "none (ipp-usb talks to it directly)"),
                ]
            )
        caps = p.caps
        if caps:
            sizes = ", ".join(s.label for s in caps.sizes[:12]) + (
                f" (+{len(caps.sizes) - 12} more)" if len(caps.sizes) > 12 else ""
            )
            items = [
                ("Paper sizes", sizes or "—"),
                ("Paper types", ", ".join(type_label(t) for t in caps.types) or "any (not needed for a PDF)"),
                ("Color", ", ".join(COLOR_MODES.get(c, c) for c in caps.colors)),
                ("Quality", ", ".join(QUALITIES.get(q, q) for q in caps.qualities)),
                ("Copies", f"1–{caps.copies_max}" if caps.copies_max > 1 else "1"),
                ("Two-sided", "yes" if any(s != "one-sided" for s in caps.sides) else "no (one-sided only)"),
                (
                    "Borderless",
                    f"yes, {len({s for s, _ in caps.borderless})} sizes" if caps.borderless else "no",
                ),
            ]
            if caps.custom_range:
                (a, b), (c, d) = caps.custom_range
                items.append(("Custom size", f"{a:g} × {b:g} mm to {c:g} × {d:g} mm"))
            out.append(("Capabilities", items))
        details = []
        if p.firmware:
            details.append(("Firmware", p.firmware))
        if caps and caps.raw.get("printer-make-and-model"):
            details.append(("Model", caps.raw["printer-make-and-model"]))
        if details:
            out.append(("Device", details))
        return out

    def on_status(self, printer, status):
        """Show a printer's state and ink"""
        label = self.status_labels.get(printer.id)
        if label is None:
            return
        level, message, _state, _reasons, markers = status
        ctx = label.get_style_context()
        for c in ("muted", *LEVEL_CSS.values()):
            ctx.remove_class(c)
        ctx.add_class(LEVEL_CSS.get(level, "muted"))
        label.set_text(message)
        box = self.ink_boxes.get(printer.id)
        if box is not None and markers:
            for child in box.get_children():
                box.remove(child)
            box.pack_start(self.label("Ink", "secondary"), False, False, 0)
            for m in markers:
                row = Gtk.Box(spacing=10)
                name = self.label(m["name"], "info-key")
                name.set_size_request(120, -1)
                row.pack_start(name, False, False, 0)
                row.pack_start(InkGauge(m), False, False, 0)
                level_text = f"{m['level']} %" if m.get("level", -1) >= 0 else "unknown"
                row.pack_start(self.label(level_text, "info-value"), False, False, 0)
                box.pack_start(row, False, False, 0)
            box.show_all()

    def identify(self, printer, label):
        """Make the printer flash"""

        def done(_):
            label.set_text("The printer should be flashing now.")

        self.ctx.printing._in_thread(
            lambda: self.ctx.printing.identify(printer), done, lambda e: label.set_text(e)
        )

    def on_shown(self):
        """Refresh the sections when opened"""
        self.show_printers()
