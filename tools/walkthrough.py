#!/usr/bin/env python3
"""
Scripted UI walkthrough with the built-in test printer (nothing is printed on real hardware).
Opens a sample document, prints it to the test printer and to PDF, and saves a screenshot of each page
to docs/screenshots/. Usage: python3 tools/walkthrough.py [out_dir]
"""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def sample_pdf(path):
    """Three pages: a letter, a landscape chart, a photo-like page"""
    from PIL import Image, ImageDraw

    pages = []
    a4 = (1240, 1754)
    letter = Image.new("RGB", a4, "white")
    d = ImageDraw.Draw(letter)
    d.rectangle((120, 120, 700, 200), fill=(0, 90, 170))
    for n in range(28):
        d.rectangle((120, 300 + n * 45, 1120 - (n % 4) * 120, 318 + n * 45), fill=(90, 90, 90))
    pages.append(letter)
    chart = Image.new("RGB", (a4[1], a4[0]), "white")
    d = ImageDraw.Draw(chart)
    for n, h in enumerate((300, 520, 410, 760, 640, 880, 700)):
        d.rectangle((150 + n * 210, 1100 - h, 300 + n * 210, 1100), fill=(40 + n * 25, 120, 200 - n * 20))
    d.line((120, 1100, 1650, 1100), fill="black", width=6)
    pages.append(chart)
    photo = Image.new("RGB", a4)
    d = ImageDraw.Draw(photo)
    for y in range(a4[1]):
        d.line((0, y, a4[0], y), fill=(30 + y // 12, 110 + y // 30, 200 - y // 12))
    d.ellipse((700, 250, 1050, 600), fill=(255, 220, 120))
    pages.append(photo)
    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=150)
    return path


def shot(window, out_dir, name):
    """Save the window as PNG"""
    pump(0.6)
    gdkwin = window.get_window()
    w, h = gdkwin.get_width(), gdkwin.get_height()
    pix = Gdk.pixbuf_get_from_window(gdkwin, 0, 0, w, h)
    path = os.path.join(out_dir, f"{name}.png")
    pix.savev(path, "png", [], [])
    print("saved", path)


def main(out_dir):
    from backends.test_printer import TestPrinter
    from config.config_themes import get_theme
    from features import FeatureRegistry
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_print import PrintManager
    from modules.manager_settings import SettingsManager
    from modules.manager_theme_applicator import ThemeApplicator
    from ui.app_window import AppWindow

    tmp = tempfile.mkdtemp(prefix="linprinter-walkthrough-")
    os.environ["XDG_DATA_HOME"] = os.path.join(tmp, "data")  # private Recent list
    settings = SettingsManager(os.path.join(tmp, "settings.json"))
    settings.override("pdf_folder", os.path.join(tmp, "prints"))
    test = TestPrinter(spool=os.path.join(tmp, "spool"))
    test.start()
    printing = PrintManager(settings, test_printer_uri=test.uri, use_cups=False, probe_usb=False)
    theme = ThemeApplicator()
    theme.apply_theme(get_theme(settings.get("theme")))
    ctx = AppContext(settings, printing, NavigationManager(), theme)
    ctx.features = FeatureRegistry(settings)
    window = AppWindow(ctx)
    window.resize(1180, 900)
    window.show_all()
    ctx.nav.navigate_to("print")
    page = ctx.nav.get_page_widget("print")
    wait_for(lambda: page.power_state == "ok")
    doc = sample_pdf(os.path.join(tmp, "sample-report.pdf"))
    page.open_document(doc)
    wait_for(lambda: page.selected_pages())
    shot(window, out_dir, "01-print")

    ctx.nav.navigate_to("preview")
    pump(3)
    shot(window, out_dir, "02-preview")

    ctx.nav.navigate_to("print")
    page.color.set_active("monochrome")
    page.quality.set_active("draft")
    page.update_summary()  # set_active() in code does not fire the change callback
    page.on_print()
    wait_for(
        lambda: page.progress.get_fraction() == 1
        or "status-error" in page.status.get_style_context().list_classes(),
        60,
    )
    print("print:", page.status.get_text())
    pump(1)
    shot(window, out_dir, "03-printed")

    ctx.nav.navigate_to("queue")
    pump(2)
    shot(window, out_dir, "04-queue")

    ctx.nav.navigate_to("printers")
    pump(2)
    shot(window, out_dir, "05-printers")
    printers = ctx.nav.get_page_widget("printers")
    scroller = (
        printers.get_parent().get_parent()
        if isinstance(printers.get_parent(), Gtk.Viewport)
        else printers.get_parent()
    )
    scroller.get_vadjustment().set_value(430)
    tp = printing.printer(page.printer.id)
    result = {}
    printing.print_test_page(
        tp, "quality", lambda t: None, lambda r: result.update(r), lambda e: result.update(error=e)
    )
    wait_for(lambda: result, 60)
    print("test page:", result, "| jobs on test printer:", len(test.jobs))
    printers.test_labels[tp.id].set_text("Test page printed. Compare it with the notes on the page.")
    shot(window, out_dir, "05b-printer-setup")
    import subprocess

    for kind in ("quality", "lines"):
        from modules.manager_testpage import make_test_page

        t = printing.test_ticket(tp, kind)
        pdf = make_test_page(
            kind, os.path.join(tmp, f"{kind}.pdf"), t["size_mm"], t["margins_mm"], tp.name, t, tp.firmware
        )
        subprocess.run(
            [
                "gs",
                "-q",
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=png16m",
                "-r50",
                f"-sOutputFile={os.path.join(out_dir, f'10-test-page-{kind}.png')}",
                pdf,
            ],
            check=True,
        )

    ctx.nav.navigate_to("recent")
    pump(1)
    shot(window, out_dir, "06-recent")

    ctx.nav.navigate_to("settings")
    shot(window, out_dir, "07-settings")
    ctx.nav.navigate_to("about")
    shot(window, out_dir, "08-about")

    test.set_state(["media-empty-error"])
    ctx.nav.navigate_to("print")
    page.check_status()
    pump(2)
    shot(window, out_dir, "09-paper-out")
    print("status:", page.printer_message.get_text() or page.status.get_text())
    print("jobs:", [(j["id"], j.get("state")) for j in test.jobs.values()])
    window.destroy()
    printing.cleanup()
    test.stop()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "screenshots"))
