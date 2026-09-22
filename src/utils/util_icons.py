"""
Icons
Phosphor Icons v2.0.8 (Helena Zhang and Tobias Fried, MIT):
resources/icons/phosphor/regular/<name>.svg (other weights: <weight>/<name>-<weight>.svg).
The SVGs draw with currentColor, which is replaced by the theme's text colour
(or a given colour) before rendering, so icons suit light and dark themes.
Rendered pixbufs are cached per (name, size, colour, weight).

To add an icon, copy its SVG from ~/projects/assets/Icons/phosphoricons (see
its INDEX.txt for names and search tags) into resources/icons/phosphor/regular/.
"""

import functools
import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gtk  # noqa: E402

from utils.util_paths import resource  # noqa: E402

DEFAULT_COLOR = "#e6e6e6"
_theme_color = [DEFAULT_COLOR]


def set_icon_color(color):
    """Colour for icons without an explicit colour (set from the active theme)"""
    _theme_color[0] = color or DEFAULT_COLOR
    icon_pixbuf.cache_clear()


def icon_path(name, style="regular"):
    """SVG path of a bundled icon in a Phosphor weight (regular, bold, fill, ...)"""
    if style in ("regular", "outline"):
        return resource("icons", "phosphor", "regular", f"{name}.svg")
    return resource("icons", "phosphor", style, f"{name}-{style}.svg")


@functools.lru_cache(maxsize=256)
def icon_pixbuf(name, size=20, color=None, style="regular"):
    """The icon as a pixbuf of size x size pixels, drawn in color (theme text colour by default)"""
    path = icon_path(name, style)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        svg = f.read().replace("currentColor", color or _theme_color[0])
    loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
    loader.set_size(size, size)
    loader.write(svg.encode("utf-8"))
    loader.close()
    return loader.get_pixbuf()


def icon_image(name, size=20, color=None, style="regular"):
    """A Gtk.Image of the icon (a generic icon if the file is missing)"""
    pix = icon_pixbuf(name, size, color, style)
    return (
        Gtk.Image.new_from_pixbuf(pix)
        if pix
        else Gtk.Image.new_from_icon_name("image-missing", Gtk.IconSize.BUTTON)
    )


def icon_button(name, tooltip, on_click=None, size=18, toggle=False, color=None):
    """A compact, square button showing only an icon (the tooltip names the action)"""
    btn = Gtk.ToggleButton() if toggle else Gtk.Button()
    btn.add(icon_image(name, size, color))
    btn.set_tooltip_text(tooltip)  # the caption shown on hover
    btn.get_style_context().add_class("icon-button")
    btn.set_halign(Gtk.Align.START)
    btn.set_valign(Gtk.Align.CENTER)
    if on_click:
        btn.connect("toggled" if toggle else "clicked", lambda *_: on_click())
    return btn


def icon_label_button(name, label, tooltip=None, on_click=None, size=16):
    """A button with an icon followed by a short label"""
    btn = Gtk.Button()
    box = Gtk.Box(spacing=6)
    box.pack_start(icon_image(name, size), False, False, 0)
    box.pack_start(Gtk.Label(label=label), False, False, 0)
    btn.add(box)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    btn.set_halign(Gtk.Align.START)
    btn.set_valign(Gtk.Align.CENTER)
    if on_click:
        btn.connect("clicked", lambda *_: on_click())
    return btn
