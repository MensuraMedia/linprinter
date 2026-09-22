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
