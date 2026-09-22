"""
Path helpers
Locations of the app root and bundled resources, independent of the cwd.
"""

import os

APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource(*parts):
    """Absolute path of a file under resources/"""
    return os.path.join(APP_ROOT, "resources", *parts)


def read_version():
    """Version string from the VERSION file"""
    try:
        with open(os.path.join(APP_ROOT, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def data_dir(*parts):
    """Folder under ~/.local/share/linprinter (honours XDG_DATA_HOME); created on demand"""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "linprinter", *parts)
    os.makedirs(path, exist_ok=True)
    return path
