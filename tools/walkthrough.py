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


def print_and_wait(page, timeout=60):
    """Press Print and wait for the result"""
    page.on_print()
    wait_for(lambda: page.ctx.printing.busy, 10)
    wait_for(lambda: not page.ctx.printing.busy, timeout)
    pump(0.5)
    return page.status.get_text()


def scroller_of(widget):
    """The ScrolledWindow a page sits in"""
    parent = widget.get_parent()
    while parent is not None and not isinstance(parent, Gtk.ScrolledWindow):
        parent = parent.get_parent()
    return parent


def main():
    from backends.test_printer import TestPrinter
    from config.config_themes import get_theme
    from features import FeatureRegistry
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_print import PrintManager
    from modules.manager_settings import SettingsManager
    from modules.manager_testpage import make_test_page
    from modules.manager_theme_applicator import ThemeApplicator
    from ui.app_window import AppWindow
    from utils.util_logging import setup_logging

    os.makedirs(OUT, exist_ok=True)
    report, photo, notes = sample_documents()
    settings = SettingsManager()  # sandbox ~/.config/linprinter/settings.json
    test = TestPrinter(spool=os.path.join(SANDBOX, "spool"))
    test.job_seconds = 0.5
    test.start()
    printing = PrintManager(settings, test_printer_uri=test.uri, use_cups=False, probe_usb=False)
    theme = ThemeApplicator()
    theme.apply_theme(get_theme(settings.get("theme")))
    ctx = AppContext(settings, printing, NavigationManager(), theme)
    ctx.features = FeatureRegistry(settings)
    ctx.features.set_enabled("profiles", True)
    ctx.log_path = setup_logging()
    window = AppWindow(ctx)
    window.resize(1180, 900)
    window.show_all()
    ctx.nav.navigate_to("print")
    page = ctx.nav.get_page_widget("print")
    wait_for(lambda: page.power_state == "ok")

    # 1. a report: open, preview, print in black & white
    page.open_document(report)
    wait_for(lambda: page.doc_label.get_text().startswith("Quarterly"))
    page.apply_choices({"size": "iso_a4_210x297mm"})
    shot(window, "01-print")
    ctx.nav.navigate_to("preview")
    pump(3)
    shot(window, "02-preview")
    preview = ctx.nav.get_page_widget("preview")
    preview.rows.set_active("2")
    preview.on_rows("2")
    pump(1.5)
    shot(window, "02b-preview-two-rows")
    preview.rows.set_active("1")
    preview.on_rows("1")
    ctx.nav.navigate_to("print")
    page.apply_choices({"color": "monochrome", "quality": "normal"})
    test.job_seconds = 6  # long enough to see it printing
    page.on_print()
    wait_for(lambda: "Printing" in page.status.get_text(), 30)
    pump(1)
    shot(window, "03-printing")
    wait_for(lambda: not printing.busy, 60)
    pump(0.5)
    shot(window, "03b-printed")
    test.job_seconds = 0.5

    # 2. a photo, borderless on 4 x 6 in glossy photo paper
    page.open_document(photo)
    wait_for(lambda: page.doc_label.get_text().startswith("Garden"))
    page.apply_choices(
        {
            "color": "color",
            "quality": "high",
            "type": "photographic",
            "size_stem": "na_index-4x6",
            "borderless": True,
        }
    )
    pump(0.5)
    shot(window, "04-photo-borderless")
    ctx.nav.navigate_to("preview")
    pump(2.5)
    shot(window, "04b-photo-preview")
    ctx.nav.navigate_to("print")
    print("photo:", print_and_wait(page))

    # 3. text notes, draft (left in the queue for the screenshot, then cancelled)
    page.open_document(notes)
    wait_for(lambda: page.doc_label.get_text().startswith("Meeting"))
    page.apply_choices(
        {
            "quality": "draft",
            "color": "monochrome",
            "size": "iso_a4_210x297mm",
            "type": "stationery",
            "borderless": False,
        }
    )
    test.job_seconds = 30
    page.on_print()
    wait_for(lambda: "Printing" in page.status.get_text(), 30)
    ctx.nav.navigate_to("queue")
    pump(2.5)
    shot(window, "05-queue")
    ctx.nav.navigate_to("print")
    printing.cancel()
    wait_for(lambda: not printing.busy, 60)
    test.job_seconds = 0.5

    # 4. Print to PDF
    page.printer_combo.set_active_id("pdf:")
    wait_for(lambda: page.printer is not None and page.printer.key == "pdf:")
    page.open_document(report)
    wait_for(lambda: page.doc_label.get_text().startswith("Quarterly"))
    print("pdf:", print_and_wait(page))
    shot(window, "06-print-to-pdf")
    page.printer_combo.set_active(0)
    wait_for(lambda: page.printer is not None and page.printer.key != "pdf:")

    # 5. printers, setup and test
    ctx.nav.navigate_to("printers")
    pump(2)
    shot(window, "07-printers")
    printers = ctx.nav.get_page_widget("printers")
    tp = page.printer
    result = {}
    printing.print_test_page(tp, "quality", lambda t: None, result.update, lambda e: result.update(error=e))
    wait_for(lambda: result, 60)
    printers.test_labels[tp.id].set_text("Test page printed. Compare it with the notes on the page.")
    scroller_of(printers).get_vadjustment().set_value(430)
    shot(window, "07b-printer-setup")
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

    # 6. recent, settings, about
    ctx.nav.navigate_to("recent")
    pump(1)
    shot(window, "09-recent")
    ctx.nav.navigate_to("settings")
    shot(window, "10-settings")
    ctx.nav.navigate_to("about")
    shot(window, "11-about")

    # 7. paper out: plain message, red mark, no fallback
    test.set_state(["media-empty-error"])
    ctx.nav.navigate_to("print")
    page.check_status()
    pump(2)
    shot(window, "12-paper-out")
    print("paper out:", page.printer_message.get_text())
    print("jobs on the test printer:", len(test.jobs))
    window.destroy()
    printing.cleanup()
    test.stop()


if __name__ == "__main__":
    main()
