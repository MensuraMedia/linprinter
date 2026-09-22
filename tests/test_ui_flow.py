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
    from PIL import Image

    from backends.test_printer import TestPrinter
    from config.config_themes import get_theme
    from features import FeatureRegistry
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_print import PrintManager
    from modules.manager_settings import SettingsManager
    from modules.manager_theme_applicator import ThemeApplicator
    from ui.app_window import AppWindow

    settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
    settings.override("pdf_folder", str(tmp_path / "prints"))
    t = TestPrinter(spool=str(tmp_path / "spool"))
    t.job_seconds = 0.1
    t.start()
    printing = PrintManager(settings, test_printer_uri=t.uri, use_cups=False, probe_usb=False)
    theme = ThemeApplicator()
    theme.apply_theme(get_theme("default"))
    ctx = AppContext(settings, printing, NavigationManager(), theme)
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
    ctx.nav.navigate_to("preview")
    assert wait_for(lambda: ctx.nav.get_page_widget("preview").preview.strip.get_children(), 20)
    ctx.nav.navigate_to("print")
    page.on_print()
    assert wait_for(lambda: page.progress.get_fraction() == 1, 30)
    assert list(t.jobs.values())[0]["attrs"]["print-color-mode"] == "monochrome"
    for pid in ("queue", "recent", "printers", "settings", "about"):
        ctx.nav.navigate_to(pid)
        wait_for(lambda: True, 0.2)
    # the window can be made small (snap to half / quarter screen)
    min_w, _nat = window.get_preferred_width()
    assert min_w <= 900
    window.destroy()
    printing.cleanup()
    t.stop()
