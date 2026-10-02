"""
Icons: Phosphor v2.0.8 (regular weight, MIT, lintheme/icons/LICENSE-phosphor), bundled.

The SVGs draw with currentColor; it is replaced by the requested colour (by
default the theme's text colour) before rendering, so icons follow the theme
and need no icon theme installed. Toolkit-neutral: returns a GdkPixbuf, which
GTK 3 shows with Gtk.Image.new_from_pixbuf and GTK 4 with
Gtk.Picture / Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(p)).

Add an icon: copy its SVG from ~/projects/assets/Icons/phosphoricons/regular/
into lintheme/icons/ (names and search tags: that folder's INDEX.txt).
"""

import functools
import os

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

from lintheme import tokens  # noqa: E402

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def names():
    """Bundled icon names"""
    return sorted(f[:-4] for f in os.listdir(ICON_DIR) if f.endswith(".svg"))


@functools.lru_cache(maxsize=256)
def pixbuf(name, size=20, color=None):
    """The icon `name` at `size` px in `color` (default: theme text colour)"""
    path = os.path.join(ICON_DIR, f"{name}.svg")
    with open(path, encoding="utf-8") as f:
        svg = f.read().replace("currentColor", color or tokens.COLOR["text"])
    loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
    loader.set_size(size, size)
    loader.write(svg.encode())
    loader.close()
    return loader.get_pixbuf()
