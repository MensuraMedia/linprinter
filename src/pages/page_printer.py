"""
Printer Page (2026 redesign: health first, then upkeep and details)
The chosen printer (the one on the Print page):
- the status hero: Ready · Busy · Needs you · Can't reach, what it means and
  the next step;
- Ink and paper, Connection (port, route, link errors from the kernel log, the
  last link test, the system queue), Look after the printer (test pages, the
  printer's own settings page);
- the printer's own defaults (use them in LinPrinter) and the details;
- a stray system queue, with the command that removes it;
- the Troubleshooter: guided steps, cheapest first (cable first), each with
  what LinPrinter measures right now.

Nothing here changes the system without asking: Reconnect and removing a queue
state their scope first, and the system asks for the password itself.
"""

import os
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from backends import usb_link  # noqa: E402
from backends.backend_base import type_label  # noqa: E402
from backends.usb_probe import speed_label  # noqa: E402
from config.config_print import COLOR_MODES, PDF_PRINTER_ID, QUALITIES, SCALING, STATUS_EVERY  # noqa: E402
from lintheme import status as lt_status  # noqa: E402
from lintheme import tokens  # noqa: E402
from lintheme.gtk3 import components as ui  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from modules.manager_status import chip_key  # noqa: E402
from utils.util_files import tilde  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

EVERY_WORDS = f"LinPrinter checks every {STATUS_EVERY} s while this page is open."

# each step's heading
STEP_TITLES = [
    "Check the power and cable",
    "Try another USB cable",
    "Test the link",
    "Power-cycle the printer",
    "Try another socket",
    "Check the system queues",
]
STEPS = [
    "Power and cable seated",
    "Another USB cable",
    "Test the link",
    "Power-cycle",
    "Another socket",
    "System queues",
]
INK = tokens.INK


def marker_colours(marker):
    """A cartridge's colours for its gauge (the printer reports them; black stays black)"""
    cols = [c for c in marker.get("colors", []) if c.lower() != "#000000"] or marker.get("colors", [])
    return cols or [INK["black"]]


class PrinterPage(BasePage):
    """Health, upkeep, details, and the Troubleshooter"""

    def build_content(self):
        ui.css(self, "lt-page")
        for setter in (
            self.set_margin_start,
            self.set_margin_end,
            self.set_margin_top,
            self.set_margin_bottom,
        ):
            setter(0)
        self.set_spacing(16)
        self.printer = None
        self.status = None
        self.last_test = None
        self.previous_test = None
        self.stack = Gtk.Stack()
        self.stack.set_vhomogeneous(False)
        self.overview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.trouble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.stack.add_named(self.overview, "overview")
        self.stack.add_named(self.trouble, "trouble")
        self.pack_start(self.stack, True, True, 0)
        self.step = 0
        self._notice = (None, "")  # kept across rebuilds; shown in the overview and the Troubleshooter
        self._testing = False
        self._awaiting = False  # the Troubleshooter waits for the printer's answer after "Check now"
        self.resolved = False
        self.notice = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.trouble_notice = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.checked_at = 0.0
        self._give_up = None
        GLib.timeout_add_seconds(1, self.tick)
        self.ctx.on("printer-selected", self.on_printer)
        self.ctx.on("printer-status", self.on_status)
        self.ctx.on("printers-changed", lambda *_: self.rebuild())
        self.rebuild()

    # -- events --------------------------------------------------------------------------
    def on_printer(self, printer):
        if printer is None or self.printer is None or printer.id != self.printer.id:
            self.last_test = self.previous_test = None  # a test belongs to its printer
        self.printer = printer
        self.status = None
        self.rebuild()

    def on_status(self, printer, status):
        if printer is not self.printer:
            return
        changed = self.status is None or self.status[:2] != status[:2] or self.status[4] != status[4]
        self.status = status
        self.checked_at = time.monotonic()
        if self._awaiting and self.key() in ("ok", "busy", "attention"):
            self._awaiting = False
            self._cancel_give_up()
            self.resolved = True
            changed = True
        if changed:
            self.rebuild()

    def tick(self):
        """Keep "Checked N s ago" true while the page is open (the Print page asks the printer)"""
        label = getattr(self, "_checked", None)
        if label is not None and self.checked_at and self.get_mapped():
            secs = int(time.monotonic() - self.checked_at)
            ago = "Checked just now." if secs < 2 else f"Checked {secs} s ago."
            label.set_text(f"{ago} {EVERY_WORDS}")
        return True

    def key(self):
        """The lintheme status key of the chosen printer"""
        p = self.printer
        if p is None:
            return "none"
        if not p.methods:
            return "error"
        if self.status is None:
            return "busy" if self.ctx.printing.busy else "checking"
        return chip_key(self.status[0], self.status[2], self.status[3])

    def rebuild(self):
        """Redraw whichever view is showing"""
        if self.stack.get_visible_child_name() == "trouble":
            self.build_trouble()
        else:
            self.build_overview()

    @staticmethod
    def _clear(box):
        for child in box.get_children():
            box.remove(child)

    # -- overview --------------------------------------------------------------------------
    def build_overview(self):
        self._clear(self.overview)
        p = self.printer
        if p is None:
            self.overview.pack_start(
                ui.EmptyState(
                    "magnifying-glass",
                    "No printer yet",
                    "Plug a printer in by USB and switch it on; LinPrinter finds it by itself. Print to PDF works meanwhile.",
                    ("Search again", lambda: self.ctx.emit("request-printer-refresh")),
                ),
                True,
                True,
                0,
            )
            self.overview.show_all()
            return
        pdf = p.virtual and p.key == PDF_PRINTER_ID
        self.notice = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.overview.pack_start(self.hero(p, pdf), False, False, 0)
        self.overview.pack_start(self.notice, False, False, 0)
        self._show_notice(self.notice)
        for note in p.notes:
            if "queue" in note.lower():
                cmd = note.split("Remove it with: ")[-1] if "Remove it with: " in note else ""
                self.overview.pack_start(
                    ui.Banner(
                        "attention",
                        GLib.markup_escape_text(note.split(" Remove it with:")[0]),
                        [("Remove it…", lambda c=cmd: self.remove_queue(c), None)] if cmd else [],
                    ),
                    False,
                    False,
                    0,
                )
        if pdf:
            card = ui.Card("Print to PDF")
            card.add_row(
                ui.key_values(
                    [("Saves into", tilde(self.ctx.settings.get("pdf_folder"))), ("Paper", "any size")]
                )
            )
            change = ui.button(
                "Change folder in Settings", lambda: self.ctx.nav.navigate_to("settings"), small=True
            )
            change.set_halign(Gtk.Align.START)
            card.add_row(change)
            self.overview.pack_start(card, False, False, 0)
            self.overview.show_all()
            return
        self.top_cards = ui.card_flow([self.ink_card(p), self.connection_card(p), self.care_card(p)], 3)
        self.overview.pack_start(self.top_cards, False, False, 0)
        self.overview.pack_start(
            ui.card_flow([self.defaults_card(p), self.details_card(p)], 2), False, False, 0
        )
        self.overview.show_all()

    def hero(self, p, pdf):
        key = self.key()
        self._checked = None
        if pdf:
            return ui.Hero(
                "ok", "Ready", (f"Print to PDF · saves into {tilde(self.ctx.settings.get('pdf_folder'))}",)
            )
        port = p.usb.port_path if p.usb else (self.ctx.printing.remembered_usb() or {}).get("port", "")
        where = f"USB port {port}" if port else "USB"
        if p.usb:
            where += f" · {speed_label(p.usb.speed_mbps)}"
        route = (
            "printing directly"
            if any(m.code in ("P1", "T") for m in p.methods)
            else "through the system queue"
        )
        message = self.status[1] if self.status else (p.hint or "")
        if key == "checking":
            return ui.Hero("busy", "Checking", (f"{p.name} · asking the printer how it is…",))
        if key == "error":
            stats = usb_link.cached()
            usb_id = p.usb.usb_id if p.usb else (self.ctx.printing.remembered_usb() or {}).get("id", "")
            failing = usb_link.failing_ports(stats, usb_id, port) or usb_link.unidentified_failing_ports(
                stats
            )
            if failing:
                lines = [usb_link.advice(failing[-1], stats).split(" Try another")[0], lt_status.CABLE_FIRST]
            elif not p.methods and p.hint:
                lines = [p.hint]
            else:
                lines = [
                    "The printer doesn't answer: it may be off, or its USB connection may be failing.",
                    lt_status.CABLE_FIRST,
                ]
            return ui.Hero(
                "error",
                "Can't reach",
                tuple(lines),
                (
                    ("Start troubleshooter", self.start_troubleshooter, "primary"),
                    ("Test connection", self.run_test, None),
                ),
            )
        if key == "attention":
            return ui.Hero(
                "attention",
                "Needs you",
                (message, "LinPrinter checks again by itself."),
                (("Check again", self.check_again, None),),
            )
        if key == "busy":
            return ui.Hero(
                "busy",
                "Busy",
                (f"{p.name} · {where} · printing",),
                (("Show in Activity", lambda: self.ctx.nav.navigate_to("activity"), None),),
            )
        actions = []
        if p.caps and p.caps.identify:
            actions.append(("Identify", self.identify, None))
        actions.append(("Check again", self.check_again, None))
        hero = ui.Hero(
            "ok",
            "Ready",
            (f"{p.name} · {where} · {route}", f"Checked just now. {EVERY_WORDS}"),
            tuple(actions),
        )
        self._checked = hero.lines[-1]
        self.tick()
        return hero

    def set_notice(self, kind, message):
        """A message kept across rebuilds, shown in the overview and in the Troubleshooter"""
        self._notice = (kind, message)
        for box in (self.notice, self.trouble_notice):
            self._show_notice(box)

    def _show_notice(self, box):
        self._clear(box)
        kind, message = self._notice
        if kind:
            box.pack_start(ui.Banner(kind, GLib.markup_escape_text(message)), False, False, 0)
            box.show_all()

    @staticmethod
    def _w(words, *classes):
        """Wrapped text that doesn't push cards wider (card rows reflow by natural width)"""
        label = ui.text(words, *classes, wrap=True)
        label.set_max_width_chars(32)
        return label

    def ink_card(self, p):
        card = ui.Card("Ink and paper")
        markers = self.status[4] if self.status else []
        low = int(self.ctx.settings.get("low_ink_percent") or 0)
        if markers:
            for m in markers:
                level = m.get("level", -1)
                name = {"Color": "Colour"}.get(m["name"], m["name"])  # the app's words
                card.add_row(ui.Gauge(name, level if level >= 0 else None, marker_colours(m), low_at=low))
        else:
            card.add_row(self._w("The printer hasn't reported its ink yet.", "lt-muted"))
        rows = []
        caps = p.caps
        ready = caps.raw.get("media-ready") if caps else None
        if isinstance(ready, list):
            ready = ready[0] if ready else None
        if ready and caps.size(ready):
            rows.append(("Paper", caps.size(ready).label.split(" (")[0]))
        rows.append(("Warn at", f"{low}% (Settings)"))
        card.add_row(ui.key_values(rows))
        if self.key() == "error" and markers:
            card.add_row(self._w("Last known levels; the printer isn't answering now.", "lt-caption"))
        link = caps.links.get("ink") if caps else None
        if link and not p.virtual:
            b = ui.button("Ink details on the printer's page", lambda u=link: self.open_uri(u), small=True)
            b.set_halign(Gtk.Align.START)
            b.set_tooltip_text("The printer's own page, served on this computer over the USB cable")
            card.add_row(b)
        return card

    def connection_card(self, p):
        card = ui.Card("Connection")
        port = p.usb.port_path if p.usb else (self.ctx.printing.remembered_usb() or {}).get("port", "")
        rows, classes = [], {}
        if p.usb:
            rows.append(("Port", f"{port} · {speed_label(p.usb.speed_mbps)}"))
        elif port:
            rows.append(("Port", f"{port} (not on USB now)"))
        route = next((m for m in p.methods if m.code in ("P1", "T")), None)
        rows.append(
            ("Route", "Direct, driverless IPP" if route else ("System queue" if p.methods else "None yet"))
        )
        if p.usb or port:
            stats = usb_link.cached()
            s = stats.get(port) or {"errors": 0, "disconnects": 0}
            if usb_link.failing(port, stats):
                rows.append(("Link errors", f"{s['errors']} errors, {s['disconnects']} drops"))
                classes["Link errors"] = "lt-error-text"
            elif usb_link.log_readable() is None:
                rows.append(("Link errors", "Checking…"))
                classes["Link errors"] = "lt-muted"
            elif not usb_link.log_readable():
                rows.append(("Link errors", "Unknown (kernel log not readable)"))
                classes["Link errors"] = "lt-muted"
            else:
                rows.append(("Link errors", "None in 10 min"))
                classes["Link errors"] = "lt-ok-text"
        if self.last_test:
            t = self.last_test
            stale = self.key() == "error"  # a result from before it stopped answering isn't good news now
            rows.append(("Last test", f"{t['failed']} of {t['asked']} failed · {self._clock(t['when'])}"))
            classes["Last test"] = "lt-muted" if stale else ("lt-error-text" if t["failed"] else "lt-ok-text")
        cups = next((m for m in p.methods if m.code == "P2"), None)
        stray = any("queue" in n.lower() for n in p.notes)
        rows.append(
            ("System queue", "Points somewhere else" if stray else ("OK, points here" if cups else "None"))
        )
        if stray:
            classes["System queue"] = "lt-attention-text"
        card.add_row(ui.key_values(rows, classes))
        if self.last_test and self.key() == "error":  # its own line: a long value would widen the card
            card.add_row(self._w("The last test is from before it stopped answering.", "lt-caption"))
        buttons = Gtk.Box(spacing=8)
        test = ui.button("Testing…" if self._testing else "Test connection", self.run_test, small=True)
        test.set_tooltip_text(
            "Ask the printer 20 small questions and count failures. Nothing is printed or changed."
        )
        test.set_sensitive(route is not None and not self._testing)
        buttons.pack_start(test, False, False, 0)
        if p.usb or port:
            rec = ui.button("Reconnect…", self.reconnect, small=True)
            rec.set_tooltip_text("Re-attach the printer to the computer (asks first, then for your password)")
            buttons.pack_start(rec, False, False, 0)
        card.add_row(buttons)
        return card

    def care_card(self, p):
        card = ui.Card("Look after the printer")
        self.care_status = ui.text("", "lt-muted")
        reachable = self.key() in ("ok", "busy", "attention", "checking") and bool(p.methods)
        if not reachable:  # as in the mockup: the reason and the way out, not dead buttons
            card.add_row(
                self._w(
                    "Test pages, cleaning and the printer's own page need a working connection. "
                    "Fix the connection first.",
                    "lt-muted",
                )
            )
            fix = ui.button("Open the troubleshooter", self.start_troubleshooter, small=True)
            fix.set_halign(Gtk.Align.START)
            card.add_row(fix)
            return card
        links = p.caps.links if p.caps else {}
        items = [
            (
                "Print a quality page",
                "Colour blocks, grey ramp, fine lines",
                lambda: self.print_test(p, "quality"),
            ),
            ("Print a line page", "Checks alignment for each ink", lambda: self.print_test(p, "lines")),
            ("Look first", "Preview a test page before printing it", lambda: self.open_test(p)),
        ]
        if links.get("settings") and not p.virtual:
            items.append(
                (
                    "Printer's own settings page",
                    "Cleaning, alignment, power-off timer",
                    lambda: self.open_uri(links["settings"]),
                )
            )
        for title, detail, action in items:
            b = ui.css(Gtk.Button(), "lt-list-btn")
            b.add(ui.vbox(self._w(title, "lt-strong"), self._w(detail, "lt-caption"), spacing=0))
            b.connect("clicked", lambda *_a, a=action: a())
            ui.name(b, f"{title}: {detail}")
            card.add_row(b)
        return card

    def defaults_card(self, p):
        card = ui.Card("The printer's own defaults")
        defaults = self.ctx.printing.printer_defaults(p) if p.caps else {}
        card.add_row(self._w(self.describe_defaults(p, defaults) or "Not reported"))
        use = ui.button("Use these in LinPrinter", lambda: self.use_defaults(p), small=True)
        use.set_halign(Gtk.Align.START)
        use.set_sensitive(bool(defaults))
        use.set_tooltip_text(
            "Start the Print page with the printer's own defaults (you can still change them for each job)"
        )
        card.add_row(use)
        return card

    def details_card(self, p):
        card = ui.Card()
        reveal = Gtk.Revealer()
        more = ui.button("Show all", None, kind="link")
        head = Gtk.Box()
        head.pack_start(ui.text("Details", "lt-heading"), True, True, 0)
        head.pack_end(more, False, False, 0)
        card.add_row(head)
        caps = p.caps
        if caps:
            card.add_row(
                ui.text(
                    f"{len(caps.sizes)} paper sizes · {len(caps.types)} paper types · "
                    f"{'two-sided' if any(s != 'one-sided' for s in caps.sides) else 'one-sided'} · "
                    f"1–{caps.copies_max} copies",
                    wrap=True,
                )
            )
        sub = " · ".join(
            x
            for x in (
                f"Firmware {p.firmware}" if p.firmware else "",
                caps.raw.get("printer-make-and-model", "") if caps else "",
            )
            if x
        )
        if sub:
            card.add_row(ui.text(sub, "lt-muted"))
        full = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for section, items in self.rows(p):
            full.pack_start(ui.text(section, "lt-strong"), False, False, 0)
            full.pack_start(ui.key_values(items), False, False, 0)
        reveal.add(full)
        card.add_row(reveal)

        def toggle():
            reveal.set_reveal_child(not reveal.get_reveal_child())
            more.get_child().set_text("Show less" if reveal.get_reveal_child() else "Show all")

        more.connect("clicked", lambda *_: toggle())
        return card

    # -- data (kept from 0.2.x) --------------------------------------------------------------
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
            parts.append(SCALING.get(d["scaling"], d["scaling"]).lower())
        return " · ".join(parts)

    def rows(self, p):
        """(section, [(key, value)]) for the details"""
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
            items = [
                (
                    "Paper sizes",
                    ", ".join(s.label for s in caps.sizes[:8])
                    + (f" (+{len(caps.sizes) - 8} more)" if len(caps.sizes) > 8 else ""),
                ),
                ("Paper types", ", ".join(type_label(t) for t in caps.types) or "any"),
                ("Colour", ", ".join(COLOR_MODES.get(c, c) for c in caps.colors)),
                ("Quality", ", ".join(QUALITIES.get(q, q) for q in caps.qualities)),
                (
                    "Borderless",
                    f"yes, {len({s for s, _ in caps.borderless})} sizes" if caps.borderless else "no",
                ),
            ]
            if caps.custom_range:
                (a, b), (c, d) = caps.custom_range
                items.append(("Custom size", f"{a:g} × {b:g} mm to {c:g} × {d:g} mm"))
            out.append(("Capabilities", items))
        return out

    # -- actions ------------------------------------------------------------------------------
    @staticmethod
    def _clock(ts):
        from datetime import datetime

        return datetime.fromtimestamp(ts).strftime("%H:%M")

    def open_uri(self, uri):
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as e:
            self.set_notice("error", f"Couldn't open the printer's page: {e.message}")

    def check_again(self):
        self.ctx.emit("request-printer-refresh")

    def identify(self):
        p = self.printer
        self.ctx.printing._in_thread(
            lambda: self.ctx.printing.identify(p),
            lambda _r: self.set_notice("ok", "The printer should be flashing now."),
            lambda e: self.set_notice("error", e),
        )

    def reconnect(self):
        p = self.printer
        port = p.usb.port_path if p and p.usb else (self.ctx.printing.remembered_usb() or {}).get("port", "?")
        if not ui.confirm(
            self.ctx.window,
            "Reconnect the printer?",
            f"LinPrinter re-attaches {p.name if p else 'the printer'} on USB port {port}. Nothing else is touched. "
            "Your system asks for your password in its own window.",
            "Reconnect",
        ):
            return
        self.set_notice("busy", "Re-attaching the printer…")

        def done(result):
            ok, message = result
            self.set_notice("ok" if ok else "error", message)
            if ok:
                self.ctx.emit("request-printer-refresh")

        self.ctx.printing._in_thread(
            lambda: self.ctx.printing.reconnect_usb(p), done, lambda e: self.set_notice("error", e)
        )

    def run_test(self, then=None):
        """The link test (read-only); the result goes in Connection and the Troubleshooter"""
        p = self.printer
        if p is None or self._testing:
            return
        self._testing = True
        self.set_notice("busy", "Testing the connection: 20 small questions to the printer…")
        self.rebuild()  # the test buttons show "Testing…" and can't be pressed twice

        def done(result):
            self._testing = False
            if self.printer is None or self.printer.id != p.id:
                self.set_notice(None, "")  # another printer is chosen now: this result isn't about it
                self.rebuild()
                if then:
                    then(None)
                return
            self.previous_test, self.last_test = self.last_test, result
            failed, asked = result["failed"], result["asked"]
            if failed:
                self.set_notice(
                    "error",
                    f"{failed} of {asked} questions to the printer failed. The connection is unreliable. {lt_status.CABLE_FIRST}",
                )
            else:
                self.set_notice(
                    "ok",
                    f"0 of {asked} questions failed ({result['seconds']:.1f} s). The connection is healthy.",
                )
            self.rebuild()
            if then:
                then(result)

        def failed(message):
            self._testing = False
            self.set_notice("error", message)
            self.rebuild()
            if then:
                then(None)

        self.ctx.printing._in_thread(lambda: self.ctx.printing.link_test(p), done, failed)

    def remove_queue(self, command):
        """A stray system queue: show the exact command; it needs the administrator's password"""
        dialog = Gtk.Dialog(title="Remove the system queue", transient_for=self.ctx.window, modal=True)
        ui.css(dialog, "lt-root", "lt-dialog")
        area = dialog.get_content_area()
        area.set_border_width(20)
        area.set_spacing(10)
        queue = command.split()[-1] if command else "the queue"
        area.pack_start(ui.text(f"Remove the queue “{queue}”?", "lt-heading", wrap=True), False, False, 0)
        area.pack_start(
            ui.text(
                "It sends jobs somewhere other than your printer. CUPS makes a correct one when the printer is "
                "connected. Run this command in a terminal; it asks for your password:",
                wrap=True,
            ),
            False,
            False,
            0,
        )
        area.pack_start(ui.text(command, "lt-mono", selectable=True), False, False, 0)
        ui.css(dialog.add_button("Close", Gtk.ResponseType.CANCEL), "lt-btn")
        copy = ui.css(dialog.add_button("Copy command", Gtk.ResponseType.OK), "lt-btn", "lt-primary")
        copy.grab_focus()
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(command, -1)
            self.set_notice("ok", "Command copied. Paste it in a terminal, then press Check again.")
        dialog.destroy()

    def use_defaults(self, p):
        choices = self.ctx.printing.use_printer_defaults(p)
        page = self.ctx.nav.get_page_widget("print")
        if page.printer is p:
            page.apply_choices(choices)
        self.ctx.emit("settings-changed", "printer-defaults")
        self.set_notice("ok", "The Print page now starts with the printer's defaults.")

    def print_test(self, p, kind):
        from modules.manager_testpage import KINDS

        if self.ctx.printing.busy:
            self.set_notice("attention", "Wait for the current job to finish first.")
            return
        ticket = self.ctx.printing.test_ticket(p, kind)
        size = p.caps.size(ticket["size"]) if p.caps else None
        if not ui.confirm(
            self.ctx.window,
            f"Print the {KINDS[kind].lower()}?",
            f"It uses one sheet of {size.label if size else ticket['size']} plain paper and a little ink. Load paper first.",
            "Print it",
        ):
            return
        self.set_notice("busy", "Preparing the test page…")

        def finished():
            self.ctx.emit("printing", False)
            self.ctx.nav.get_page_widget("print").check_status()  # the chip leaves Busy at once

        def failed(message):
            finished()
            if message.strip() == "Cancelled.":  # cancelled before it was sent: nothing went wrong
                self.set_notice(None, "")
            else:
                self.set_notice("error", message)

        def done(result):
            finished()
            if result.get("state") == "canceled":
                self.set_notice(None, "")
                return
            ok = result.get("state") in ("completed", "processing")
            self.set_notice(
                "ok" if ok else "error",
                (
                    f"Test page {'printed' if result.get('state') == 'completed' else 'sent'}. Compare it with the notes on the page."
                    if ok
                    else "The printer stopped the test page. Check its display or lights."
                ),
            )
            self.ctx.emit("jobs-changed")

        try:
            self.ctx.printing.print_test_page(p, kind, lambda t: None, done, failed, ticket=ticket)
        except Exception as e:  # a UI boundary: drawing the page failed before the job began
            log.warning("test page: %s", e, exc_info=True)
            self.set_notice("error", f"Couldn't prepare the test page: {e}")
            return
        self.ctx.emit("printing", True)

    def open_test(self, p):
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
        self.ctx.nav.navigate_to("print")
        self.ctx.nav.get_page_widget("print").open_document(path)

    # -- troubleshooter -------------------------------------------------------------------------
    def start_troubleshooter(self, step=0):
        self.step = step
        self.resolved = False
        self._awaiting = False
        self.set_notice(None, "")
        self.stack.set_visible_child_name("trouble")
        self.build_trouble()

    def close_troubleshooter(self):
        self._awaiting = False
        self._cancel_give_up()
        self.stack.set_visible_child_name("overview")
        self.build_overview()

    def build_trouble(self):
        self._clear(self.trouble)
        head = Gtk.Box()
        head.pack_start(
            ui.vbox(
                ui.text("Fix the printer connection", "lt-title"),
                ui.text("Cheapest checks first. Stops at the first step that works.", "lt-muted"),
                spacing=0,
            ),
            True,
            True,
            0,
        )
        close = ui.button("Close", self.close_troubleshooter)
        close.set_valign(Gtk.Align.START)
        head.pack_end(close, False, False, 0)
        self.trouble.pack_start(head, False, False, 0)
        self.trouble.pack_start(ui.StepLadder(STEPS, self.step, done=self.resolved), False, False, 0)
        self.trouble_notice = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.trouble.pack_start(self.trouble_notice, False, False, 0)
        self._show_notice(self.trouble_notice)
        body = Gtk.Grid(column_spacing=16, column_homogeneous=False)
        left = ui.Card(large=True)
        left.set_hexpand(True)
        right = self.evidence_card()
        right.set_size_request(380, -1)
        body.attach(left, 0, 0, 1, 1)
        body.attach(right, 1, 0, 1, 1)
        self.trouble.pack_start(body, False, False, 0)
        self.fill_step(left)
        self.trouble.show_all()

    def evidence_card(self):
        """What LinPrinter measures right now (honest evidence, not guesses)"""
        card = ui.Card("What LinPrinter sees now", large=True)
        p = self.printer
        port = p.usb.port_path if p and p.usb else (self.ctx.printing.remembered_usb() or {}).get("port", "")
        usb_id = p.usb.usb_id if p and p.usb else (self.ctx.printing.remembered_usb() or {}).get("id", "")
        stats = usb_link.cached()
        mine = usb_link.failing_ports(stats, usb_id, port) or usb_link.unidentified_failing_ports(stats)
        if mine:
            s = stats[mine[-1]]
            card.add_row(
                ui.Banner(
                    "error",
                    f"Port {mine[-1]}: <b>{s['errors']} connection errors, {s['disconnects']} disconnects</b> in 10 minutes.",
                )
            )
        elif p is not None and p.usb:
            if usb_link.log_readable():
                card.add_row(ui.Banner("ok", f"Port {port}: <b>no connection errors</b> in 10 minutes."))
            elif usb_link.log_readable() is None:
                card.add_row(ui.Banner("busy", f"Port {port}: reading the connection log…"))
            else:
                card.add_row(
                    ui.Banner(
                        None, f"Port {port}: connection errors <b>unknown</b> (the kernel log can't be read)."
                    )
                )
        elif p is not None and p.virtual:
            card.add_row(ui.Banner("busy", "This printer isn't a USB device, so there is no cable to check."))
        else:
            card.add_row(ui.Banner("attention", "The printer isn't on USB right now."))
        others = [
            q for q, s in stats.items() if q not in mine and s["ids"] and not usb_link.failing(q, stats)
        ]
        if others and not (p is not None and p.virtual):
            card.add_row(ui.Banner("ok", "Other USB devices on this computer: <b>no errors</b>."))
            card.add_row(
                ui.text(
                    "So the computer's USB is working. The fault is between the computer and the printer: "
                    "cable first, then the socket, then the printer's own port.",
                    "lt-muted",
                    wrap=True,
                )
            )
        if usb_link.log_readable() is False:
            card.add_row(
                ui.text(
                    "The kernel log can't be read here, so connection errors aren't known.",
                    "lt-muted",
                    wrap=True,
                )
            )
        if self.last_test:
            t = self.last_test
            card.add_row(
                ui.text(
                    f"Last link test: {t['failed']} of {t['asked']} failed · {self._clock(t['when'])}",
                    "lt-strong",
                )
            )
        return card

    def fill_step(self, card):
        step = self.step
        title = "Fixed" if self.resolved else f"Step {step + 1} of {len(STEPS)}: {STEP_TITLES[step]}"
        card.add_row(ui.text(title, "lt-heading", wrap=True))
        nxt = ("Next step", self.next_step, None)
        check = ("Check now", self.check_and_continue, "primary")
        if self._awaiting:
            card.add_row(ui.Banner("busy", "Looking for the printer… this takes a few seconds."))
            return
        if self.resolved:
            fixed_by = STEP_TITLES[step].lower()
            card.add_row(
                ui.Banner(
                    "ok",
                    f"<b>The printer answers again.</b> Fixed at step {step + 1} ({GLib.markup_escape_text(fixed_by)}).",
                )
            )
            done = ui.button(
                "Done: back to Print",
                lambda: (self.close_troubleshooter(), self.ctx.nav.navigate_to("print")),
                kind="primary",
            )
            done.set_halign(Gtk.Align.START)
            card.add_row(done)
            return
        if step == 0:
            text = "Make sure the printer is switched on and both ends of the USB cable are pushed in fully."
            buttons = [check, nxt]
        elif step == 1:
            text = (
                "A cable is the cheapest thing to rule out, and the most common cause. On this printer, two faulty "
                "cables caused every connection failure for a week, including one that worked for a few minutes."
            )
            buttons = [
                ("I've changed it: check now", self.check_and_continue, "primary"),
                ("Skip this step", self.next_step, None),
            ]
        elif step == 2:
            text = "LinPrinter asks the printer 20 small questions and counts the failures. Nothing is printed or changed."
            buttons = [("Test now", self.test_step, "primary"), nxt]
        elif step == 3:
            text = "Turn the printer off, unplug its power for 30 seconds, then turn it on and wait until it is ready."
            buttons = [("It's back on: check now", self.check_and_continue, "primary"), nxt]
        elif step == 4:
            text = "Plug the cable into another USB socket on the computer, directly, not into a hub or extension."
            buttons = [check, nxt]
        else:
            stray = [n for n in (self.printer.notes if self.printer else []) if "queue" in n.lower()]
            text = (
                "A system print queue points somewhere other than your printer: " + stray[0]
                if stray
                else "No stray system queues found. If it still doesn't print, try the printer on another computer: "
                "that tells whether its own USB port is at fault."
            )
            buttons = [check, ("Close", self.close_troubleshooter, None)]
        card.add_row(ui.text(text, wrap=True))
        if step == 1:
            steps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            for i, line in enumerate(
                (
                    "Use a short USB 2.0 printer cable (A to B), under 2 m.",
                    "Plug it straight into the computer, not into a hub or extension.",
                    "Wait a few seconds. LinPrinter notices the printer by itself.",
                ),
                start=1,
            ):
                steps.pack_start(ui.text(f"{i}. {line}", wrap=True), False, False, 0)
            card.add_row(steps)
        if step == 2 and self.last_test:
            t = self.last_test
            rows = [("This printer, now", t)]
            if self.previous_test:
                rows.append(("This printer, before", self.previous_test))
            for label, r in rows:
                answered = r["asked"] - r["failed"]
                card.add_row(
                    ui.Gauge(
                        f"{label}: {answered} of {r['asked']} answered",
                        round(100 * answered / max(1, r["asked"])),
                        [tokens.COLOR["error" if r["failed"] else "ok"]],
                    )
                )
            card.add_row(
                ui.Banner("ok", "<b>The connection is healthy.</b>")
                if not t["failed"]
                else ui.Banner("error", f"<b>The connection is unreliable.</b> {lt_status.CABLE_FIRST}")
            )
        row = Gtk.Box(spacing=8)
        for label, action, kind in buttons:
            row.pack_start(ui.button(label, action, kind=kind), False, False, 0)
        card.add_row(row)

    def next_step(self):
        self.step = min(self.step + 1, len(STEPS) - 1)
        self.build_trouble()

    def test_step(self):
        self.run_test(
            then=lambda _r: self.stack.get_visible_child_name() == "trouble" and self.build_trouble()
        )

    def check_and_continue(self):
        """Search again and wait for the printer's own answer; only that counts as fixed"""
        self.set_notice(None, "")
        self.resolved = False
        self._awaiting = True
        self._cancel_give_up()
        self.build_trouble()
        self.ctx.emit("request-printer-refresh")
        self._give_up = GLib.timeout_add_seconds(15, self._no_answer)

    def _no_answer(self):
        """No answer in time: say so; the step stays"""
        self._give_up = None
        if self._awaiting:
            self._awaiting = False
            self.set_notice("error", f"The printer still doesn't answer. {lt_status.CABLE_FIRST}")
            self.build_trouble()
        return False

    def _cancel_give_up(self):
        if self._give_up:
            GLib.source_remove(self._give_up)
            self._give_up = None

    def on_shown(self):
        if self.printer is not None and self.printer.methods:
            self.ctx.printing.status_async(self.printer, lambda st: self.on_status(self.printer, st))
        self.rebuild()
