"""
Recent (printed documents)
Every document LinPrinter prints (or saves with Print to PDF) is remembered,
newest first, in ~/.local/share/linprinter/recent.json: the file's path, when,
where to, pages and options. The list stays on this computer.
"""

import json
import os
from datetime import datetime

from utils.util_paths import data_dir

RECENT_MAX = 50


def recent_path():
    """The recent-documents list file"""
    return os.path.join(data_dir(), "recent.json")


def _saved_ts(entry):
    """When an entry was printed (epoch seconds; 0 if unknown)"""
    try:
        return datetime.fromisoformat(entry.get("printed_at", "")).timestamp()
    except ValueError:
        return 0


def recent_entries(existing_only=True):
    """Recent documents, newest first: [{path, printed_at, printer, pages, summary}]"""
    try:
        with open(recent_path()) as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return []
    entries = [e for e in entries if isinstance(e, dict) and isinstance(e.get("path"), str)]
    entries.sort(key=_saved_ts, reverse=True)
    return [e for e in entries if os.path.exists(e["path"])] if existing_only else entries


def add_recent(path, printer, pages, summary):
    """Remember a printed document (a re-printed file moves to the top)"""
    entry = {
        "path": os.path.abspath(path),
        "printed_at": datetime.now().isoformat(timespec="seconds"),
        "printer": printer,
        "pages": pages,
        "summary": summary,
    }
    entries = [entry] + [e for e in recent_entries(existing_only=False) if e["path"] != entry["path"]]
    tmp = recent_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries[:RECENT_MAX], f, indent=2)
    os.replace(tmp, recent_path())


def forget_recent(path):
    """Remove one file from the list (the file itself is not touched)"""
    entries = [e for e in recent_entries(existing_only=False) if e["path"] != path]
    with open(recent_path(), "w") as f:
        json.dump(entries, f, indent=2)


def clear_recent(older_than_days=None):
    """Empty the list, or drop entries older than N days; returns how many were removed"""
    entries = recent_entries(existing_only=False)
    keep = (
        []
        if older_than_days is None
        else [e for e in entries if _saved_ts(e) >= datetime.now().timestamp() - older_than_days * 86400]
    )
    with open(recent_path(), "w") as f:
        json.dump(keep, f, indent=2)
    return len(entries) - len(keep)
