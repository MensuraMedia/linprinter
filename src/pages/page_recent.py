"""
Recent Page
Documents printed with LinPrinter (or saved with Print to PDF), as a table
sorted by date (newest first):

  Date printed | [folder] Folder | File name [document] | Printer | Pages | [trash]

- folder icon: opens the system file manager at that folder (the file is
  highlighted when the file manager supports it)
- document icon (or double-click / Enter on a row): opens the document on the
  Print page, ready to print again
- trash icon: removes the entry from the list (the file is not touched)
- Clear: All, or entries older than 5 / 10 / 20 / 30 / 60 / 90 days

Icons are Phosphor Icons. The list is stored on this computer only
(~/.local/share/linprinter/recent.json).
"""

import os
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from modules.manager_documents import clear_recent, forget_recent, recent_entries  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from utils.util_icons import icon_label_button, icon_pixbuf  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

CLEAR_CHOICES = [("all", "All")] + [(str(d), f"Older than {d} days") for d in (5, 10, 20, 30, 60, 90)]
ICON_PX = 18

# ListStore columns
C_DATE, C_SORT, C_FOLDER_ICON, C_FOLDER, C_NAME, C_DOC_ICON, C_PAGES, C_FORMAT, C_TRASH, C_PATH = range(10)


def short_path(path):
    """Folder part of a path with the home folder shown as ~"""
    folder = os.path.dirname(path)
    home = os.path.expanduser("~")
    if folder == home or folder.startswith(home + os.sep):
        folder = "~" + folder[len(home) :]
    return folder + os.sep


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


class RecentPage(BasePage):
    """Recently saved documents, as a table"""

    def build_content(self):
        """Title, Clear controls and the scrollable table"""
        self.add_title(
            "Recent",
            "Documents you printed, newest first. The folder icon opens the folder in your file manager; "
            "the document icon opens the file on the Print page to print it again.",
        )
        row = Gtk.Box(spacing=8)
        row.pack_start(self.label("Clear", "secondary"), False, False, 0)
        self.clear_combo = Gtk.ComboBoxText()
        for key, text in CLEAR_CHOICES:
            self.clear_combo.append(key, text)
        self.clear_combo.set_active_id("all")
        self.clear_combo.set_halign(Gtk.Align.START)
        row.pack_start(self.clear_combo, False, False, 0)
        self.clear_btn = icon_label_button(
            "trash", "Clear", "Remove these entries from the list (your files are not touched)", self.clear
        )
        row.pack_start(self.clear_btn, False, False, 0)
        self.count = self.label("", "muted")
        row.pack_end(self.count, False, False, 0)
        self.pack_start(row, False, False, 0)

        px = GdkPixbuf.Pixbuf
        self.store = Gtk.ListStore(str, str, px, str, str, px, int, str, px, str)
        self.store.set_sort_column_id(C_SORT, Gtk.SortType.DESCENDING)  # newest first
        self.view = Gtk.TreeView(model=self.store)
        self.view.set_enable_search(False)
        self._add_text_column("Date printed", C_DATE, 140, sort=C_SORT)
        self._add_icon_column(C_FOLDER_ICON, "open_folder", "Open the folder in your file manager")
        self._add_text_column("Folder", C_FOLDER, 200, expand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        self._add_text_column("File name", C_NAME, 200, sort=C_NAME, ellipsize=Pango.EllipsizeMode.END)
        self._add_icon_column(C_DOC_ICON, "open_document", "Open on the Print page to print it again")
        self._add_text_column("Printer", C_FORMAT, 170, ellipsize=Pango.EllipsizeMode.END)
        self._add_text_column("Pages", C_PAGES, 60, xalign=1.0)
        self._add_icon_column(C_TRASH, "forget", "Remove from this list (the file is not touched)")
        self.view.set_fixed_height_mode(True)  # uniform rows
        self.view.connect("button-press-event", self.on_click)
        self.view.connect("row-activated", lambda _v, path, _c: self.open_document(self.store[path][C_PATH]))
        self.view.connect("motion-notify-event", self.on_motion)
        self.view.set_has_tooltip(True)
        self.view.connect("query-tooltip", self.on_tooltip)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.add(self.view)
        self.pack_start(scroller, True, True, 0)
        self.empty = self.label("Nothing here yet. Documents you save will be listed here.", "muted")
        self.empty.set_no_show_all(True)
        self.pack_start(self.empty, False, False, 0)
        self.ctx.on("documents-changed", self.refresh)
        self.refresh()

    # -- columns ---------------------------------------------------------------------
    def _add_text_column(self, title, col, width, sort=None, expand=False, xalign=0.0, ellipsize=None):
        """Fixed-width text column"""
        cell = Gtk.CellRendererText()
        cell.set_property("xalign", xalign)
        if ellipsize is not None:
            cell.set_property("ellipsize", ellipsize)
        column = Gtk.TreeViewColumn(title, cell, text=col)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(width)
        column.set_expand(expand)
        column.set_resizable(True)
        if sort is not None:
            column.set_sort_column_id(sort)
        self.view.append_column(column)
        return column

    def _add_icon_column(self, col, action, tooltip):
        """Narrow column of clickable icons"""
        cell = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("", cell, pixbuf=col)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(ICON_PX + 18)
        column.action = (action, tooltip)
        self.view.append_column(column)
        return column

    def _column_at(self, x, y):
        """(row path, column) under a point of the table, or (None, None)"""
        hit = self.view.get_path_at_pos(int(x), int(y))
        return (hit[0], hit[1]) if hit else (None, None)

    # -- data -----------------------------------------------------------------------
    def on_shown(self):
        """Refresh when opened (files may have been moved or deleted)"""
        self.refresh()

    def refresh(self, *_):
        """Reload the table from the recent list (newest first)"""
        self.store.clear()
        entries = recent_entries()
        folder = icon_pixbuf("folder-open", ICON_PX)
        doc = icon_pixbuf("file-text", ICON_PX)
        trash = icon_pixbuf("trash", ICON_PX)
        for e in entries:
            try:
                saved = datetime.fromisoformat(e.get("printed_at", ""))
                shown, key = saved.strftime("%Y-%m-%d  %H:%M"), saved.isoformat()
            except ValueError:
                shown, key = "?", ""
            self.store.append(
                [
                    shown,
                    key,
                    folder,
                    short_path(e["path"]),
                    os.path.basename(e["path"]),
                    doc,
                    int(e.get("pages") or 0),
                    str(e.get("printer", "")),
                    trash,
                    e["path"],
                ]
            )
        self.store.set_sort_column_id(C_SORT, Gtk.SortType.DESCENDING)
        self.clear_btn.set_sensitive(bool(entries))
        self.empty.set_visible(not entries)
        self.count.set_text(f"{len(entries)} document(s)" if entries else "")

    # -- events ---------------------------------------------------------------------
    def on_click(self, _view, event):
        """A click on an icon cell runs its action"""
        if event.button != 1 or event.type != Gdk.EventType.BUTTON_PRESS:
            return False
        path, column = self._column_at(event.x, event.y)
        action = getattr(column, "action", None)
        if path is None or not action:
            return False
        getattr(self, action[0])(self.store[path][C_PATH])
        return True

    def on_motion(self, view, event):
        """Hand pointer over the icon cells"""
        _path, column = self._column_at(event.x, event.y)
        window = view.get_bin_window()
        name = "pointer" if getattr(column, "action", None) else None
        window.set_cursor(Gdk.Cursor.new_from_name(window.get_display(), name) if name else None)
        return False

    def on_tooltip(self, view, x, y, keyboard, tooltip):
        """Tooltips for the icon cells"""
        bx, by = view.convert_widget_to_bin_window_coords(x, y)
        path, column = self._column_at(bx, by)
        action = getattr(column, "action", None)
        if path is None or not action:
            return False
        tooltip.set_text(action[1])
        return True

    # -- actions ------------------------------------------------------------------------
    def open_folder(self, path):
        """Folder icon: the system file manager at the file's folder"""
        log.info("recent: show %s in the file manager", path)
        show_in_file_manager(path, self.ctx.window)

    def open_document(self, path):
        """Document icon: open the file on the Print page"""
        log.info("recent: open %s", path)
        self.ctx.nav.navigate_to("print")
        self.ctx.emit("open-document", path)

    def forget(self, path):
        """Trash icon: remove one entry (the file is not touched)"""
        forget_recent(path)
        self.refresh()

    def clear(self):
        """Clear all entries, or those older than the chosen number of days (after confirming)"""
        key = self.clear_combo.get_active_id() or "all"
        days = None if key == "all" else int(key)
        what = "all entries" if days is None else f"entries older than {days} days"
        dlg = Gtk.MessageDialog(
            transient_for=self.ctx.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Clear {what} from the Recent list?",
        )
        dlg.format_secondary_text("Only the list changes. Your saved files are not touched.")
        ok = dlg.run() == Gtk.ResponseType.OK
        dlg.destroy()
        if ok:
            removed = clear_recent(days)
            log.info("recent: cleared %d entr(ies) (%s)", removed, what)
            self.refresh()
