"""PrintManager end to end with the built-in test printer (no hardware)"""

import os
import threading

import pytest
from PIL import Image

from backends.test_printer import TestPrinter
from conftest import requires_gs
from modules.manager_documents import recent_entries
from modules.manager_print import PrintManager
from modules.manager_settings import SettingsManager

pytestmark = requires_gs


@pytest.fixture
def setup(tmp_path):
    t = TestPrinter(spool=str(tmp_path / "spool"))
    t.job_seconds = 0.1
    t.start()
    settings = SettingsManager(str(tmp_path / "settings.json"))
    settings.override("pdf_folder", str(tmp_path / "prints"))
    pm = PrintManager(settings, test_printer_uri=t.uri, use_cups=False, probe_usb=False)
    doc = tmp_path / "doc.pdf"
    Image.new("RGB", (620, 877), "white").save(
        doc, save_all=True, append_images=[Image.new("RGB", (877, 620), "red")]
    )
    yield t, pm, str(doc), tmp_path
    pm.cleanup()
    t.stop()


def run(pm, *args, **kw):
    """print_async without a GTK loop: call the worker synchronously"""
    box = {}
    ev = threading.Event()
    pm._in_thread = lambda work, done, failed: _sync(work, done, failed)

    def _sync(work, done, failed):
        try:
            done(work())
        except Exception as e:  # noqa: BLE001
            failed(str(e))

    pm.print_async(
        *args,
        lambda _t: None,
        lambda r: (box.update(result=r), ev.set()),
        lambda e: (box.update(error=e), ev.set()),
        **kw,
    )
    return box


def test_discovers_test_printer_and_pdf(setup):
    _t, pm, _doc, _tmp = setup
    names = [p.name for p in pm.discover()]
    assert names[0].startswith("Canon TR150") and names[-1] == "Print to PDF"


def test_print_job_attributes(setup):
    t, pm, doc, _tmp = setup
    printer = pm.discover()[0]
    pm.open_document(doc)
    ticket = pm.ticket(
        printer,
        {
            "color": "monochrome",
            "quality": "high",
            "copies": 2,
            "type": "photographic",
            "size": "iso_a4_210x297mm",
            "borderless": False,
            "scaling": "fit",
        },
    )
    box = run(pm, printer, ticket, [1, 2])
    assert box["result"]["state"] == "completed", box
    job = list(t.jobs.values())[-1]
    assert job["attrs"]["copies"] == 2
    assert job["attrs"]["print-color-mode"] == "monochrome"
    assert job["attrs"]["print-quality"] == 5
    assert open(job["file"], "rb").read(4) == b"RaS2"
    assert recent_entries()[0]["printer"] == printer.name


def test_paper_out_does_not_fall_back(setup):
    t, pm, doc, _tmp = setup
    printer = pm.discover()[0]
    pm.open_document(doc)
    t.set_state(["media-empty-error"])
    box = run(pm, printer, pm.ticket(printer, {}), [1])
    assert "paper" in box["error"].lower()
    assert not t.jobs


def test_failing_usb_link_does_not_fall_back(setup):
    """P1 and a driverless CUPS queue share ipp-usb's link: don't spool the job onto it"""
    from backends.backend_base import Method, PrintError

    class Broken:
        def status(self, _target):
            raise PrintError("The printer's USB connection isn't carrying data.", "link")

    class Spooler:
        submitted = []

        def status(self, _target):
            return "idle", [], []

        def submit(self, *args):
            self.submitted.append(args)
            return "Q-1"

    _t, pm, doc, _tmp = setup
    printer = pm.discover()[0]
    spooler = Spooler()
    printer.methods = [Method("P1", Broken(), "ipp://127.0.0.1:60000/ipp/print"), Method("P2", spooler, "Q")]
    pm.open_document(doc)
    box = run(pm, printer, pm.ticket(printer, {}), [1])
    assert "USB connection" in box["error"]
    assert spooler.submitted == []
    assert pm.status(printer)[:2] == ("error", "The printer's USB connection isn't carrying data.")


def test_print_to_pdf(setup):
    _t, pm, doc, tmp = setup
    pdf = pm.printer("pdf:")
    pm.discover()
    pdf = pm.printer("pdf:") or pm.pdf_printer()
    pm.open_document(doc)
    box = run(pm, pdf, pm.ticket(pdf, {"size": "iso_a4_210x297mm"}), [1, 2])
    out = box["result"]["file"]
    assert out.startswith(str(tmp / "prints")) and os.path.exists(out)


def test_test_page_and_defaults(setup):
    t, pm, _doc, _tmp = setup
    printer = pm.discover()[0]
    assert pm.printer_defaults(printer) == {
        "color": "color",
        "quality": "normal",
        "size": "na_letter_8.5x11in",
        "type": "stationery",
        "scaling": "fit",
    }
    ticket = pm.test_ticket(printer)
    assert ticket["scaling"] == "none" and ticket["type"] == "stationery"
    box = {}
    pm._in_thread = lambda work, done, failed: done(work())
    pm.print_test_page(printer, "quality", lambda _t: None, box.update, lambda e: box.update(error=e))
    assert box["state"] == "completed"
    assert len(t.jobs) == 1
    assert recent_entries() == []  # test pages are not added to Recent
    applied = pm.use_printer_defaults(printer)
    assert pm.settings.get("paper") == applied["size"]


def test_refused_because_paper_ran_out_does_not_fall_back(setup):
    """Paper runs out between the check and Print-Job: say so in words, and don't try the CUPS queue"""
    from backends.backend_base import Method, PrintError

    class EmptiesTray:
        calls = 0

        def status(self, _target):
            self.calls += 1
            return ("idle", [], []) if self.calls == 1 else ("stopped", ["media-empty-error"], [])

        def submit(self, *args):
            raise PrintError("Print-Job failed (server-error-not-accepting-jobs)", "busy")

    class Spooler:
        submitted = []

        def status(self, _target):
            return "idle", [], []

        def submit(self, *args):
            self.submitted.append(args)
            return "Q-1"

    _t, pm, doc, _tmp = setup
    printer = pm.discover()[0]
    spooler = Spooler()
    printer.methods = [
        Method("P1", EmptiesTray(), "ipp://127.0.0.1:60000/ipp/print"),
        Method("P2", spooler, "Q"),
    ]
    pm.open_document(doc)
    box = run(pm, printer, pm.ticket(printer, {}), [1])
    assert "paper" in box["error"].lower() and "server-error" not in box["error"]
    assert spooler.submitted == []


def test_a_refusal_is_said_in_plain_words(setup):
    """No raw IPP status in what the user reads"""
    from backends.backend_base import Method, PrintError

    class Refuses:
        def status(self, _target):
            return "idle", [], []

        def submit(self, *args):
            raise PrintError("Print-Job failed (client-error-document-format-not-supported)", "unsupported")

    _t, pm, doc, _tmp = setup
    printer = pm.discover()[0]
    printer.methods = [Method("P1", Refuses(), "ipp://127.0.0.1:60000/ipp/print")]
    pm.open_document(doc)
    box = run(pm, printer, pm.ticket(printer, {}), [1])
    assert box["error"] == "The printer can't print with these settings. Try other paper or quality."


def _two_methods(setup, first):
    from backends.backend_base import Method

    class Spooler:
        submitted = []

        def status(self, _target):
            return "idle", [], []

        def submit(self, *args):
            self.submitted.append(args)
            return "Q-1"

    _t, pm, doc, _tmp = setup
    printer = pm.discover()[0]
    spooler = Spooler()
    printer.methods = [Method("P1", first, "ipp://127.0.0.1:60000/ipp/print"), Method("P2", spooler, "Q")]
    pm.open_document(doc)
    return pm, printer, spooler


def test_link_dies_under_the_upload_does_not_fall_back(setup):
    """Print-Job dies mid-upload and the link is gone: name the USB connection, don't use CUPS"""
    from backends.backend_base import PrintError

    class DiesMidUpload:
        calls = 0

        def status(self, _target):
            self.calls += 1
            if self.calls == 1:
                return "idle", [], []
            raise PrintError("The printer's USB connection isn't carrying data.", "link")

        def submit(self, *args):
            raise PrintError("Connection reset", "unreachable")

    pm, printer, spooler = _two_methods(setup, DiesMidUpload())
    box = run(pm, printer, pm.ticket(printer, {}), [1])
    assert "USB connection" in box["error"] and spooler.submitted == []


def test_printer_not_taking_jobs_is_final(setup):
    """The printer says it isn't taking jobs (no reason the user can fix): no CUPS queue holding it"""
    from backends.backend_base import PrintError

    class Paused:
        def status(self, _target):
            return "stopped", [], []

        def submit(self, *args):
            raise PrintError("Print-Job failed (server-error-not-accepting-jobs)", "busy")

    pm, printer, spooler = _two_methods(setup, Paused())
    box = run(pm, printer, pm.ticket(printer, {}), [1])
    assert box["error"].startswith("The printer isn't taking jobs") and spooler.submitted == []


def test_cancel_while_sending_is_cancelled(setup):
    """Cancelled while the upload fails: the outcome is Cancelled, not a refusal"""
    from backends.backend_base import PrintError

    holder = {}

    class FailsAfterCancel:
        def status(self, _target):
            return "idle", [], []

        def submit(self, *args):
            holder["pm"]._cancel.set()
            raise PrintError("Connection reset", "unreachable")

    pm, printer, spooler = _two_methods(setup, FailsAfterCancel())
    holder["pm"] = pm
    box = run(pm, printer, pm.ticket(printer, {}), [1])
    assert box["error"] == "Cancelled." and spooler.submitted == []
