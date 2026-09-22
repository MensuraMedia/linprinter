"""
Test printer
A small IPP Everywhere printer inside LinPrinter, for tests and --test-printer
(the printing counterpart of SANE's virtual scanner). It answers with a real
printer's attributes (the Canon TR150's, identifiers removed), listens on
127.0.0.1 only, keeps print jobs as files, and lets tests set printer states
(paper out, jam, low ink, ...).

(CUPS' ippeveprinter would do the same, but it needs IPv6, which is switched
off on the reference machine.)
"""

import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backends import ipp
from utils.util_paths import resource

FIXTURE = resource("test-printer", "tr150-attributes.json")


def load_fixture(path=FIXTURE):
    """[(name, tag, values)] printer attributes from a fixture file"""
    with open(path) as f:
        return [tuple(a) for a in json.load(f)["attributes"]]


class TestPrinter:
    """Start with .start(); .uri is the printer URI; jobs are saved in .spool"""

    __test__ = False  # not a pytest test class

    def __init__(self, fixture=FIXTURE, spool=None, name="LinPrinter Test Printer"):
        self.attributes = [
            a
            for a in load_fixture(fixture)
            if a[0]
            not in (
                "printer-state",
                "printer-state-reasons",
                "marker-levels",
                "printer-name",
                "printer-uri-supported",
            )
        ]
        self.name = name
        self.state = 3  # idle
        self.reasons = ["none"]
        self.marker_levels = [60, 80]
        self.jobs = {}  # id -> dict
        self.next_job = 1
        self.identified = 0
        self.requests = []  # operation ids received (for tests)
        self.spool = spool or tempfile.mkdtemp(prefix="linprinter-test-printer-")
        os.makedirs(self.spool, exist_ok=True)
        self.job_seconds = 0.3  # how long a job "prints"
        self._server = None

    # -- control ------------------------------------------------------------------
    @property
    def uri(self):
        """ipp://127.0.0.1:<port>/ipp/print"""
        return f"ipp://127.0.0.1:{self._server.server_address[1]}/ipp/print"

    def start(self):
        """Serve in a background thread on a free 127.0.0.1 port"""
        printer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"  # IPP requires HTTP/1.1 (RFC 8010)

            def log_message(self, *_):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                reply = printer.handle(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/ipp")
                self.send_header("Content-Length", str(len(reply)))
                self.end_headers()
                self.wfile.write(reply)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        """Stop serving"""
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def set_state(self, reasons=("none",), state=None):
        """Simulate printer-state-reasons, e.g. ("media-empty-error",)"""
        self.reasons = list(reasons)
        self.state = state or (5 if any(r.endswith("-error") for r in reasons) else 3)

    # -- IPP ------------------------------------------------------------------------
    def printer_attributes(self):
        """The attribute list with the live state"""
        return self.attributes + [
            ("printer-name", ipp.NAME, [self.name]),
            ("printer-state", ipp.ENUM, [self.state]),
            ("printer-state-reasons", ipp.KEYWORD, self.reasons),
            ("marker-levels", ipp.INTEGER, self.marker_levels),
            ("printer-uri-supported", ipp.URI, [self.uri]),
        ]

    def _job_attrs(self, job):
        """A job's attributes for responses"""
        self._advance(job)
        return [
            ("job-id", ipp.INTEGER, [job["id"]]),
            ("job-uri", ipp.URI, [f"{self.uri}/{job['id']}"]),
            ("job-name", ipp.NAME, [job["name"]]),
            ("job-state", ipp.ENUM, [job["state"]]),
            ("job-state-reasons", ipp.KEYWORD, [job["reasons"]]),
            ("job-impressions-completed", ipp.INTEGER, [job["done"]]),
            ("time-at-creation", ipp.INTEGER, [int(job["created"])]),
        ]

    def _advance(self, job):
        """Jobs finish after job_seconds (unless the printer has an error)"""
        if job["state"] in (5, 3) and self.state != 5 and time.time() - job["created"] >= self.job_seconds:
            job["state"], job["reasons"], job["done"] = 9, "job-completed-successfully", job["pages"]
        elif job["state"] in (3, 5) and self.state == 5:
            job["state"], job["reasons"] = 6, "printer-stopped"

    def handle(self, body):
        """One IPP request -> response bytes"""
        op, rid, groups = ipp.decode_message(body)
        self.requests.append(op)
        ops = next((a for t, a in groups if t == ipp.OPERATION), {})
        head = [
            ("attributes-charset", ipp.CHARSET, ["utf-8"]),
            ("attributes-natural-language", ipp.LANGUAGE, ["en"]),
        ]
        if op == ipp.GET_PRINTER_ATTRIBUTES:
            return ipp.encode_response(
                0, rid, [(ipp.OPERATION, head), (ipp.PRINTER, self.printer_attributes())]
            )
        if op == ipp.VALIDATE_JOB:
            fmt = ops.get("document-format", "application/octet-stream")
            if fmt not in ("image/pwg-raster", "image/urf", "image/jpeg", "application/octet-stream"):
                return ipp.encode_response(0x040A, rid, [(ipp.OPERATION, head)])
            return ipp.encode_response(0, rid, [(ipp.OPERATION, head)])
        if op == ipp.PRINT_JOB:
            if self.state == 5 and any(r.endswith("-error") for r in self.reasons):
                return ipp.encode_response(0x0506, rid, [(ipp.OPERATION, head)])
            data = body[self._end_of_attributes(body) :]
            job = {
                "id": self.next_job,
                "name": ops.get("job-name", "job"),
                "state": 5,
                "reasons": "job-printing",
                "created": time.time(),
                "done": 0,
                "pages": max(1, data.count(b"PwgRaster") or data.count(b"\xff\xd8\xff") or 1),
                "attrs": dict(next((a for t, a in groups if t == ipp.JOB), {})),
                "format": ops.get("document-format"),
            }
            job["file"] = os.path.join(
                self.spool, f"job-{job['id']:04d}.{'pwg' if 'pwg' in str(job['format']) else 'bin'}"
            )
            with open(job["file"], "wb") as f:
                f.write(data)
            self.jobs[job["id"]] = job
            self.next_job += 1
            return ipp.encode_response(0, rid, [(ipp.OPERATION, head), (ipp.JOB, self._job_attrs(job))])
        if op == ipp.GET_JOBS:
            which = ops.get("which-jobs", "not-completed")
            groups_out = [(ipp.OPERATION, head)]
            for job in self.jobs.values():
                self._advance(job)
                done = job["state"] >= 7
                if (which == "completed") == done or which == "all":
                    groups_out.append((ipp.JOB, self._job_attrs(job)))
            return ipp.encode_response(0, rid, groups_out)
        if op in (ipp.GET_JOB_ATTRIBUTES, ipp.CANCEL_JOB):
            job = self.jobs.get(ops.get("job-id"))
            if job is None:
                return ipp.encode_response(0x0406, rid, [(ipp.OPERATION, head)])
            if op == ipp.CANCEL_JOB:
                job["state"], job["reasons"] = 7, "job-canceled-by-user"
                return ipp.encode_response(0, rid, [(ipp.OPERATION, head)])
            return ipp.encode_response(0, rid, [(ipp.OPERATION, head), (ipp.JOB, self._job_attrs(job))])
        if op == ipp.IDENTIFY_PRINTER:
            self.identified += 1
            return ipp.encode_response(0, rid, [(ipp.OPERATION, head)])
        return ipp.encode_response(0x0501, rid, [(ipp.OPERATION, head)])

    @staticmethod
    def _end_of_attributes(body):
        """Offset of the document data after the IPP attributes"""
        pos = 8
        while pos < len(body):
            tag = body[pos]
            if tag == ipp.END:
                return pos + 1
            if tag in ipp.GROUP_TAGS:
                pos += 1
                continue
            nlen = int.from_bytes(body[pos + 1 : pos + 3], "big")
            pos += 3 + nlen
            vlen = int.from_bytes(body[pos : pos + 2], "big")
            pos += 2 + vlen
        return len(body)
