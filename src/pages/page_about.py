"""
About Page
What LinPrinter is, compatibility (ever evolving), privacy and licence in
brief, where your files are, shortcuts, system versions and credits.
"""

import os
import platform

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from pages.page_base import BasePage  # noqa: E402
from utils.util_logging import package_version  # noqa: E402
from utils.util_paths import APP_ROOT, read_version  # noqa: E402


def tilde(path):
    """A path with the home folder shown as ~"""
    home = os.path.expanduser("~")
    return "~" + path[len(home) :] if path.startswith(home) else path


class AboutPage(BasePage):
    """About LinPrinter"""

    def _text(self, card, text, css="secondary", selectable=False):
        """A wrapped label"""
        card.pack_start(self.label(text, css, wrap=True, selectable=selectable), False, False, 0)

    def _grid(self, card, rows):
        """Two-column key / value grid"""
        grid = Gtk.Grid(column_spacing=18, row_spacing=3)
        for n, (key, value) in enumerate(rows):
            grid.attach(self.label(key, "info-key"), 0, n, 1, 1)
            val = self.label(value, "info-value", wrap=True, selectable=True)
            val.set_hexpand(True)
            grid.attach(val, 1, n, 1, 1)
        card.pack_start(grid, False, False, 0)

    def build_content(self):
        """All About sections"""
        from modules.manager_documents import recent_path
        from modules.manager_settings import default_path
        from utils.util_logging import log_dir

        self.add_title("LinPrinter", f"Version {read_version()} · a document printer for Linux")
        card = self.add_card("What it is")
        self._text(
            card,
            "Print PDFs, images and text on any USB printer that Linux supports, with only the options your "
            "printer really has: copies, color or black & white, quality, pages, paper size and type, "
            "borderless and fitting. Preview exactly what will print, follow the job in the Queue, check ink "
            "levels, test and set up the printer (test pages, its own defaults, its maintenance page), or Print "
            "to PDF. A sibling of LinScanner, built the same way.",
        )
        self._text(
            card,
            "Connection: USB cable only. Wi-Fi and network printing are not supported at this time.",
            "muted",
        )

        card = self.add_card("Compatibility")
        self._text(
            card,
            "LinPrinter is ever evolving: each release adds and verifies more printers and systems. What it works with today:",
            "muted",
        )
        self._grid(
            card,
            [
                (
                    "Printers",
                    "USB printers that print driverless (IPP Everywhere / AirPrint over IPP-USB): most inkjet and laser printers since about 2015 from Canon, Epson, HP, Brother, Samsung, Xerox and others",
                ),
                ("Older printers", "Any USB printer with a CUPS queue (Gutenprint, HPLIP, vendor drivers)"),
                ("Verified", "Canon TR150 series (USB, driverless)"),
                ("Documents", "PDF, PNG, JPEG, TIFF (multi-page), BMP, GIF, plain text"),
                ("Also", "Print to PDF (no printer needed)"),
                (
                    "Systems",
                    "Linux Mint 22 (tested). Ubuntu 24.04 and other Debian-based systems with Python 3.10+, GTK 3, CUPS and Ghostscript",
                ),
                (
                    "Not yet",
                    "Wi-Fi / network printers, automatic two-sided printing, N-up and booklets (planned)",
                ),
                ("Check a printer", "Printers shows whether LinPrinter can reach your printer and how"),
            ],
        )

        card = self.add_card("Privacy")
        self._text(
            card,
            "Everything happens on this computer. LinPrinter never sends your documents or any other information "
            "to anyone: no cloud, no accounts, no telemetry, no network printer search. Documents travel only "
            "down the USB cable to your printer (or into your Print to PDF folder).",
        )

        card = self.add_card("Licence")
        self._text(
            card,
            "LinPrinter Community License (Noncommercial) 1.0. You're welcome to use it free of charge, and to "
            "copy, modify and share it for any noncommercial purpose. Commercial use needs written permission "
            "from MensuraMedia; we're happy to talk. The components LinPrinter builds on keep their own licences.",
        )
        self._text(card, f"Full text: {tilde(os.path.join(APP_ROOT, 'LICENSE'))}", "muted", selectable=True)

        card = self.add_card("Your files")
        self._grid(
            card,
            [
                ("Settings", tilde(default_path())),
                ("Print to PDF", tilde(self.ctx.settings.get("pdf_folder"))),
                ("Recent list", tilde(recent_path())),
                ("Logs (kept 14 days)", tilde(log_dir())),
                ("Jobs being prepared", "/tmp/linprinter-*/ (deleted when LinPrinter closes)"),
            ],
        )

        card = self.add_card("Handy shortcuts")
        self._grid(
            card,
            [
                ("Print", "Drop a file on the Print page to open it"),
                ("Preview", "Ctrl + mouse wheel to zoom; drag to move around; Page Up / Page Down"),
                ("Recent", "Folder icon: open in the file manager · document icon: print it again"),
            ],
        )

        card = self.add_card("System")
        try:
            gtk = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
        except Exception:
            gtk = "?"
        self._grid(
            card,
            [
                ("LinPrinter", read_version()),
                ("CUPS", package_version("cups")),
                ("cups-filters", package_version("cups-filters")),
                ("ipp-usb", package_version("ipp-usb")),
                ("Ghostscript", package_version("ghostscript")),
                ("Python", platform.python_version()),
                ("GTK", gtk),
            ],
        )

        card = self.add_card("Credits")
        self._grid(
            card,
            [
                ("Made by", "MensuraMedia · sibling of LinScanner · part of linux-peripherals"),
                ("Interface", "gtk-python-dashboard-starter by mikesdatawork"),
                ("Build process", "MensuraMedia universal-instruction-set"),
                (
                    "Printing",
                    "CUPS and cups-filters (OpenPrinting), ipp-usb (OpenPrinting), IPP Everywhere (PWG)",
                ),
                ("Rendering", "Ghostscript (Artifex), Pillow"),
                ("Icons", "Phosphor Icons by Helena Zhang and Tobias Fried (MIT licence)"),
            ],
        )
