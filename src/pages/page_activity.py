"""
Activity Page (2026 redesign: Queue and Recent merged)
Both answer "what happened to my print?":
- Now printing: the chosen printer's jobs that are waiting or printing, with
  progress and Cancel print (asks first);
- History: what was printed (or didn't print, and why), newest first, with the
  settings used; Print again (same settings, still editable), Show file,
  Remove; Clear older than… (asks first; files are never touched).
The list is stored on this computer only (~/.local/share/linprinter/recent.json).
"""

import os
import time
from datetime import datetime, timedelta

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from config.config_print import PDF_PRINTER_ID  # noqa: E402
from lintheme.gtk3 import components as ui  # noqa: E402
from modules.manager_documents import clear_recent, forget_recent, recent_entries  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from utils.util_files import show_in_file_manager, tilde  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

ACTIVE = ("pending", "pending-held", "processing", "processing-stopped")
JOB_WORDS = {
    "pending": "Waiting",
    "pending-held": "Held",
    "processing": "Printing",
    "processing-stopped": "Stopped: the printer needs you",
}
NOT_FAILURES = ("Cancelled", "Sent (not confirmed)")  # shown neutral, without Troubleshoot
FILTERS = [("all", "All"), ("ok", "Printed"), ("failed", "Didn't print")]
CLEAR_DAYS = [("30", "30 days"), ("90", "90 days"), ("365", "1 year")]


def when_words(iso):
    """'Today 00:54', 'Yesterday 18:20', '28 Sep'"""
    try:
        t = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return "?"
    today = datetime.now().date()
    if t.date() == today:
        return f"Today {t:%H:%M}"
    if t.date() == today - timedelta(days=1):
        return f"Yesterday {t:%H:%M}"
    return f"{t.day} {t:%b}" + (f" {t:%Y}" if t.year != today.year else "")


class ActivityPage(BasePage):
    """Now printing + History"""

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
        top = Gtk.Box()
        top.pack_start(
            ui.vbox(
                ui.text("Activity", "lt-title"),
                ui.text(
                    "What is printing now, and everything printed before, with the settings used.", "lt-muted"
                ),
                spacing=0,
            ),
            True,
            True,
            0,
        )
        self.clear_btn = ui.button("Clear older than…", self.clear)
        self.clear_btn.set_valign(Gtk.Align.END)
        top.pack_end(self.clear_btn, False, False, 0)
        self.pack_start(top, False, False, 0)

        self.now = ui.Card("Now printing")
        self.now_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.now.add_row(self.now_rows)
        self.pack_start(self.now, False, False, 0)

        self.history = ui.Card()
        head = Gtk.Box()
        head.pack_start(ui.text("History", "lt-heading"), True, True, 0)
        self.filter = ui.Segmented(FILTERS, "all", lambda _v: self.refresh(), "Show")
        head.pack_end(self.filter, False, False, 0)
        self.history.add_row(head)
        self.table = Gtk.Grid(column_spacing=16, row_spacing=0)
        self.history.add_row(self.table)
        self.history_note = ui.text("", "lt-muted")
        self.history.add_row(self.history_note)
        self.pack_start(self.history, False, False, 0)

        self.empty = ui.EmptyState(
            "clock-counter-clockwise",
            "Nothing printed yet",
            "Each print appears here with the settings used, so you can print it again in one click.",
            ("Go to Print", lambda: self.ctx.nav.navigate_to("print")),
        )
        self.empty.show_all()  # its insides now; show_all skips a no_show_all widget's children
        self.empty.set_no_show_all(True)
        self.empty.hide()
        self.pack_start(self.empty, True, True, 0)
        self._has_history = False
        self._jobs_request = 0

        self.jobs = []
        self._asking = False  # one jobs question at a time
        self.ctx.on("jobs-changed", lambda *_: self.refresh_jobs())
        self.ctx.on("printer-selected", lambda *_: self.refresh_jobs())
        self.ctx.on("documents-changed", lambda *_: self.refresh())
        self.ctx.on("printing", lambda busy: self.refresh_jobs())
        GLib.timeout_add_seconds(3, self._tick)

    # -- now printing ----------------------------------------------------------------------
    def _tick(self):
        if self.ctx.nav.get_current_page() == "activity" and not self._asking:
            self.refresh_jobs()
        return True

    def printer(self):
        page = self.ctx.nav.get_page_widget("print")
        return page.printer if page else None

    def refresh_jobs(self):
        """Read the chosen printer's jobs in the background"""
        printer = self.printer()
        if printer is None or (printer.virtual and printer.key == PDF_PRINTER_ID) or not printer.methods:
            self.show_jobs(printer, [])
            return
        self._asking = True
        self._jobs_request += 1
        mine = self._jobs_request

        def done(jobs):
            if mine != self._jobs_request:
                return  # a newer request is running; it clears _asking
            self._asking = False
            if printer is self.printer():  # only the newest answer counts
                self.show_jobs(printer, jobs)

        def failed(e):
            if mine == self._jobs_request:
                self._asking = False
            log.info("jobs: %s", e)

        self.ctx.printing._in_thread(lambda: self.ctx.printing.jobs(printer), done, failed)

    def show_jobs(self, printer, jobs):
        for child in self.now_rows.get_children():
            self.now_rows.remove(child)
        active, seen = [], set()
        for j in jobs:
            key = f"{j['method'].code}:{j['id']}"
            if key not in seen and j["state"] in ACTIVE:
                seen.add(key)
                active.append(j)
        self.jobs = active
        self._show_now()
        if not active:
            self.now_rows.pack_start(ui.text("Nothing is printing.", "lt-muted"), False, False, 0)
        page = self.ctx.nav.get_page_widget("print")
        mine = getattr(page, "_printing", False) and len(active) == 1  # the job the Print page started
        total = int(getattr(page, "_job_pages", 0) or 0) if mine else 0
        for j in active:
            done = int(j.get("done") or 0)
            words = JOB_WORDS.get(j["state"], j["state"])
            if total and j["state"] == "processing":
                secs = int(time.monotonic() - getattr(page, "_started", time.monotonic()))
                words = f"page {min(done + 1, total)} of {total} · {secs} s"
            elif done:
                words += f" · {done} page{'s' if done != 1 else ''} done"
            detail = f"{printer.name if printer else ''} · {words}"
            row = Gtk.Box(spacing=14)
            row.pack_start(ui.icon_tile("file-text"), False, False, 0)
            mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            line = Gtk.Box(spacing=12)
            line.pack_start(ui.text(j.get("name") or f"Job {j['id']}", "lt-strong"), False, False, 0)
            line.pack_end(ui.text(detail, "lt-muted"), False, False, 0)
            mid.pack_start(line, False, False, 0)
            bar = ui.progress(done / total if total else 0, f"{j.get('name', '')}: {words}", width=-1)
            if j["state"] == "processing" and not total:
                bar.pulse()
            mid.pack_start(bar, False, False, 0)
            row.pack_start(mid, True, True, 0)
            row.pack_start(
                ui.button("Cancel print", lambda j=j: self.cancel(j), kind="danger"), False, False, 0
            )
            self.now_rows.pack_start(row, False, False, 0)
        self.now_rows.show_all()

    def cancel(self, job):
        """Ask, then cancel one job"""
        if not ui.confirm(
            self.ctx.window,
            "Cancel this print?",
            f"“{job.get('name') or 'This job'}” stops. The printer finishes the sheet it is on.",
            "Cancel print",
            destructive=True,
            cancel_label="Keep printing",
        ):
            return
        self.ctx.printing._in_thread(
            lambda: self.ctx.printing.cancel_job(job["method"], job["id"]),
            lambda *_: self.refresh_jobs(),
            lambda e: log.warning("cancel: %s", e),
        )

    # -- history -------------------------------------------------------------------------------
    def refresh(self, *_):
        """Rebuild the history table (newest first), filtered"""
        for child in self.table.get_children():
            self.table.remove(child)
        entries = recent_entries()
        shown = self.filter.get_value()
        if shown == "ok":
            entries = [e for e in entries if e.get("result", "printed") == "printed"]
        elif shown == "failed":
            entries = [e for e in entries if e.get("result", "printed") not in ("printed",) + NOT_FAILURES]
        all_entries = recent_entries()
        self._has_history = bool(all_entries)
        self.empty.set_visible(not all_entries)
        self.history.set_visible(bool(all_entries))
        self.clear_btn.set_visible(bool(all_entries))  # as in the mockup: nothing to clear, no button
        self._show_now()
        for c, title in enumerate(("When", "Document", "Settings", "Result", "", "")):
            self.table.attach(ui.css(ui.text(title), "lt-thead"), c, 0, 1, 1)
        for r, e in enumerate(entries, start=1):
            self._row(r, e)
        self.history_note.set_text("" if entries else ("Nothing matches this filter." if all_entries else ""))
        self.table.show_all()

    def _show_now(self):
        """Now printing shows while something prints, or above a history (not on the empty page)"""
        self.now.set_visible(bool(self.jobs) or self._has_history)

    def _row(self, r, e):
        path = e["path"]
        pages = int(e.get("pages") or 0)
        result = e.get("result", "printed")
        ok = result == "printed"
        name = (
            f"{os.path.basename(path)} · {pages} p{'p' if pages != 1 else ''}"
            if pages
            else os.path.basename(path)
        )
        failed = not ok and result not in NOT_FAILURES  # cancelled by you, or sent: nothing to fix
        actions = Gtk.Box(spacing=6)
        actions.set_halign(Gtk.Align.START)  # "Print again" lines up in every row
        again = ui.button(
            "Print again", lambda p=path, c=e.get("choices"): self.print_again(p, c), small=True
        )
        again.set_tooltip_text("Open it on the Print page with the same settings; change any before printing")
        actions.pack_start(again, False, False, 0)
        if failed:
            actions.pack_start(ui.button("Troubleshoot", self.troubleshoot, small=True), False, False, 0)
        if ok:
            show = ui.button("Show file", lambda p=path: show_in_file_manager(p, self.ctx.window), small=True)
            show.set_tooltip_text(tilde(path))
            actions.pack_start(show, False, False, 0)
        remove = ui.icon_button(
            "x",
            f"Remove {os.path.basename(path)} from history (the file is kept)",
            lambda p=path: self.forget(p),
        )
        doc = ui.text(name, "lt-strong")
        doc.set_ellipsize(3)
        doc.set_tooltip_text(tilde(path))
        cells = (
            ui.text(when_words(e.get("printed_at"))),
            doc,
            ui.text(e.get("summary") or "", "lt-muted"),
            ui.pill("Printed" if ok else result, "ok" if ok else ("error" if failed else None)),
            actions,
            remove,
        )
        for c, w in enumerate(cells):
            cell = ui.css(Gtk.Box(), "lt-row")
            w.set_valign(Gtk.Align.CENTER)
            if c == 2:
                w.set_ellipsize(3)
                w.set_tooltip_text(e.get("summary") or "")
            cell.pack_start(w, c in (1, 2, 4), c in (1, 2, 4), 0)
            cell.set_hexpand(c in (1, 2))
            self.table.attach(cell, c, r, 1, 1)

    def print_again(self, path, choices):
        page = self.ctx.nav.get_page_widget("print")
        page.reprint(path, choices or None)

    def troubleshoot(self):
        self.ctx.nav.navigate_to("printer")
        page = self.ctx.nav.get_page_widget("printer")
        if hasattr(page, "start_troubleshooter"):
            page.start_troubleshooter()

    def forget(self, path):
        """Remove one entry (the file is not touched)"""
        forget_recent(path)
        self.refresh()

    def clear(self):
        """Clear entries older than 30 days, 90 days or a year (asks first, names how many)"""
        dialog = Gtk.Dialog(title="Clear history", transient_for=self.ctx.window, modal=True)
        ui.css(dialog, "lt-root", "lt-dialog")
        area = dialog.get_content_area()
        area.set_border_width(20)
        area.set_spacing(10)
        area.pack_start(ui.text("Clear prints older than…", "lt-heading"), False, False, 0)
        span = ui.Segmented(CLEAR_DAYS, "90", None, "Older than")
        span.set_halign(Gtk.Align.START)
        area.pack_start(span, False, False, 0)
        words = ui.text("", wrap=True)
        area.pack_start(words, False, False, 0)
        cancel = ui.css(dialog.add_button("Cancel", Gtk.ResponseType.CANCEL), "lt-btn")
        ok = ui.css(dialog.add_button("Clear", Gtk.ResponseType.OK), "lt-btn", "lt-danger", "lt-filled")

        def count():
            days = int(span.get_value())
            cutoff = datetime.now() - timedelta(days=days)
            n = 0
            for e in recent_entries(existing_only=False):
                try:
                    n += datetime.fromisoformat(e.get("printed_at") or "") < cutoff
                except (ValueError, TypeError):
                    n += 1
            words.set_text(
                f"Removes {n} entr{'ies' if n != 1 else 'y'} from Activity. Your documents are not deleted."
            )
            ok.set_label(f"Clear {n} entr{'ies' if n != 1 else 'y'}")
            ok.set_sensitive(n > 0)

        for b in span._buttons.values():
            b.connect("toggled", lambda *_: count())
        count()
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        cancel.grab_focus()
        dialog.show_all()
        answer = dialog.run()
        days = int(span.get_value())
        dialog.destroy()
        if answer == Gtk.ResponseType.OK:
            removed = clear_recent(days)
            log.info("activity: cleared %d entr(ies) older than %d days", removed, days)
            self.refresh()

    def on_shown(self):
        self.refresh()
        self.refresh_jobs()
