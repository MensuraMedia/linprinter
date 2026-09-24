"""
Print Manager
Owns the printers (discovery, remembered printer, capabilities), the open
document, job tickets, printing with fallback across methods, job
monitoring, status and the Recent list. Pages call it; it calls the backends.

Methods, best first (as LinScanner's connection engine):
  P1 direct IPP over ipp-usb   exact options, validation, job state, identify
  P2 CUPS queue                spooler; printers that need a driver
  PDF Print to PDF             ~/Documents/prints (Settings)
  T  test printer              --test-printer and tests
No fallback when the printer needs the user (paper, jam, cover, empty ink).
"""

import os
import re
import tempfile
import threading
import time

from gi.repository import GLib

from backends.backend_base import (
    Method,
    PaperSize,
    PrintError,
    PrinterCapabilities,
    PrinterDevice,
    capabilities_from_ipp,
)
from backends.backend_cups import CupsBackend, queue_model
from backends.backend_ipp import IppBackend
from backends.backend_pdf import PdfBackend, pdf_capabilities
from backends.usb_probe import likely_printers, probe
from config.config_print import COLOR_MODES, DEFAULT_PAPER, PDF_PRINTER_ID, QUALITIES, SCALING
from modules import manager_render as render
from modules.manager_documents import add_recent
from modules.manager_status import describe, user_must_act
from utils.util_logging import get_logger

log = get_logger("print")

FINAL_JOB_STATES = ("completed", "canceled", "aborted")
JOB_TIMEOUT = 1800  # seconds to follow a job before giving up watching it


def model_key(name):
    """Normalised model name used to match one printer offered by several methods"""
    name = re.sub(r"\(usb\)|\busb\b", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


def generic_capabilities():
    """Capabilities for a CUPS-only printer that can't be asked over IPP"""
    caps = pdf_capabilities()
    caps.qualities = ["draft", "normal", "high"]
    caps.copies_max = 99
    caps.borderless = set()
    caps.margins = {}
    return caps


class PrintManager:
    """Printers, document, tickets, jobs"""

    def __init__(self, settings, test_printer_uri=None, use_cups=True, probe_usb=True):
        """test_printer_uri: add the built-in test printer (--test-printer, tests)"""
        self.settings = settings
        self.ipp = IppBackend(extra_uris=[test_printer_uri] if test_printer_uri else (), probe_usb=probe_usb)
        self.test_uri = test_printer_uri
        self.cups = CupsBackend() if use_cups else None
        self.pdf = PdfBackend()
        self.probe_usb = probe_usb
        self.printers = []
        self.session_dir = tempfile.mkdtemp(prefix="linprinter-")
        self.document = None  # {"path", "pdf", "pages"}: the file to print
        self.busy = False
        self.current_job = None  # {"method", "job_id", "printer"}
        self._cancel = threading.Event()

    # -- threads -----------------------------------------------------------------
    @staticmethod
    def _in_thread(work, on_done, on_error):
        """Run work() in a thread; deliver the result or a plain error on the GTK thread (once)"""

        def once(callback, value):
            callback(value)
            return False

        def runner():
            try:
                result = work()
            except (PrintError, render.RenderError) as e:
                GLib.idle_add(once, on_error, str(e))
            except Exception as e:  # unexpected: show it instead of a silent UI
                log.exception("unexpected error")
                GLib.idle_add(once, on_error, f"Unexpected error: {e}")
            else:
                GLib.idle_add(once, on_done, result)

        threading.Thread(target=runner, daemon=True).start()

    # -- printers ------------------------------------------------------------------
    def pdf_printer(self):
        """The built-in Print to PDF destination"""
        folder = self.settings.get("pdf_folder")
        return PrinterDevice(
            key=PDF_PRINTER_ID,
            name="Print to PDF",
            methods=[Method("PDF", self.pdf, folder)],
            caps=pdf_capabilities(),
            virtual=True,
        )

    def discover(self):
        """Every printer (grouped, methods ranked) plus Print to PDF"""
        printers = []
        for uri, attrs in self.ipp.list_printers():
            name = attrs.get("printer-make-and-model") or attrs.get("printer-info") or "IPP printer"
            test = uri == self.test_uri
            printers.append(
                PrinterDevice(
                    key=("test:" if test else "usb:") + model_key(name),
                    name=name + (" (test printer)" if test else ""),
                    methods=[Method("T" if test else "P1", self.ipp, uri)],
                    caps=capabilities_from_ipp(attrs),
                    firmware=attrs.get("printer-firmware-string-version", ""),
                    virtual=test,
                )
            )
        if self.cups:
            for queue, uri in self.cups.list_printers():
                key = model_key(queue_model(queue))
                match = next((p for p in printers if not p.virtual and model_key(p.name) == key), None)
                method = Method("P2", self.cups, queue)
                if match:
                    match.methods.append(method)
                else:
                    printers.append(
                        PrinterDevice(
                            key="cups:" + key,
                            name=queue_model(queue),
                            methods=[method],
                            caps=generic_capabilities(),
                        )
                    )
        if self.probe_usb:
            usb = probe()
            for dev in likely_printers(usb):
                label = f"{dev.manufacturer} {dev.product}".strip()
                match = next(
                    (
                        p
                        for p in printers
                        if not p.virtual
                        and model_key(dev.product or "")
                        and model_key(dev.product) in model_key(p.name)
                    ),
                    None,
                )
                if match:
                    match.usb = dev
                else:
                    hint = (
                        "This printer is connected, but nothing answers for it yet. It can print "
                        "driverless through ipp-usb (sudo apt install ipp-usb)."
                        if "ipp-usb" in dev.kinds
                        else "This printer is connected but has no CUPS queue. Add it in the system's Printers settings."
                    )
                    printers.append(
                        PrinterDevice(key=f"usb:{dev.usb_id}", name=label or dev.usb_id, usb=dev, hint=hint)
                    )
        printers.append(self.pdf_printer())
        self.printers = printers
        for p in printers:
            log.info(
                "printer %s: %s", p.name, ", ".join(m.label for m in p.methods) or f"no method ({p.hint})"
            )
        return printers

    @staticmethod
    def should_reconnect(level, misses, seconds_since_last_try, busy, virtual=False):
        """Search for the printer again? (unreachable a few times, not printing, not too often)"""
        from config.config_print import RECONNECT_AFTER_MISSES, RECONNECT_EVERY

        if busy or virtual or level != "error":
            return False
        return misses >= RECONNECT_AFTER_MISSES and seconds_since_last_try >= RECONNECT_EVERY

    def refresh_printers(self, on_done, on_error):
        """Find printers in the background"""
        self._in_thread(self.discover, on_done, on_error)

    def remembered_usb(self):
        """{"id", "port"} of the last USB printer used ({} if none) - for Reconnect"""
        return (self.settings.get("last_printer_info") or {}).get("usb") or {}

    def reconnect_usb(self, printer=None):
        """Re-attach the chosen printer (or the remembered one) on USB: (ok, message)"""
        from backends.usb_reset import reset

        usb = self.remembered_usb()
        port = printer.usb.port_path if printer is not None and printer.usb else usb.get("port", "")
        usb_id = printer.usb.usb_id if printer is not None and printer.usb else usb.get("id", "")
        if not usb_id and not port:  # nothing remembered yet: take a printer that is plugged in now
            from backends.usb_probe import likely_printers, probe

            found = next(iter(likely_printers(probe())), None)
            if found is None:
                return False, "No USB printer found, so there is nothing to re-attach."
            port, usb_id = found.port_path, found.usb_id
        return reset(port, usb_id)

    def printer(self, printer_id):
        """A printer by id (None if unknown)"""
        return next((p for p in self.printers if p.id == printer_id), None)

    def remember(self, printer):
        """Store the printer in use, so the next start reaches it without a full search"""
        if printer.virtual or not printer.methods:
            return
        info = {
            "key": printer.key,
            "name": printer.name,
            "methods": [{"code": m.code, "target": m.target} for m in printer.methods],
        }
        if printer.usb:  # so Reconnect works even when the printer has dropped off or after a restart
            info["usb"] = {"id": printer.usb.usb_id, "port": printer.usb.port_path}
        if info != self.settings.get("last_printer_info"):
            self.settings.set("last_printer_info", info)

    def restore(self, on_done, on_error):
        """Reach the remembered printer directly (one IPP request instead of a full search)"""
        info = self.settings.get("last_printer_info") or {}

        def work():
            methods, caps, firmware = [], None, ""
            for m in info.get("methods", []):
                if m["code"] == "P1":
                    attrs = self.ipp.attributes(m["target"], timeout=4)  # proves it answers
                    caps, firmware = capabilities_from_ipp(attrs), attrs.get(
                        "printer-firmware-string-version", ""
                    )
                    methods.append(Method("P1", self.ipp, m["target"]))
                elif m["code"] == "P2" and self.cups:
                    methods.append(Method("P2", self.cups, m["target"]))
            if not methods or caps is None:
                raise PrintError("The remembered printer didn't answer.", "unreachable")
            printer = PrinterDevice(
                key=info["key"],
                name=info["name"],
                methods=methods,
                caps=caps,
                firmware=firmware,
                restored=True,
            )
            self.printers = [printer, self.pdf_printer()]
            return self.printers

        self._in_thread(work, on_done, on_error)

    # -- status ----------------------------------------------------------------------
    def status(self, printer):
        """(level, message, state, reasons, markers) for a printer"""
        if printer is None or not printer.methods:
            return "error", (printer.hint if printer else "No printer."), "unknown", [], []
        method = printer.methods[0]
        try:
            state, reasons, markers = method.backend.status(method.target)
        except PrintError:
            level, message = describe("unknown", [], reachable=False)
            return level, message, "unknown", [], []
        level, message = describe(state, reasons)
        return level, message, state, reasons, markers

    def status_async(self, printer, on_done):
        """status() in the background"""
        self._in_thread(
            lambda: self.status(printer), on_done, lambda e: on_done(("error", e, "unknown", [], []))
        )

    def identify(self, printer):
        """Make the printer flash (direct IPP only)"""
        method = next((m for m in printer.methods if m.code in ("P1", "T")), None)
        if method is None:
            raise PrintError("This printer can't identify itself.", "unsupported")
        method.backend.identify(method.target)

    def jobs(self, printer):
        """Jobs waiting or printing, then finished ones: [{id, name, state, done, method}]"""
        out = []
        for m in printer.methods:
            if not hasattr(m.backend, "jobs"):
                continue
            for which in ("not-completed", "completed"):
                try:
                    for j in m.backend.jobs(m.target, which):
                        out.append(dict(j, method=m))
                except PrintError as e:
                    log.debug("jobs via %s: %s", m.code, e)
        return out

    def cancel_job(self, method, job_id):
        """Cancel a job"""
        method.backend.cancel(method.target, job_id)

    # -- documents -------------------------------------------------------------------
    def open_document(self, path):
        """Prepare a file for printing (PDF, image or text): {"path", "pdf", "pages"}"""
        work = os.path.join(self.session_dir, "documents")
        pdf = render.normalise(path, work)
        doc = {"path": path, "pdf": pdf, "pages": render.page_count(pdf)}
        log.info("opened %s: %d page(s)", path, doc["pages"])
        self.document = doc
        return doc

    def open_async(self, path, on_done, on_error):
        """open_document() in the background"""
        self._in_thread(lambda: self.open_document(path), on_done, on_error)

    # -- tickets ---------------------------------------------------------------------
    @staticmethod
    def default_size(caps):
        """The size to start with: A4 / Letter if offered, else the printer's default"""
        for stem in DEFAULT_PAPER:
            kw = next((s.keyword for s in caps.sizes if s.keyword.startswith(stem + "_")), None)
            if kw and kw == caps.default_size:
                return kw
        return caps.default_size or (caps.sizes[0].keyword if caps.sizes else "iso_a4_210x297mm")

    def ticket(self, printer, choices):
        """A job ticket from the user's choices, fitted to what the printer supports"""
        caps = printer.caps or PrinterCapabilities()
        size = choices.get("size") if caps.size(choices.get("size") or "") else self.default_size(caps)
        paper = caps.size(size) or PaperSize(size, 210, 297)
        mtype = (
            choices.get("type")
            if choices.get("type") in caps.types
            else (
                caps.default_type
                if caps.default_type in caps.types
                else (caps.types[0] if caps.types else "")
            )
        )
        borderless = bool(choices.get("borderless")) and caps.can_borderless(size, mtype or None)
        color = choices.get("color") if choices.get("color") in caps.colors else caps.colors[0]
        quality = (
            choices.get("quality")
            if choices.get("quality") in caps.qualities
            else caps.qualities[min(1, len(caps.qualities) - 1)]
        )
        return {
            "size": size,
            "size_mm": (paper.width_mm, paper.height_mm),
            "type": mtype,
            "borderless": borderless,
            "margins_mm": caps.margins_for(size, mtype or None, borderless),
            "color": color,
            "quality": quality,
            "copies": max(1, min(int(choices.get("copies", 1)), caps.copies_max)),
            "scaling": choices.get("scaling") if choices.get("scaling") in SCALING else "fit",
            "dpi": 600,
        }

    @staticmethod
    def summary(ticket, pages, printer):
        """One line of what will print"""
        from backends.backend_base import type_label

        parts = [
            f"{ticket['copies']} cop{'y' if ticket['copies'] == 1 else 'ies'}",
            COLOR_MODES.get(ticket["color"], ticket["color"]),
            QUALITIES.get(ticket["quality"], ticket["quality"]) if printer.key != PDF_PRINTER_ID else "",
            (
                printer.caps.size(ticket["size"]).label
                if printer.caps and printer.caps.size(ticket["size"])
                else ticket["size"]
            ),
            type_label(ticket["type"]) if ticket.get("type") else "",
            "borderless" if ticket["borderless"] else "",
            SCALING.get(ticket["scaling"], ""),
            f"{len(pages)} page(s)",
        ]
        return " · ".join(p for p in parts if p)

    # -- preview ---------------------------------------------------------------------
    def preview(self, ticket, pages):
        """Preview images of the chosen pages as they will print"""
        return render.render_preview(
            self.document["pdf"], pages, ticket, os.path.join(self.session_dir, "preview")
        )

    def preview_async(self, ticket, pages, on_done, on_error):
        """preview() in the background"""
        self._in_thread(lambda: self.preview(ticket, pages), on_done, on_error)

    # -- printing --------------------------------------------------------------------
    def print_async(self, printer, ticket, pages, on_progress, on_done, on_error, document=None, recent=True):
        """Print the open document (or `document`): try each method in order; follow the job; add it to Recent"""
        self._cancel.clear()
        self.busy = True
        doc = document or self.document
        job_name = os.path.basename(doc["path"])

        def progress(text):
            GLib.idle_add(lambda: on_progress(text) and False)

        def work():
            if not printer.methods:
                raise PrintError(printer.hint or "This printer can't be reached.", "unreachable")
            last = None
            for method in printer.methods:
                if self._cancel.is_set():
                    raise PrintError("Cancelled.", "user")
                if method.code in ("P1", "T", "P2"):
                    try:
                        state, reasons, _m = method.backend.status(method.target)
                    except PrintError as e:
                        last = e
                        log.info("method %s unreachable (%s); trying the next", method.code, e)
                        continue
                    if user_must_act(reasons):
                        raise PrintError(describe(state, reasons)[1], "user")
                progress(f"Preparing {len(pages)} page(s)…")
                try:
                    job_id = method.backend.submit(
                        method.target,
                        ticket,
                        printer.caps,
                        doc["pdf"],
                        pages,
                        os.path.join(self.session_dir, "jobs"),
                        job_name,
                    )
                except PrintError as e:
                    last = e
                    if e.needs_user:
                        raise
                    log.warning("printing via %s failed (%s); trying the next method", method.code, e)
                    continue
                self.current_job = {"method": method, "job_id": job_id, "printer": printer}
                result = self._follow(method, job_id, len(pages) * ticket["copies"], progress)
                if recent:
                    add_recent(doc["path"], printer.name, len(pages), self.summary(ticket, pages, printer))
                return result
            raise last or PrintError("No way to reach this printer worked.", "unreachable")

        def done(result):
            self.busy = False
            self.current_job = None
            on_done(result)

        def failed(message):
            self.busy = False
            self.current_job = None
            on_error(message)

        self._in_thread(work, done, failed)

    # -- printer setup and tests ------------------------------------------------------
    def printer_defaults(self, printer):
        """The printer's own defaults as LinPrinter choices ({} if unknown)"""
        caps = printer.caps
        if not caps:
            return {}
        out = {}
        if caps.default_color:
            out["color"] = caps.default_color
        if caps.default_quality in caps.qualities:
            out["quality"] = caps.default_quality
        if caps.default_size and caps.size(caps.default_size):
            out["size"] = caps.default_size
        if caps.default_type in caps.types:
            out["type"] = caps.default_type
        if caps.default_scaling in ("none",):
            out["scaling"] = "none"
        elif caps.default_scaling:
            out["scaling"] = "fit"
        return out

    def use_printer_defaults(self, printer):
        """Store the printer's defaults as LinPrinter's own; returns the choices applied"""
        choices = self.printer_defaults(printer)
        keys = {
            "color": "color_mode",
            "quality": "quality",
            "size": "paper",
            "type": "paper_type",
            "scaling": "scaling",
        }
        for key, value in choices.items():
            self.settings.set(keys[key], value)
        log.info("using %s's defaults: %s", printer.name, choices)
        return choices

    def test_ticket(self, printer, kind="quality"):
        """Plain paper, colour, normal quality at the printer's usual size; actual size (no scaling)"""
        caps = printer.caps or PrinterCapabilities()
        return self.ticket(
            printer,
            {
                "size": self.default_size(caps),
                "type": "stationery" if "stationery" in caps.types else caps.default_type,
                "color": "color" if "color" in caps.colors else "monochrome",
                "quality": "normal",
                "copies": 1,
                "borderless": False,
                "scaling": "none",
            },
        )

    def print_test_page(self, printer, kind, on_progress, on_done, on_error, ticket=None):
        """Draw a built-in test page for this printer's paper and print it (not added to Recent)"""
        from modules.manager_testpage import KINDS, make_test_page

        ticket = ticket or self.test_ticket(printer, kind)
        path = os.path.join(self.session_dir, "tests", f"linprinter-test-{kind}.pdf")
        make_test_page(
            kind, path, ticket["size_mm"], ticket["margins_mm"], printer.name, ticket, printer.firmware
        )
        log.info("test page (%s) for %s", KINDS.get(kind, kind), printer.name)
        doc = {"path": path, "pdf": path, "pages": 1}
        self.print_async(printer, ticket, [1], on_progress, on_done, on_error, document=doc, recent=False)

    def _follow(self, method, job_id, impressions, progress):
        """Watch a job until it's done; returns {"state", "method", "job_id", "file"}"""
        if method.code == "PDF":
            return {"state": "completed", "method": method.code, "job_id": None, "file": job_id}
        start = time.monotonic()
        while time.monotonic() - start < JOB_TIMEOUT:
            if self._cancel.is_set():
                try:
                    method.backend.cancel(method.target, job_id)
                except PrintError as e:
                    log.warning("cancel failed: %s", e)
                return {"state": "canceled", "method": method.code, "job_id": job_id, "file": None}
            try:
                state, done, reasons = method.backend.job(method.target, job_id)
            except PrintError as e:
                log.info("job %s: %s", job_id, e)
                state, done, reasons = "processing", 0, []
            if state in FINAL_JOB_STATES:
                return {
                    "state": state,
                    "method": method.code,
                    "job_id": job_id,
                    "file": None,
                    "reasons": reasons,
                }
            progress(f"Printing{f' page {min(done + 1, impressions)} of {impressions}' if done else ''}…")
            time.sleep(1)
        return {"state": "processing", "method": method.code, "job_id": job_id, "file": None}

    def cancel(self):
        """Stop the job being printed"""
        self._cancel.set()

    def cleanup(self):
        """Delete the session's temporary files"""
        import shutil

        shutil.rmtree(self.session_dir, ignore_errors=True)
