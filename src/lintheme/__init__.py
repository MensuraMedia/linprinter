"""
lintheme: the shared look and building blocks of the Lin* utility apps.

    tokens   colours, type, space, sizes, motion: the single source (Graphite Night)
    css      the stylesheet for GTK 3 or GTK 4, generated from the tokens
    apply    install the stylesheet in a running app
    status   the four-state vocabulary and the message pattern
    icons    bundled Phosphor icons, recoloured to the theme
    gtk3     components and the dashboard shell for GTK 3 apps (LinPrinter, LinScanner, …)

Copy this package into an app (the universal rule is copy, not reference), then
see docs/06-ADOPTING.md.
"""

__version__ = "1.2.4"
THEME = "Graphite Night"
