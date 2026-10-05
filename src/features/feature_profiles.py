"""
Print profiles
One-click presets on the Print page ("Everyday", "Draft (saves ink)",
"Photo borderless", "Envelope", ...) plus "Save as profile…" for your own.
A preset only sets choices the printer supports; the rest stay as they are.
"""

import gi

from features import BaseFeature

BUILT_IN = {
    "Everyday": {
        "color": "color",
        "quality": "normal",
        "type": "stationery",
        "borderless": False,
        "scaling": "fit",
    },
    "Draft (saves ink)": {
        "color": "monochrome",
        "quality": "draft",
        "type": "stationery",
        "borderless": False,
    },
    "Black & White document": {"color": "monochrome", "quality": "normal", "type": "stationery"},
    "Best quality": {"color": "color", "quality": "high", "type": "stationery"},
    "Photo 4 × 6 borderless": {
        "color": "color",
        "quality": "high",
        "type": "photographic",
        "size_stem": "na_index-4x6",
        "borderless": True,
    },
    "Envelope #10": {
        "color": "monochrome",
        "quality": "normal",
        "type": "envelope",
        "size_stem": "na_number-10",
    },
}


class Feature(BaseFeature):
    """Presets for common jobs"""

    id = "profiles"
    name = "Print profiles"
    description = "One-click presets (Everyday, Draft, Photo borderless, Envelope, …) and your own."
    default_enabled = False
    order = 60

    def profiles(self):
        """Built-in and saved profiles"""
        return {**BUILT_IN, **(self.option("saved", {}) or {})}

    def extend_print_page(self, page):
        """A Profile row at the end of More options"""
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        from lintheme.gtk3 import components as ui

        row = Gtk.Box(spacing=8)
        self.combo = ui.select([("", "Choose a profile…")], "", accessible_name="Profile")
        for name in self.profiles():
            self.combo.append(name, name)
        self.combo.set_active_id("")
        self.combo.set_hexpand(True)
        self.combo.connect(
            "changed", lambda c: self.apply(page, c.get_active_id()) if c.get_active_id() else None
        )
        save = ui.button("Save as…", lambda: self.save_current(page), small=True)
        save.set_tooltip_text("Save the current choices as a profile")
        row.pack_start(self.combo, True, True, 0)
        row.pack_start(save, False, False, 0)
        page.profile_row = page.form_row("Profile", row)
        page.options_card.pack_start(page.profile_row, False, False, 0)  # last: features add, never reorder
        page.profile_row.set_no_show_all(True)
        page.ctx.on("features-changed", lambda *_: self._visibility(page))
        self._visibility(page)

    def _visibility(self, page):
        """Show the row only while the feature is on"""
        on = page.ctx.features.is_enabled(self)
        page.profile_row.set_no_show_all(not on)
        page.profile_row.show_all() if on else page.profile_row.hide()

    def apply(self, page, name):
        """Set the Print page's choices from a profile"""
        page.apply_choices(self.profiles().get(name, {}))

    def save_current(self, page):
        """Store the current choices under a name"""
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        from lintheme.gtk3 import components as ui

        dlg = Gtk.Dialog(title="Save profile", transient_for=page.ctx.window, modal=True)
        ui.css(dlg, "lt-root", "lt-dialog")
        ui.css(dlg.add_button("Cancel", Gtk.ResponseType.CANCEL), "lt-btn")
        ui.css(dlg.add_button("Save", Gtk.ResponseType.OK), "lt-btn", "lt-primary")
        dlg.set_default_response(Gtk.ResponseType.OK)
        area = dlg.get_content_area()
        area.set_border_width(20)
        area.set_spacing(10)
        area.pack_start(ui.text("Save these choices as a profile", "lt-heading"), False, False, 0)
        entry = ui.entry(placeholder="Profile name", accessible_name="Profile name", width_chars=24)
        entry.set_activates_default(True)
        area.pack_start(entry, False, False, 0)
        dlg.show_all()
        ok = dlg.run() == Gtk.ResponseType.OK and entry.get_text().strip()
        name = entry.get_text().strip()
        dlg.destroy()
        if ok:
            saved = dict(self.option("saved", {}) or {})
            saved[name] = page.choices()
            self.set_option("saved", saved)
            self.combo.append(name, name)
