"""
Settings Page (2026 redesign; About folded in)
Sections, chosen on the left:
- Printing: Print to PDF folder, the low-ink warning level, what to do at start,
  and the optional features (switches with one-line descriptions);
- Privacy and diagnostics: what stays on this computer (USB only, no network,
  no telemetry, no AI), the files LinPrinter keeps, Save diagnostics;
- About: version, what it is, compatibility, licence, system, credits, shortcuts.
There is one theme (Graphite Night), so there is no theme choice.
"""

import os
import platform

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gio, Gtk, Pango  # noqa: E402

from lintheme import tokens  # noqa: E402
from lintheme.gtk3 import components as ui  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from utils.util_files import tilde  # noqa: E402
from utils.util_logging import package_version  # noqa: E402
from utils.util_paths import APP_ROOT, read_version  # noqa: E402

SECTIONS = [("printing", "Printing"), ("privacy", "Privacy and diagnostics"), ("about", "About")]


class SettingsPage(BasePage):
    """User preferences (saved to ~/.config/linprinter/settings.json) and About"""

    def build_content(self):
        ui.css(self, "lt-page")
        for setter in (
            self.set_margin_start,
            self.set_margin_end,
            self.set_margin_top,
            self.set_margin_bottom,
        ):
            setter(0)
        self.set_spacing(16)
        self.pack_start(ui.text("Settings", "lt-title"), False, False, 0)
        body = Gtk.Box(spacing=24)
        self.pack_start(body, True, True, 0)

        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        nav.set_size_request(200, -1)
        self.section_buttons = {}
        group = None
        for key, label in SECTIONS:
            b = Gtk.RadioButton.new_with_label_from_widget(group, label)
            b.set_mode(False)
            group = group or b
            ui.css(b, "lt-tab")
            b.get_child().set_xalign(0)
            b.connect("toggled", lambda btn, k=key: btn.get_active() and self.show_section(k))
            self.section_buttons[key] = b
            nav.pack_start(b, False, False, 0)
        body.pack_start(nav, False, False, 0)

        self.sections = Gtk.Stack()
        self.sections.set_vhomogeneous(False)
        self.sections.set_hexpand(True)
        self.sections.add_named(self.printing_section(), "printing")
        self.sections.add_named(self.privacy_section(), "privacy")
        self.sections.add_named(self.about_section(), "about")
        body.pack_start(self.sections, True, True, 0)

    def show_section(self, key):
        """Open a section (the header menu's About uses this)"""
        self.sections.set_visible_child_name(key)
        b = self.section_buttons[key]
        if not b.get_active():
            b.set_active(True)

    def show_licence(self):
        """The full licence text (LICENSE.md, shipped with the app), in a dialog"""
        try:
            with open(os.path.join(APP_ROOT, "LICENSE.md"), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = "The licence file is missing from this installation. It is CC BY-NC 4.0."
        dialog = Gtk.Dialog(title="Licence", transient_for=self.ctx.window, modal=True)
        ui.css(dialog, "lt-root", "lt-dialog")
        dialog.set_default_size(720, 600)
        view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD)
        view.get_buffer().set_text(text)
        for setter in (
            view.set_left_margin,
            view.set_right_margin,
            view.set_top_margin,
            view.set_bottom_margin,
        ):
            setter(16)
        dialog.get_content_area().pack_start(ui.scrolled(view), True, True, 0)
        ui.css(dialog.add_button("Close", Gtk.ResponseType.CLOSE), "lt-btn").grab_focus()
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def save(self, key, value):
        """Persist a setting and broadcast settings-changed"""
        self.ctx.settings.set(key, value)
        self.ctx.emit("settings-changed", key)

    # -- Printing ----------------------------------------------------------------------------
    def printing_section(self):
        s = self.ctx.settings
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        card = ui.Card("Printing")
        self.pdf_label = ui.text(tilde(s.get("pdf_folder")), selectable=True)
        self.pdf_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        change = ui.button("Change…", self.choose_pdf_folder, small=True)
        change.set_tooltip_text("Choose the folder Print to PDF saves in")
        card.add_row(ui.field_row("Print to PDF folder", ui.hbox(self.pdf_label, change), label_width=200))
        self.low_ink = ui.Stepper(
            int(s.get("low_ink_percent") or 15),
            0,
            50,
            on_change=lambda v: self.save("low_ink_percent", v),
            accessible_name="Low ink level",
            unit="%",
        )
        card.add_row(
            ui.field_row(
                "Warn about low ink at",
                self.low_ink,
                "LinPrinter warns before printing when ink is at or below this level",
                label_width=200,
            )
        )
        start = ui.select(
            [("last", "Use the last printer"), ("search", "Search for printers every time")],
            "search" if s.get("search_at_start") else "last",
            lambda v: self.save("search_at_start", v == "search"),
            "When LinPrinter starts",
        )
        card.add_row(ui.field_row("When LinPrinter starts", start, label_width=200))
        box.pack_start(card, False, False, 0)

        if self.ctx.features:
            feats = ui.Card("Optional features")
            feats.add_row(
                ui.text("Each one can be turned off without affecting printing.", "lt-muted", wrap=True)
            )
            self.feature_switches = {}
            for feature in self.ctx.features.features:
                row = ui.SwitchRow(
                    feature.name,
                    feature.description,
                    self.ctx.features.is_enabled(feature),
                    lambda on, f=feature: self.on_feature(f, on),
                )
                self.feature_switches[feature.id] = row.switch
                feats.add_row(row)
            for name, error in self.ctx.features.errors:
                feats.add_row(ui.Banner("error", f"{name}: {error}"))
            box.pack_start(feats, False, False, 0)
        return box

    def choose_pdf_folder(self):
        """Folder dialog for Print to PDF"""
        dlg = Gtk.FileChooserDialog(
            title="Print to PDF folder",
            transient_for=self.ctx.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Select", Gtk.ResponseType.ACCEPT)
        current = self.ctx.settings.get("pdf_folder")
        if os.path.isdir(current):
            dlg.set_current_folder(current)
        path = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if path:
            self.set_pdf_folder(path)

    def set_pdf_folder(self, path):
        """Store the Print to PDF folder and show it"""
        self.save("pdf_folder", path)
        self.pdf_label.set_text(tilde(path))
        pdf = self.ctx.printing.printer("pdf:")
        if pdf:
            pdf.methods[0].target = path

    def on_feature(self, feature, on):
        """Enable or disable a feature module"""
        if on == self.ctx.features.is_enabled(feature):
            return
        self.ctx.features.set_enabled(feature.id, on)
        self.ctx.emit("features-changed")

    # -- Privacy and diagnostics ---------------------------------------------------------------
    def privacy_section(self):
        from modules.manager_documents import recent_path
        from modules.manager_settings import default_path
        from utils.util_logging import log_dir

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        card = ui.Card("Everything stays on this computer")
        for line in (
            "Documents go only down the USB cable to your printer, or into your Print to PDF folder.",
            "No network: LinPrinter doesn't search the network and ignores network print queues.",
            "No account, no telemetry, no update checks.",
            "No AI: LinPrinter doesn't use AI or generate content.",
        ):
            row = Gtk.Box(spacing=10)
            tick = ui.icon("check", 18, tokens.COLOR["ok"])
            tick.set_valign(Gtk.Align.START)
            row.pack_start(tick, False, False, 0)
            row.pack_start(ui.text(line, wrap=True), True, True, 0)
            card.add_row(row)
        box.pack_start(card, False, False, 0)

        files = ui.Card("What LinPrinter keeps")
        files.add_row(
            ui.key_values(
                [
                    ("Settings", tilde(default_path())),
                    ("Activity history", tilde(recent_path())),
                    ("Logs, kept 14 days (serials and home folder removed)", tilde(log_dir())),
                    ("Jobs being prepared", "/tmp/linprinter-*/ (deleted when LinPrinter closes)"),
                ]
            )
        )
        row = Gtk.Box(spacing=8)
        save = ui.button("Save diagnostics…", self.save_diagnostics, small=True)
        save.set_tooltip_text(
            "A zip with recent logs, system details and printer details, saved where you choose"
        )
        row.pack_start(save, False, False, 0)
        row.pack_start(ui.button("Open logs folder", self.open_log_folder, small=True), False, False, 0)
        files.add_row(row)
        self.diag_status = ui.text("", "lt-muted", wrap=True, selectable=True)
        files.add_row(self.diag_status)
        box.pack_start(files, False, False, 0)
        return box

    def open_log_folder(self):
        from utils.util_logging import log_dir

        folder = log_dir()
        os.makedirs(folder, exist_ok=True)
        try:
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(folder).get_uri(), None)
        except Exception as e:
            self.diag_status.set_text(f"Log folder: {folder} ({e})")

    def save_diagnostics(self):
        """Save a zip with recent logs, system info, printers and settings"""
        from datetime import datetime

        from utils.util_logging import get_logger, write_diagnostics

        dlg = Gtk.FileChooserDialog(
            title="Save diagnostics", transient_for=self.ctx.window, action=Gtk.FileChooserAction.SAVE
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.ACCEPT)
        dlg.set_do_overwrite_confirmation(True)
        dlg.set_current_folder(os.path.expanduser("~"))
        dlg.set_current_name(f"linprinter-diagnostics-{datetime.now():%Y%m%d-%H%M}.zip")
        path = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if not path:
            return
        sections = {}
        for p in self.ctx.printing.printers:
            lines = [f"methods: {', '.join(m.label for m in p.methods) or 'none'}", f"hint: {p.hint}"]
            if p.caps:
                lines.append(f"sizes: {', '.join(s.keyword for s in p.caps.sizes)}")
                lines.append(f"types: {', '.join(p.caps.types)}")
            sections[f"Printer: {p.name}"] = "\n".join(lines)
        sections["Settings"] = "\n".join(
            f"{k}: {self.ctx.settings.get(k)}"
            for k in (
                "color_mode",
                "quality",
                "paper",
                "paper_type",
                "scaling",
                "borderless",
                "low_ink_percent",
            )
        )
        try:
            write_diagnostics(path, sections)
        except OSError as e:
            self.diag_status.set_text(f"Couldn't save diagnostics: {e}")
            return
        get_logger("ui").info("diagnostics saved to %s", path)
        self.diag_status.set_text(f"Diagnostics saved: {tilde(path)}")

    # -- About -----------------------------------------------------------------------------------
    def about_section(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        card = ui.Card(f"LinPrinter {read_version()}")
        card.add_row(
            ui.text(
                "A document printer for Linux: driverless printing over USB, the system print queue as a backup, "
                "and Print to PDF. Only the options your printer really has; the preview shows exactly what will print.",
                wrap=True,
            )
        )
        card.add_row(
            ui.key_values(
                [
                    (
                        "Printers",
                        "USB printers that print driverless (IPP Everywhere / AirPrint over IPP-USB), and any USB printer with a CUPS queue",
                    ),
                    ("Verified", "Canon TR150 series (USB, driverless)"),
                    ("Documents", "PDF, PNG, JPEG, TIFF, BMP, GIF, plain text"),
                    ("Not yet", "Wi-Fi and network printers, automatic two-sided printing, N-up, booklets"),
                ]
            )
        )
        keys = ui.button("Keyboard shortcuts", lambda: self.ctx.window.show_shortcuts(), small=True)
        keys.set_halign(Gtk.Align.START)
        card.add_row(keys)
        box.pack_start(card, False, False, 0)

        lic = ui.Card("Licence")
        lic.add_row(
            ui.text(
                "Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0): free to use, share and "
                "adapt for any noncommercial purpose, with credit and a link to the licence. Commercial use needs "
                "written permission from MensuraMedia. The components LinPrinter builds on keep their own licences.",
                wrap=True,
            )
        )
        read = ui.button("Read the full licence", self.show_licence, small=True)
        read.set_halign(Gtk.Align.START)
        lic.add_row(read)
        box.pack_start(lic, False, False, 0)

        try:
            gtk = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
        except Exception:
            gtk = "?"
        system = ui.Card("System")
        system.add_row(
            ui.key_values(
                [
                    ("CUPS", package_version("cups")),
                    ("cups-filters", package_version("cups-filters")),
                    ("ipp-usb", package_version("ipp-usb")),
                    ("Ghostscript", package_version("ghostscript")),
                    ("Python", platform.python_version()),
                    ("GTK", gtk),
                ]
            )
        )
        box.pack_start(system, False, False, 0)

        credits = ui.Card("Credits")
        credits.add_row(
            ui.key_values(
                [
                    ("Made by", "MensuraMedia · sibling of LinScanner · part of linux-peripherals"),
                    ("Look", "lin-dashboard-theme (Graphite Night)"),
                    ("Printing", "CUPS, cups-filters and ipp-usb (OpenPrinting), IPP Everywhere (PWG)"),
                    ("Rendering", "Ghostscript (Artifex), Pillow"),
                    ("Icons", "Phosphor Icons by Helena Zhang and Tobias Fried (MIT)"),
                ]
            )
        )
        box.pack_start(credits, False, False, 0)
        return box
