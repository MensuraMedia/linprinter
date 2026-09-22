"""
Queue Page
Print jobs for the chosen printer: waiting, printing and finished, as a table
(job, document, state, pages done, how it was sent), newest first, with Cancel
for a waiting or printing job. Refreshes every few seconds while shown.
"""

from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from modules.manager_status import JOB_WORDS  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from utils.util_icons import icon_label_button  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")
C_ID, C_NAME, C_STATE, C_DONE, C_WHEN, C_METHOD, C_SORT = range(7)


class QueuePage(BasePage):
    """Print jobs"""

    def build_content(self):
        """Printer name, Cancel / Refresh, and the jobs table"""
        self.add_title("Queue", "Print jobs on the chosen printer. Finished jobs stay listed for a while.")
        row = Gtk.Box(spacing=8)
        self.cancel_btn = icon_label_button(
            "x-circle", "Cancel job", "Cancel the selected job", self.cancel_selected
        )
        row.pack_start(self.cancel_btn, False, False, 0)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", lambda *_: self.refresh())
        row.pack_start(refresh, False, False, 0)
        self.printer_label = self.label("", "muted")
        row.pack_end(self.printer_label, False, False, 0)
        self.pack_start(row, False, False, 0)

        self.store = Gtk.ListStore(str, str, str, str, str, str, float)
        self.store.set_sort_column_id(C_SORT, Gtk.SortType.DESCENDING)
        self.view = Gtk.TreeView(model=self.store)
        for title, col, width, expand in (
            ("Job", C_ID, 110, False),
            ("Document", C_NAME, 280, True),
            ("State", C_STATE, 110, False),
            ("Pages done", C_DONE, 100, False),
            ("Sent", C_WHEN, 140, False),
            ("Via", C_METHOD, 180, False),
        ):
            cell = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, cell, text=col)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(width)
            column.set_expand(expand)
            column.set_resizable(True)
            self.view.append_column(column)
        self.view.set_fixed_height_mode(True)
        self.view.get_selection().connect("changed", lambda *_: self.update_buttons())
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.add(self.view)
        self.pack_start(scroller, True, True, 0)
        self.empty = self.label("No print jobs.", "muted")
        self.empty.set_no_show_all(True)
        self.pack_start(self.empty, False, False, 0)
        self.jobs = {}
        self.ctx.on("jobs-changed", lambda *_: self.refresh())
        self.ctx.on("printer-selected", lambda *_: self.refresh())
        GLib.timeout_add_seconds(3, self._tick)
        self.update_buttons()

    def _tick(self):
        """Auto-refresh while the page is shown"""
        if self.ctx.nav.get_current_page() == "queue":
            self.refresh()
        return True

    def printer(self):
        """The printer chosen on the Print page"""
        return self.ctx.nav.get_page_widget("print").printer

    def refresh(self):
        """Read the jobs in the background"""
        printer = self.printer()
        if printer is None or printer.virtual and printer.key == "pdf:":
            self.show_jobs(printer, [])
            return

        def work():
            return self.ctx.printing.jobs(printer)

        self.ctx.printing._in_thread(
            work, lambda jobs: self.show_jobs(printer, jobs), lambda e: log.info("jobs: %s", e)
        )

    def show_jobs(self, printer, jobs):
        """Fill the table"""
        self.printer_label.set_text(printer.name if printer else "")
        selected = self.selected_id()
        self.store.clear()
        self.jobs = {}
        for j in jobs:
            key = f"{j['method'].code}:{j['id']}"
            if key in self.jobs:
                continue
            self.jobs[key] = j
            created = j.get("created") or 0
            when = datetime.fromtimestamp(created).strftime("%H:%M:%S") if created > 1e9 else ""
            self.store.append(
                [
                    key,
                    j.get("name", ""),
                    JOB_WORDS.get(j["state"], j["state"]),
                    str(j.get("done", 0)),
                    when,
                    j["method"].LABELS.get(j["method"].code, j["method"].code),
                    float(created or j["id"] if isinstance(j["id"], int) else created),
                ]
            )
        self.empty.set_visible(not jobs)
        if selected:
            for row in self.store:
                if row[C_ID] == selected:
                    self.view.get_selection().select_iter(row.iter)
        self.update_buttons()

    def selected_id(self):
        """Key of the selected row, or None"""
        model, it = self.view.get_selection().get_selected()
        return model[it][C_ID] if it else None

    def update_buttons(self):
        """Cancel only for a waiting or printing job"""
        job = self.jobs.get(self.selected_id() or "")
        self.cancel_btn.set_sensitive(
            bool(job) and job["state"] in ("pending", "pending-held", "processing", "processing-stopped")
        )

    def cancel_selected(self):
        """Cancel the selected job"""
        job = self.jobs.get(self.selected_id() or "")
        if not job:
            return

        def work():
            self.ctx.printing.cancel_job(job["method"], job["id"])

        self.ctx.printing._in_thread(work, lambda *_: self.refresh(), lambda e: log.warning("cancel: %s", e))

    def on_shown(self):
        """Refresh when opened"""
        self.refresh()
