#!/usr/bin/env python3
"""
Scripted UI walkthrough with the built-in test printer (nothing is printed on real hardware).

Runs in a sandbox home folder (so the screenshots show ~/Documents/... and none of your own files),
prints a report, a borderless photo, a text file and a Print to PDF, and saves a screenshot of every
page to docs/screenshots/.  Usage: python3 tools/walkthrough.py [out_dir]
"""

import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "screenshots")

# sandbox home: set before anything reads HOME or the XDG folders
SANDBOX = tempfile.mkdtemp(prefix="linprinter-walkthrough-")
HOME = os.path.join(SANDBOX, "home")
os.makedirs(HOME)
os.environ["HOME"] = HOME
for var, sub in (
    ("XDG_CONFIG_HOME", ".config"),
    ("XDG_DATA_HOME", ".local/share"),
    ("XDG_STATE_HOME", ".local/state"),
):
    os.environ[var] = os.path.join(HOME, sub)
sys.path.insert(0, os.path.join(ROOT, "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

GLib.set_prgname("linprinter")
Gdk.set_program_class("linprinter")


def pump(seconds=0.3):
    """Run the GTK loop for a while"""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def wait_for(condition, timeout=30):
    """Run the GTK loop until condition() is true"""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        pump(0.05)
        if condition():
            return True
    raise TimeoutError("condition not met")


def sample_documents():
    """A report (3 pages), a photo and a text file in the sandbox home"""
    from PIL import Image, ImageDraw

    docs = os.path.join(HOME, "Documents")
    pics = os.path.join(HOME, "Pictures")
    for d in (docs, pics, os.path.join(docs, "prints")):
        os.makedirs(d, exist_ok=True)
    a4 = (1240, 1754)
    letter = Image.new("RGB", a4, "white")
    d = ImageDraw.Draw(letter)
    d.rectangle((120, 120, 700, 200), fill=(0, 90, 170))
    for n in range(28):
        d.rectangle((120, 300 + n * 45, 1120 - (n % 4) * 120, 318 + n * 45), fill=(90, 90, 90))
    chart = Image.new("RGB", (a4[1], a4[0]), "white")
    d = ImageDraw.Draw(chart)
    for n, h in enumerate((300, 520, 410, 760, 640, 880, 700)):
        d.rectangle((150 + n * 210, 1100 - h, 300 + n * 210, 1100), fill=(40 + n * 25, 120, 200 - n * 20))
    d.line((120, 1100, 1650, 1100), fill="black", width=6)
    table = Image.new("RGB", a4, "white")
    d = ImageDraw.Draw(table)
    for r in range(18):
        for c in range(4):
            d.rectangle(
                (120 + c * 250, 200 + r * 70, 350 + c * 250, 250 + r * 70), outline=(120, 120, 120), width=3
            )
    report = os.path.join(docs, "Quarterly report.pdf")
    letter.save(report, save_all=True, append_images=[chart, table], resolution=150)

    photo = Image.new("RGB", (1800, 1200))
    d = ImageDraw.Draw(photo)
    for y in range(1200):
        d.line((0, y, 1800, y), fill=(40 + y // 10, 120 + y // 20, 220 - y // 8))
    d.ellipse((1250, 150, 1550, 450), fill=(255, 220, 120))
    d.polygon([(0, 1200), (600, 700), (1100, 1200)], fill=(50, 110, 60))
    d.polygon([(700, 1200), (1300, 800), (1800, 1200)], fill=(40, 90, 50))
    photo_path = os.path.join(pics, "Garden.jpg")
    photo.save(photo_path, quality=92)

    notes = os.path.join(docs, "Meeting notes.txt")
    with open(notes, "w") as f:
        f.write("Meeting notes\n=============\n\n")
        for n in range(1, 41):
            f.write(f"{n:2d}. Item {n}: discussed, agreed next steps and owners.\n")
    return report, photo_path, notes


def shot(window, name):
    """Save the window as PNG"""
    pump(0.6)
    gdkwin = window.get_window()
    pix = Gdk.pixbuf_get_from_window(gdkwin, 0, 0, gdkwin.get_width(), gdkwin.get_height())
    path = os.path.join(OUT, f"{name}.png")
    pix.savev(path, "png", [], [])
    print("saved", os.path.relpath(path, ROOT))


def check_one_row(flow, name):
    """The design: Ink, Connection and Look after side by side (a long value must not break the row)"""
    rows = {child.get_allocation().y for child in flow.get_children()}
    if len(rows) != 1:
        raise SystemExit(f"{name}: the three cards fell onto {len(rows)} rows")


def print_and_wait(page, timeout=60):
    """Press Print and wait for the result"""
    page.on_print()
    wait_for(lambda: page.ctx.printing.busy, 10)
    wait_for(lambda: not page.ctx.printing.busy, timeout)
    pump(0.5)
    return page.bar._done_head.get_text() or page.bar._head.get_text()


def doc_is(page, prefix):
    return page.doc_name.get_text().startswith(prefix)


def main():
    from backends.test_printer import TestPrinter
    from features import FeatureRegistry
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_print import PrintManager
    from modules.manager_settings import SettingsManager
    from modules.manager_testpage import make_test_page
    from ui.app_window import AppWindow
    from backends.usb_probe import UsbDevice
    from modules.manager_documents import add_recent
    from utils.util_logging import setup_logging

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):  # screenshots of pages that no longer exist must not linger
        if old.endswith(".png"):
            os.remove(os.path.join(OUT, old))
    report, photo, notes = sample_documents()
    settings = SettingsManager()  # sandbox ~/.config/linprinter/settings.json
    test = TestPrinter(spool=os.path.join(SANDBOX, "spool"))
    test.job_seconds = 0.5
    test.start()
    printing = PrintManager(settings, test_printer_uri=test.uri, use_cups=False, probe_usb=False)
    ctx = AppContext(settings, printing, NavigationManager(), None)
    ctx.features = FeatureRegistry(settings)
    ctx.features.set_enabled("profiles", True)
    ctx.log_path = setup_logging()
    window = AppWindow(ctx)
    window.resize(1280, 860)
    window.show_all()
    ctx.nav.navigate_to("print")
    page = ctx.nav.get_page_widget("print")
    wait_for(lambda: page.power_state == "ok")
    wait_for(lambda: window.get_window().get_height() >= 860, 10)  # every shot at the same size
    pump(1)
    shot(window, "01-print-first-run")
    ctx.nav.navigate_to("activity")
    pump(1)
    shot(window, "05a-activity-empty")
    ctx.nav.navigate_to("print")

    # 1. a report: open, preview, More options, print in black & white
    page.open_document(report)
    wait_for(lambda: doc_is(page, "Quarterly"))
    page.apply_choices({"size_stem": "na_letter"})
    pump(3)
    shot(window, "02-print-ready")
    page.toggle_more()
    page.pages.set_active("range")
    page.on_pages_choice("range")
    page.range_entry.set_text("1-2")
    pump(2.5)
    shot(window, "02b-print-more-options")
    adj = page.left.get_vadjustment()
    adj.set_value(adj.get_upper() - adj.get_page_size())  # Which, Fit and Profile
    pump(1)
    shot(window, "02c-print-more-options-end")
    adj.set_value(0)
    page.pages.set_active("all")
    page.on_pages_choice("all")
    page.toggle_more()
    page.apply_choices({"color": "monochrome", "quality": "normal"})
    test.job_seconds = 6  # long enough to see it printing
    page.on_print()
    wait_for(lambda: printing.busy, 30)
    pump(2)
    shot(window, "03-printing")
    wait_for(lambda: not printing.busy, 60)
    pump(0.5)
    shot(window, "03b-printed")
    test.job_seconds = 0.5

    # 2. a photo, borderless on 4 x 6 in glossy photo paper
    page.open_document(photo)
    wait_for(lambda: doc_is(page, "Garden"))
    page.apply_choices(
        {
            "color": "color",
            "quality": "high",
            "type": "photographic",
            "size_stem": "na_index-4x6",
            "borderless": True,
        }
    )
    pump(3)
    shot(window, "04-photo-borderless")
    print("photo:", print_and_wait(page))

    # 3. text notes, draft: Activity while it prints (then cancelled)
    page.open_document(notes)
    wait_for(lambda: doc_is(page, "Meeting"))
    page.apply_choices(
        {
            "quality": "draft",
            "color": "monochrome",
            "size_stem": "na_letter",
            "type": "stationery",
            "borderless": False,
        }
    )
    test.job_seconds = 30
    page.on_print()
    wait_for(lambda: printing.busy, 30)
    pump(1)
    ctx.nav.navigate_to("activity")
    pump(3.5)
    shot(window, "05-activity")
    ctx.nav.navigate_to("print")
    printing.cancel()
    wait_for(lambda: not printing.busy, 60)
    test.job_seconds = 0.5
    ctx.nav.navigate_to("activity")
    pump(1.5)
    shot(window, "05b-activity-history")  # printed rows and the cancelled one
    # a print lost to the USB link (staged: the test printer's link never fails), then the filter
    add_recent(
        report, page.printer.name, 3, "Black & white · Normal · Letter", result="Stopped: USB link dropped"
    )
    activity = ctx.nav.get_page_widget("activity")
    activity.filter.set_value("failed")
    activity.refresh()
    pump(1)
    shot(window, "05c-activity-didnt-print")
    activity.filter.set_value("all")
    activity.refresh()
    ctx.nav.navigate_to("print")

    # 4. Print to PDF
    pdf_printer = next(p for p in page.printers if p.key == "pdf:")
    page.select_printer(pdf_printer)
    wait_for(lambda: page.printer is not None and page.printer.key == "pdf:")
    page.open_document(report)
    wait_for(lambda: doc_is(page, "Quarterly"))
    print("pdf:", print_and_wait(page))
    shot(window, "06-print-to-pdf")
    page.select_printer(next(p for p in page.printers if p.key != "pdf:"))
    wait_for(lambda: page.printer is not None and page.printer.key != "pdf:")
    pump(1)

    # 5. the printer: health, link test, upkeep, the troubleshooter
    # (sample USB facts and a stray system queue, so the Connection card and the queue banner show)
    page.printer.usb = UsbDevice(3, 7, "04a9", "18a4", "Canon", "TR150 series", 480, "3-2")
    page.printer.notes.append(
        'The system print queue "TR150_series" sends jobs to dnssd://Canon TR150 series._ipp._tcp.local/, '
        "not to this printer, so Print in other programs fails. Remove it with: sudo lpadmin -x TR150_series"
    )
    ctx.nav.navigate_to("printer")
    printer_page = ctx.nav.get_page_widget("printer")
    pump(2)
    done = {}
    printer_page.run_test(then=lambda r: done.update(r=r))
    wait_for(lambda: done, 30)
    pump(1)
    shot(window, "07-printer")
    check_one_row(ctx.nav.get_page_widget("printer").top_cards, "07-printer")
    printer_page.start_troubleshooter(step=1)
    pump(1)
    shot(window, "07b-troubleshooter-cable")
    printer_page.step = 2
    printer_page.build_trouble()
    pump(1)
    shot(window, "07c-troubleshooter-link-test")
    printer_page.resolved = True
    printer_page.build_trouble()
    pump(1)
    shot(window, "07d-troubleshooter-fixed")
    printer_page.close_troubleshooter()
    tp = page.printer
    for kind in ("quality", "lines"):
        t = printing.test_ticket(tp, kind)
        pdf = make_test_page(
            kind, os.path.join(SANDBOX, f"{kind}.pdf"), t["size_mm"], t["margins_mm"], tp.name, t, tp.firmware
        )
        png = os.path.join(OUT, f"08-test-page-{kind}.png")
        gs = ["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m", "-r60"]
        subprocess.run(
            gs + ["-dTextAlphaBits=4", "-dGraphicsAlphaBits=4", f"-sOutputFile={png}", pdf], check=True
        )
        print("saved", os.path.relpath(png, ROOT))

    # the header menu
    window.menu_button.set_active(True)
    pump(1)
    shot(window, "15-menu")
    window.menu_button.set_active(False)

    # 6. settings: printing, privacy, about
    settings_page = ctx.nav.get_page_widget("settings")
    ctx.nav.navigate_to("settings")
    settings_page.show_section("printing")
    shot(window, "09-settings")
    settings_page.show_section("privacy")
    shot(window, "10-settings-privacy")
    settings_page.show_section("about")
    shot(window, "11-settings-about")

    # 7. paper out: Needs you, the fix in place, Print disabled with the reason, no fallback
    test.set_state(["media-empty-error"])
    ctx.nav.navigate_to("print")
    page.check_status()
    pump(2)
    shot(window, "12-paper-out")
    # paper runs out while a job prints: Needs you breaks through Busy
    test.set_state([])
    page.check_status()
    wait_for(lambda: page.status_key == "ok", 15)
    test.job_seconds = 30
    jobs_before = len(test.jobs)
    page.on_print()
    wait_for(lambda: len(test.jobs) > jobs_before, 30)  # the job is on the printer, then the paper runs out
    pump(1)
    test.set_state(["media-empty-error"])
    page.check_status()
    wait_for(lambda: page.status_key == "attention", 15)
    pump(1)
    shot(window, "12b-paper-out-while-printing")
    printing.cancel()
    wait_for(lambda: not printing.busy, 60)
    test.job_seconds = 0.5
    print("paper out:", page.why_not.get_text())
    test.set_state([])

    # 8. can't reach: the printer stops answering
    print("jobs on the test printer:", len(test.jobs))
    test.stop()
    page.check_status()
    pump(3)
    shot(window, "13-cant-reach")
    ctx.nav.navigate_to("printer")
    pump(2)
    shot(window, "14-printer-cant-reach")
    check_one_row(ctx.nav.get_page_widget("printer").top_cards, "14-printer-cant-reach")
    window.destroy()
    printing.cleanup()


if __name__ == "__main__":
    main()
