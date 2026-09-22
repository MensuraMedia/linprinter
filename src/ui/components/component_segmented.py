"""
Segmented Control
Pill-shaped group of mutually exclusive toggle buttons (e.g. Color | B&W).
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


class SegmentedControl(Gtk.Box):
    """Radio-style toggle buttons; on_changed(key) fires on user selection"""

    def __init__(self, items, active=None, on_changed=None, button_width=None):
        """items: [(key, label)]; button_width: same width for every button (uniform rows)"""
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.get_style_context().add_class("segment")
        self.set_halign(Gtk.Align.START)
        self.buttons = {}
        self.on_changed = on_changed
        self._updating = False
        for key, text in items:
            btn = Gtk.ToggleButton(label=text)
            if button_width:
                btn.set_size_request(button_width, -1)
            btn.connect("toggled", self._toggled, key)
            self.pack_start(btn, False, False, 0)
            self.buttons[key] = btn
        self.set_active(active or items[0][0])

    def _toggled(self, button, key):
        """Keep exactly one button active; report user changes"""
        if self._updating:
            return
        if not button.get_active():  # clicking the active one keeps it active
            self._updating = True
            button.set_active(True)
            self._updating = False
            return
        self.set_active(key)
        if self.on_changed:
            self.on_changed(key)

    def set_active(self, key):
        """Select a key without firing on_changed"""
        self._updating = True
        for k, btn in self.buttons.items():
            btn.set_active(k == key)
        self._updating = False
        self.active = key

    def get_active(self):
        """Currently selected key"""
        return self.active
