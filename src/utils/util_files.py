"""
Files
Small helpers for paths the user sees: the home folder shown as ~, and opening
the file manager at a file (highlighting it where the file manager supports it).
"""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")


def tilde(text):
    """Text with the home folder shown as ~"""
    home = os.path.expanduser("~")
    return text.replace(home, "~", 1) if text and home and home != "/" else text


def short_folder(path):
    """Folder part of a path, home shown as ~, ending in /"""
    return tilde(os.path.dirname(path)) + os.sep


def show_in_file_manager(path, window=None):
    """Open the file manager at the file's folder, highlighting the file if possible"""
    uri = Gio.File.new_for_path(path).get_uri()
    try:  # freedesktop FileManager1 (Nemo, Nautilus, Dolphin, Thunar, Caja...)
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "org.freedesktop.FileManager1",
            "/org/freedesktop/FileManager1",
            "org.freedesktop.FileManager1",
            "ShowItems",
            GLib.Variant("(ass)", ([uri], "")),
            None,
            Gio.DBusCallFlags.NONE,
            3000,
            None,
        )
        return True
    except GLib.Error as e:
        log.debug("FileManager1.ShowItems unavailable (%s); opening the folder", e.message)
    folder_uri = Gio.File.new_for_path(os.path.dirname(path)).get_uri()
    try:
        Gtk.show_uri_on_window(window, folder_uri, Gtk.get_current_event_time())
        return True
    except GLib.Error as e:
        log.warning("could not open the folder %s: %s", os.path.dirname(path), e.message)
        return False
