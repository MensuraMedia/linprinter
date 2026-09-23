#!/usr/bin/env python3
"""
LinPrinter
Document printer for Linux (driverless IPP over USB, CUPS, Print to PDF). Entry point.
"""

import argparse
import os
import sys
import tempfile

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

# Identify the app to the desktop before any window exists: WM_CLASS "linprinter"
# matches the menu entry (StartupWMClass), so the panel and Alt+Tab show its icon.
GLib.set_prgname("linprinter")
GLib.set_application_name("LinPrinter")
Gdk.set_program_class("linprinter")

from config.config_print import NETWORK_PRINTING  # noqa: E402
from config.config_themes import get_theme  # noqa: E402
from features import FeatureRegistry  # noqa: E402
from modules.app_context import AppContext  # noqa: E402
from modules.manager_navigation import NavigationManager  # noqa: E402
from modules.manager_print import PrintManager  # noqa: E402
from modules.manager_settings import SettingsManager  # noqa: E402
from modules.manager_theme_applicator import ThemeApplicator  # noqa: E402
from ui.app_window import AppWindow  # noqa: E402
from utils.util_logging import get_logger, install_excepthook, setup_logging, system_info  # noqa: E402
from utils.util_paths import read_version  # noqa: E402


def parse_args(argv):
    """Parse command-line options (--version, --test-printer, --page, --quit-after, --debug)"""
    p = argparse.ArgumentParser(
        prog="linprinter", description="Document printer (driverless IPP over USB, CUPS)"
    )
    p.add_argument("--version", action="version", version=f"LinPrinter {read_version()}")
    p.add_argument(
        "--test-printer",
        action="store_true",
        help="use only LinPrinter's built-in test printer and Print to PDF (no hardware, nothing is printed)",
    )
    p.add_argument(
        "--page",
        default="print",
        help="page to open: print, preview, queue, recent, printers, settings, about",
    )
    p.add_argument(
        "--quit-after", type=int, default=0, metavar="SECONDS", help="close automatically (for UI tests)"
    )
    p.add_argument(
        "--list-printers", action="store_true", help="print the printers LinPrinter can reach, then exit"
    )
    p.add_argument("--debug", action="store_true", help="verbose log (+ terminal)")
    p.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="document to open (PDF, image or text) - used by 'Open with LinPrinter' in the file manager",
    )
    return p.parse_args(argv)


def main(argv=None):
    """Build services and the window, run the GTK loop, clean up temporary files on exit"""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    log_path = setup_logging(debug=args.debug)
    install_excepthook()
    log = get_logger("app")
    log.info(
        "===== LinPrinter start (args: %s) =====", " ".join(sys.argv[1:] if argv is None else argv) or "none"
    )
    for line in system_info().splitlines():
        log.info("  %s", line)
    log.info("  log file: %s", log_path or "unavailable (logging disabled)")

    test = None
    if args.test_printer:
        # isolated session: throwaway settings and PDF folder, only the built-in test printer
        from backends.test_printer import TestPrinter

        tmp = tempfile.mkdtemp(prefix="linprinter-test-")
        settings = SettingsManager(path=os.path.join(tmp, "settings.json"))
        settings.override("pdf_folder", os.path.join(tmp, "prints"))
        test = TestPrinter(spool=os.path.join(tmp, "spool"))
        test.start()
        printing = PrintManager(settings, test_printer_uri=test.uri, use_cups=False, probe_usb=False)
        log.info("test printer at %s (jobs saved in %s)", test.uri, test.spool)
    else:
        settings = SettingsManager()
        printing = PrintManager(settings)

    if args.list_printers:
        for p in printing.discover():
            if p.methods:
                print(f"{p.name}\t{', '.join(m.label for m in p.methods)}")
        printing.cleanup()
        if test:
            test.stop()
        return 0

    theme = ThemeApplicator()
    theme.apply_theme(get_theme(settings.get("theme")))
    ctx = AppContext(settings, printing, NavigationManager(), theme)
    ctx.features = FeatureRegistry(settings)  # optional modules (src/features/feature_*.py)
    ctx.log_path = log_path
    log.info("network printing: %s", "on" if NETWORK_PRINTING else "off (USB only, no network discovery)")
    log.info(
        "settings: theme=%s color=%s quality=%s paper=%s type=%s scaling=%s pdf_folder=%s",
        *(
            settings.get(k)
            for k in ("theme", "color_mode", "quality", "paper", "paper_type", "scaling", "pdf_folder")
        ),
    )

    window = AppWindow(ctx)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    ctx.nav.navigate_to("print" if args.files else args.page)
    if args.files:
        # "Open with LinPrinter": open the file once the window is up (printers load in parallel)
        path = os.path.abspath(args.files[0])
        if len(args.files) > 1:
            log.info("%d files given; opening the first one (%s)", len(args.files), path)
        log.info("opening %s from the command line", path)
        GLib.idle_add(lambda: ctx.nav.get_page_widget("print").open_document(path) and False)
    if args.quit_after:
        GLib.timeout_add_seconds(args.quit_after, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        printing.cleanup()  # remove this session's temporary job files
        if test:
            test.stop()
        log.info("===== LinPrinter exit =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
