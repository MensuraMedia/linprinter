"""
Settings Page
Theme; Print to PDF folder (~/Documents/prints by default); low-ink warning
level; network printing (shown as Not Supported); feature modules;
diagnostics (log folder, save a diagnostics zip).
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, Gtk, Pango  # noqa: E402

from config.config_print import NETWORK_PRINTING  # noqa: E402
from config.config_themes import DEFAULT_THEME_ID, get_all_themes, get_theme  # noqa: E402
from pages.page_base import BasePage  # noqa: E402


def tilde(path):
    """A path with the home folder shown as ~"""
    home = os.path.expanduser("~")
    return "~" + path[len(home) :] if path and path.startswith(home) else (path or "")


class SettingsPage(BasePage):
    """User preferences (saved to ~/.config/linprinter/settings.json)"""

    def build_content(self):
        """Theme, printing, features and diagnostics cards"""
        s = self.ctx.settings
        self.add_title("Settings")

        card = self.add_card("Theme")
        self.theme_combo = Gtk.ComboBoxText()
        for tid, theme in get_all_themes().items():
            self.theme_combo.append(tid, theme.name)
        if not self.theme_combo.set_active_id(s.get("theme")):
            self.theme_combo.set_active_id(DEFAULT_THEME_ID)
        self.theme_combo.connect("changed", self.on_theme)
        row = Gtk.Box(spacing=12)
        row.pack_start(self.theme_combo, False, False, 0)
        self.swatches = Gtk.Box(spacing=6)
        row.pack_start(self.swatches, False, False, 0)
        card.pack_start(self.form_row("Color scheme", row), False, False, 0)
        self.draw_swatches(get_theme(s.get("theme")))

        card = self.add_card("Printing")
        row = Gtk.Box(spacing=10)
        self.pdf_label = self.label(tilde(s.get("pdf_folder")), "info-value", selectable=True)
        self.pdf_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        row.pack_start(self.pdf_label, True, True, 0)
        choose = Gtk.Button(label="Choose…")
        choose.set_tooltip_text("Choose the folder Print to PDF saves in")
        choose.connect("clicked", lambda *_: self.choose_pdf_folder())
        row.pack_start(choose, False, False, 0)
        card.pack_start(self.form_row("Print to PDF folder", row), False, False, 0)
        self.low_ink = Gtk.SpinButton.new_with_range(0, 50, 5)
        self.low_ink.set_value(s.get("low_ink_percent"))
        self.low_ink.set_halign(Gtk.Align.START)
        self.low_ink.connect("value-changed", lambda b: self.save("low_ink_percent", int(b.get_value())))
        box = Gtk.Box(spacing=8)
        box.pack_start(self.low_ink, False, False, 0)
        box.pack_start(self.label("% (Ink alerts warns at or below this level)", "muted"), False, False, 0)
        card.pack_start(self.form_row("Low ink", box), False, False, 0)
        row = Gtk.Box(spacing=10)
        net = Gtk.CheckButton(label="Network printing (Wi-Fi / Ethernet)")
        net.set_active(NETWORK_PRINTING)
        net.set_sensitive(False)
        row.pack_start(net, False, False, 0)
        row.pack_start(self.label("Not Supported", "muted"), False, False, 0)
        card.pack_start(row, False, False, 0)
        desc = self.label(
            "Only printers connected by USB cable are supported at this time. LinPrinter does not search the "
            "network for printers, and network print queues are not used.",
            "muted",
            wrap=True,
        )
        desc.set_margin_start(26)
        card.pack_start(desc, False, False, 0)

        if self.ctx.features:
            card = self.add_card("Features")
            card.pack_start(
                self.label(
                    "Optional modules. Turn any of them off (or delete its file in src/features/) without affecting printing.",
                    "muted",
                    wrap=True,
                ),
                False,
                False,
                0,
            )
            self.feature_checks = {}
            for feature in self.ctx.features.features:
                check = Gtk.CheckButton(label=feature.name)
                check.set_active(self.ctx.features.is_enabled(feature))
                check.connect("toggled", self.on_feature_toggled, feature)
                self.feature_checks[feature.id] = check
                card.pack_start(check, False, False, 0)
                desc = self.label(feature.description, "muted", wrap=True)
                desc.set_margin_start(26)
                card.pack_start(desc, False, False, 0)
            for name, error in self.ctx.features.errors:
                card.pack_start(self.label(f"⚠ {name}: {error}", "status-error", wrap=True), False, False, 0)

        card = self.add_card("Diagnostics")
        path = self.ctx.log_path or "logging unavailable"
        card.pack_start(
            self.label(f"Today's log: {tilde(path)}", "muted", wrap=True, selectable=True), False, False, 0
        )
        row = Gtk.Box(spacing=8)
        open_logs = Gtk.Button(label="Open log folder")
        open_logs.connect("clicked", lambda *_: self.open_log_folder())
        save = Gtk.Button(label="Save diagnostics…")
        save.set_tooltip_text(
            "A zip with recent logs, system details and printer details, saved on this computer"
        )
        save.connect("clicked", lambda *_: self.save_diagnostics())
        row.pack_start(open_logs, False, False, 0)
        row.pack_start(save, False, False, 0)
        card.pack_start(row, False, False, 0)
        self.diag_status = self.label("", "muted", wrap=True, selectable=True)
        card.pack_start(self.diag_status, False, False, 0)

    def save(self, key, value):
        """Persist a setting and broadcast settings-changed"""
        self.ctx.settings.set(key, value)
        self.ctx.emit("settings-changed", key)

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

    def on_theme(self, combo):
        """Apply and store the chosen colour scheme"""
        theme = get_theme(combo.get_active_id())
        self.ctx.theme.apply_theme(theme)
        self.save("theme", combo.get_active_id())
        self.draw_swatches(theme)

    def on_feature_toggled(self, check, feature):
        """Enable or disable a feature module"""
        if check.get_active() == self.ctx.features.is_enabled(feature):
            return
        self.ctx.features.set_enabled(feature.id, check.get_active())
        self.ctx.emit("features-changed")

    def open_log_folder(self):
        """Open the log folder in the file manager"""
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
                "theme",
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
            self.diag_status.set_text(f"Could not save diagnostics: {e}")
            return
        get_logger("ui").info("diagnostics saved to %s", path)
        self.diag_status.set_text(f"Diagnostics saved: {path}")

    def draw_swatches(self, theme):
        """Colour dots for the theme's main colours"""
        for child in self.swatches.get_children():
            self.swatches.remove(child)
        for color in (
            theme.window_bg,
            theme.card_bg,
            theme.raised_bg,
            theme.accent_color,
            theme.text_secondary,
        ):
            area = Gtk.DrawingArea()
            area.set_size_request(22, 22)
            rgba = Gdk.RGBA()
            rgba.parse(color)
            area.connect("draw", self._draw_dot, rgba)
            self.swatches.pack_start(area, False, False, 0)
        self.swatches.show_all()

    @staticmethod
    def _draw_dot(area, cr, rgba):
        """Cairo draw handler for one swatch"""
        w, h = area.get_allocated_width(), area.get_allocated_height()
        cr.arc(w / 2, h / 2, min(w, h) / 2 - 1, 0, 6.2832)
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1)
        cr.fill_preserve()
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.6)
        cr.set_line_width(1)
        cr.stroke()
