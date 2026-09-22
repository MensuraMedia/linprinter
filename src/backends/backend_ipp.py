"""
Direct IPP backend (method P1)
Talks IPP Everywhere straight to USB printers through ipp-usb, which listens
on 127.0.0.1 from port 60000. Loopback only: LinPrinter never reaches the
network (config_print.NETWORK_PRINTING is off).

Why first: it controls every job attribute exactly (paper type, borderless
margins through media-col), validates a job before sending it, reports the
job's state, and can make the printer identify itself. CUPS (backend_cups)
is the fallback.
"""

import os
import socket
import time
import urllib.parse

from backends import ipp
from backends.backend_base import PrintError, capabilities_from_ipp, printer_status
from config.config_print import IPP_PATHS, IPP_USB_PORTS, QUALITIES
from modules.manager_render import render_pwg
from utils.util_logging import get_logger

log = get_logger("ipp")

QUALITY_ENUM = {"draft": 3, "normal": 4, "high": 5}


def is_loopback(uri):
    """True if an IPP URI points at this computer"""
    host = urllib.parse.urlsplit(uri).hostname or ""
    return host in ("localhost", "::1") or host.startswith("127.")


def ipp_usb_uris():
    """IPP URIs of USB printers served by ipp-usb (open ports on 127.0.0.1:60000+)"""
    uris = []
    for port in IPP_USB_PORTS:
        with socket.socket() as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                uris += [f"ipp://127.0.0.1:{port}{path}" for path in IPP_PATHS]
    return uris


def _error(e):
    """PrintError for an IppError"""
    code = {"unreachable": "unreachable", "busy": "busy", "unsupported": "unsupported"}.get(
        e.code, "rejected"
    )
    return PrintError(str(e), code)


def job_attributes(ticket, caps):
    """IPP job attributes for a ticket, limited to what the printer supports"""
    size = caps.size(ticket["size"]) if caps else None
    w, h = ticket["size_mm"]
    media = [
        (
            "media-size",
            ipp.BEG_COLLECTION,
            [
                [
                    ("x-dimension", ipp.INTEGER, [int(round(w * 100))]),
                    ("y-dimension", ipp.INTEGER, [int(round(h * 100))]),
                ]
            ],
        ),
    ]
    if ticket.get("type"):
        media.append(("media-type", ipp.KEYWORD, [ticket["type"]]))
    if ticket.get("borderless"):
        media += [(f"media-{side}-margin", ipp.INTEGER, [0]) for side in ("top", "bottom", "left", "right")]
    attrs = [
        ("copies", ipp.INTEGER, [max(1, int(ticket.get("copies", 1)))]),
        ("print-color-mode", ipp.KEYWORD, [ticket.get("color", "color")]),
        ("print-quality", ipp.ENUM, [QUALITY_ENUM.get(ticket.get("quality"), 4)]),
        ("media-col", ipp.BEG_COLLECTION, [media]),
    ]
    if caps and "none" in caps.scaling:
        attrs.append(("print-scaling", ipp.KEYWORD, ["none"]))  # LinPrinter already fitted the pages
    if not size:
        log.debug("size %s not listed by the printer; sent as dimensions only", ticket["size"])
    return attrs


class IppBackend:
    """Driverless IPP Everywhere over USB (ipp-usb), plus the built-in test printer"""

    name = "ipp"
    code = "P1"

    def __init__(self, extra_uris=(), probe_usb=True):
        """extra_uris: more IPP printers on 127.0.0.1 (the test printer)"""
        self.extra_uris = [u for u in extra_uris if is_loopback(u)]
        self.probe_usb = probe_usb

    def candidates(self):
        """IPP URIs to try"""
        return (ipp_usb_uris() if self.probe_usb else []) + list(self.extra_uris)

    def attributes(self, uri, timeout=10):
        """Every printer attribute (PrintError if unreachable)"""
        try:
            return ipp.IppClient(uri, timeout=timeout).get_printer_attributes()
        except ipp.IppError as e:
            raise _error(e)

    def list_printers(self):
        """[(uri, attributes)] of the IPP printers that answer"""
        found = []
        for uri in self.candidates():
            try:
                found.append((uri, self.attributes(uri, timeout=5)))
            except PrintError as e:
                log.info("no IPP printer at %s (%s)", uri, e)
        return found

    def capabilities(self, uri):
        """PrinterCapabilities for a printer"""
        return capabilities_from_ipp(self.attributes(uri))

    def status(self, uri):
        """(state, reasons, markers)"""
        return printer_status(self.attributes(uri, timeout=5))

    def submit(self, uri, ticket, caps, pdf, pages, work_dir, job_name):
        """Render to PWG raster, validate, and send; returns the printer's job id"""
        os.makedirs(work_dir, exist_ok=True)
        raster = os.path.join(work_dir, f"job-{int(time.time() * 1000)}.pwg")
        start = time.monotonic()
        render_pwg(pdf, pages, ticket, raster)
        log.info(
            "rendered %d page(s) to PWG raster in %.1f s (%d KB)",
            len(pages),
            time.monotonic() - start,
            os.path.getsize(raster) // 1024,
        )
        client = ipp.IppClient(uri, timeout=30)
        attrs = job_attributes(ticket, caps)
        try:
            status, unsupported = client.validate_job(attrs, "image/pwg-raster")
            if unsupported:
                log.info("printer substitutes: %s", ", ".join(unsupported))
            job = client.print_job(raster, "image/pwg-raster", attrs, job_name=job_name)
        except ipp.IppError as e:
            raise _error(e)
        finally:
            try:
                os.remove(raster)
            except OSError:
                pass
        job_id = job.get("job-id")
        log.info(
            "sent job %s to %s (%s, %s copies, %s, %s)",
            job_id,
            uri,
            ticket["size"],
            ticket.get("copies"),
            ticket.get("color"),
            QUALITIES.get(ticket.get("quality")),
        )
        return job_id

    def job(self, uri, job_id):
        """(state name, pages done, reasons) of a job"""
        try:
            attrs = ipp.IppClient(uri, timeout=5).get_job(job_id)
        except ipp.IppError as e:
            raise _error(e)
        return (
            ipp.JOB_STATES.get(attrs.get("job-state"), "unknown"),
            attrs.get("job-impressions-completed", 0),
            ipp.values(attrs, "job-state-reasons"),
        )

    def jobs(self, uri, which="not-completed"):
        """Jobs on the printer: [{id, name, state, done}]"""
        try:
            raw = ipp.IppClient(uri, timeout=5).get_jobs(which)
        except ipp.IppError as e:
            raise _error(e)
        return [
            {
                "id": j.get("job-id"),
                "name": j.get("job-name", ""),
                "state": ipp.JOB_STATES.get(j.get("job-state"), "unknown"),
                "done": j.get("job-impressions-completed", 0),
                "created": j.get("time-at-creation", 0),
            }
            for j in raw
        ]

    def cancel(self, uri, job_id):
        """Cancel a job"""
        try:
            ipp.IppClient(uri, timeout=10).cancel_job(job_id)
        except ipp.IppError as e:
            raise _error(e)

    def identify(self, uri):
        """Make the printer flash (Identify-Printer)"""
        try:
            ipp.IppClient(uri, timeout=10).identify()
        except ipp.IppError as e:
            raise _error(e)
