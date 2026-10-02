"""UI flow in-process with the test printer; needs a display"""

import os
import tempfile
import time

from conftest import requires_display, requires_gs

pytestmark = [requires_display, requires_gs]


def wait_for(condition, timeout=30):
    from gi.repository import Gtk

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_print_flow(tmp_path):
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    from PIL import Image

    from backends.test_printer import TestPrinter
    from features import FeatureRegistry
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_print import PrintManager
    from modules.manager_settings import SettingsManager
    from ui.app_window import AppWindow

    settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
    settings.override("pdf_folder", str(tmp_path / "prints"))
    t = TestPrinter(spool=str(tmp_path / "spool"))
    t.job_seconds = 0.1
    t.start()
    printing = PrintManager(settings, test_printer_uri=t.uri, use_cups=False, probe_usb=False)
    ctx = AppContext(settings, printing, NavigationManager(), None)
    ctx.features = FeatureRegistry(settings)
    window = AppWindow(ctx)
    window.show_all()
    ctx.nav.navigate_to("print")
    page = ctx.nav.get_page_widget("print")
    assert wait_for(lambda: page.power_state == "ok")
    doc = tmp_path / "doc.pdf"
    Image.new("RGB", (620, 877), "white").save(doc)
    page.open_document(str(doc))
    assert wait_for(lambda: page.selected_pages() == [1])
    page.color.set_active("monochrome")
    assert wait_for(lambda: page.preview.strip.get_children(), 20)  # the preview sits on the Print page
    assert page.print_btn.get_sensitive() and page.why_not.get_text() == ""
    assert window.chip.get_accessible().get_name().startswith("Device status: Canon TR150")
    page.on_print()
    assert wait_for(lambda: page.bar.state() == "done", 30)
    assert page.bar._done_head.get_text().startswith("Printed 1 page on")
    assert list(t.jobs.values())[0]["attrs"]["print-color-mode"] == "monochrome"
    for pid in ("activity", "printer", "settings"):
        assert ctx.nav.navigate_to(pid)
        wait_for(lambda: True, 0.2)
    activity = ctx.nav.get_page_widget("activity")
    assert any(isinstance(w, Gtk.Box) for w in activity.table.get_children())  # the print is in History
    printer_page = ctx.nav.get_page_widget("printer")
    result = {}
    printer_page.run_test(then=lambda r: result.update(r=r))
    assert wait_for(lambda: result, 30) and result["r"]["failed"] == 0
    printer_page.start_troubleshooter()
    assert printer_page.stack.get_visible_child_name() == "trouble"
    ctx.nav.get_page_widget("settings").show_section("about")
    # 0.2.x page names still work from the command line
    from main import PAGE_ALIASES

    assert {PAGE_ALIASES[k] for k in ("preview", "queue", "recent", "printers", "about")} <= {
        "print",
        "activity",
        "printer",
        "settings",
    }
    # the window can be made small (snap to half / quarter screen)
    min_w, _nat = window.get_preferred_width()
    assert min_w <= 900
    window.destroy()
    printing.cleanup()
    t.stop()


def _app(tmp_path, job_seconds=0.1):
    """The real window with the test printer (no hardware)"""
    import gi

    gi.require_version("Gtk", "3.0")
    from backends.test_printer import TestPrinter
    from features import FeatureRegistry
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_print import PrintManager
    from modules.manager_settings import SettingsManager
    from ui.app_window import AppWindow

    settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
    settings.override("pdf_folder", str(tmp_path / "prints"))
    t = TestPrinter(spool=str(tmp_path / "spool"))
    t.job_seconds = job_seconds
    t.start()
    printing = PrintManager(settings, test_printer_uri=t.uri, use_cups=False, probe_usb=False)
    ctx = AppContext(settings, printing, NavigationManager(), None)
    ctx.features = FeatureRegistry(settings)
    window = AppWindow(ctx)
    window.show_all()
    ctx.nav.navigate_to("print")
    page = ctx.nav.get_page_widget("print")
    assert wait_for(lambda: page.power_state == "ok")

    def close():
        window.destroy()
        printing.cleanup()
        t.stop()

    return ctx, page, t, close


def _open(page, tmp_path):
    from PIL import Image

    doc = tmp_path / "doc.pdf"
    Image.new("RGB", (620, 877), "white").save(doc)
    page.open_document(str(doc))
    assert wait_for(lambda: page.selected_pages() == [1])
    return doc


def test_cancelled_print_is_not_recorded_as_printed(tmp_path):
    """A job cancelled on the way is 'Cancelled' in Activity, and the Print page says so"""
    from modules.manager_documents import recent_entries

    ctx, page, t, close = _app(tmp_path, job_seconds=30)
    try:
        _open(page, tmp_path)
        page.on_print()
        assert wait_for(lambda: t.jobs, 30)
        assert not page.print_btn.get_sensitive()  # while printing
        assert page.status_key == "busy"
        ctx.printing.cancel()
        assert wait_for(lambda: not ctx.printing.busy, 30)
        assert wait_for(lambda: recent_entries(existing_only=False), 10)
        assert recent_entries(existing_only=False)[0]["result"] == "Cancelled"
        assert page.bar._head.get_text() == "Cancelled"
    finally:
        close()


def test_change_menu_marks_the_chosen_printer(tmp_path):
    """The Change popover's radio follows the printer actually chosen (matched by id)"""
    from gi.repository import Gtk

    ctx, page, t, close = _app(tmp_path)
    try:
        radios = lambda: [
            w for w in page.printer_menu.get_child().get_children() if isinstance(w, Gtk.RadioButton)
        ]
        chosen = [r.get_label() for r in radios() if r.get_active()]
        assert chosen == [page.printer.label]
        pdf = next(p for p in page.printers if p.virtual and p is not page.printer)
        page._choose(pdf)
        assert page.printer is pdf
        page._build_printer_menu()
        assert [r.get_label() for r in radios() if r.get_active()] == [pdf.label]
    finally:
        close()


def test_failed_print_shows_in_activity(tmp_path):
    """A print the printer stops is in History as 'Didn't print', with its reason"""
    from modules.manager_documents import recent_entries

    ctx, page, t, close = _app(tmp_path)
    try:
        _open(page, tmp_path)
        t.set_state(("media-empty-error",), state=5)
        page.check_status()
        assert wait_for(lambda: page.status_key == "attention", 15)
        assert not page.print_btn.get_sensitive() and page.why_not.get_text() == "Load paper first"
        page._job_doc, page._started = ctx.printing.document, time.monotonic()  # as on_print sets them
        page.on_error("The USB connection dropped. Try another cable.", page.printer, page.ticket(), [1])
        entry = recent_entries(existing_only=False)[0]
        assert entry["result"] == "Stopped: USB link dropped"
        activity = ctx.nav.get_page_widget("activity")
        activity.filter.set_value("failed")
        activity.refresh()
        texts = []
        from gi.repository import Gtk

        def walk(w):
            if isinstance(w, Gtk.Label):
                texts.append(w.get_text())
            if isinstance(w, Gtk.Container):
                for c in w.get_children():
                    walk(c)

        walk(activity.table)
        assert "Stopped: USB link dropped" in texts
    finally:
        close()


def test_test_page_marks_busy_then_returns(tmp_path):
    """A test page makes the app Busy (chip, Print page) and the chip comes back afterwards"""
    ctx, page, t, close = _app(tmp_path, job_seconds=1)
    try:
        printer_page = ctx.nav.get_page_widget("printer")
        seen = []
        ctx.on("printing", lambda busy: seen.append(busy))
        import lintheme.gtk3.components as ui

        real_confirm, ui.confirm = ui.confirm, lambda *a, **k: True
        try:
            printer_page.print_test(page.printer, "quality")
        finally:
            ui.confirm = real_confirm
        assert wait_for(lambda: ctx.printing.busy, 30)
        page.show_power("error", "No answer", "unknown", [])  # a slow answer while the test page prints
        assert page.status_key == "busy"
        assert wait_for(lambda: seen == [True, False], 60)
        assert wait_for(lambda: "Ready" in ctx.window.chip.get_accessible().get_name(), 15)
        # a document can't be swapped in while printing (the job keeps its own)
        doc = _open(page, tmp_path)
        other = tmp_path / "other.pdf"
        other.write_bytes(doc.read_bytes())
        page._printing = True
        page.open_document(str(other))
        wait_for(lambda: False, 1)
        assert ctx.printing.document["path"] != str(other)
        page._printing = False
    finally:
        close()


def test_evidence_when_the_kernel_log_is_unreadable(tmp_path, monkeypatch):
    """A USB printer with an unreadable log: errors 'unknown', never 'not on USB' or a green all-clear"""
    from gi.repository import Gtk

    from backends import usb_link
    from backends.usb_probe import UsbDevice

    monkeypatch.setattr(usb_link, "log_readable", lambda: False)
    monkeypatch.setattr(usb_link, "recent", lambda *a, **k: {})
    monkeypatch.setattr(usb_link, "cached", lambda: {})
    ctx, page, t, close = _app(tmp_path)
    try:
        page.printer.usb = UsbDevice(3, 7, "04a9", "18a4", "Canon", "TR150 series", 480, "3-2")
        ctx.nav.navigate_to("printer")
        printer_page = ctx.nav.get_page_widget("printer")
        printer_page.start_troubleshooter()
        texts = []

        def walk(w):
            if isinstance(w, Gtk.Label):
                texts.append(w.get_text())
            if isinstance(w, Gtk.Container):
                for c in w.get_children():
                    walk(c)

        walk(printer_page.trouble)
        joined = " ".join(texts)
        assert "unknown" in joined and "isn't on USB" not in joined and "no connection errors" not in joined
    finally:
        close()


def test_chip_during_a_print_paper_out_then_back(tmp_path):
    """Mid-job: paper out shows Needs you (chip and page, no Reconnect), then both go back to Busy"""
    ctx, page, t, close = _app(tmp_path, job_seconds=60)
    try:
        _open(page, tmp_path)
        page.on_print()
        assert wait_for(lambda: t.jobs and ctx.printing.busy, 30)
        name = lambda: ctx.window.chip.get_accessible().get_name()  # noqa: E731
        # low ink is a warning, not a pause: the job stays Busy
        t.set_state(("marker-supply-low-warning",))
        page.check_status()
        wait_for(lambda: False, 1.5)
        assert "Busy" in name() and page.status_key == "busy"
        t.set_state(("media-empty-error",))
        page.check_status()
        assert wait_for(lambda: "Needs you" in name() and page.status_key == "attention", 15)
        t.set_state([])
        page.check_status()
        assert wait_for(lambda: "Busy" in name() and page.status_key == "busy", 15)
        # a status error mid-job (slow answer) never turns the page into Can't reach with Reconnect
        page.show_power("error", "No answer", "unknown", [])
        assert page.status_key == "busy"
        ctx.printing.cancel()
        assert wait_for(lambda: not ctx.printing.busy, 30)
    finally:
        close()
