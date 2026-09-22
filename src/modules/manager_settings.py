"""
Settings Manager
Loads and saves user preferences as JSON in ~/.config/linprinter/settings.json
"""

import json
import os

from config.config_print import DEFAULT_PDF_FOLDER, DEFAULT_QUALITY
from config.config_themes import DEFAULT_THEME_ID

DEFAULTS = {
    "theme": DEFAULT_THEME_ID,
    "color_mode": "color",
    "quality": DEFAULT_QUALITY,
    "paper": "",  # size keyword; empty = the printer's default
    "paper_type": "",  # media-type keyword; empty = the printer's default
    "scaling": "fit",
    "borderless": False,
    "last_printer": "",  # printer id
    "last_printer_info": {},  # the remembered printer: {"key", "name", "methods": [...]}
    "pdf_folder": DEFAULT_PDF_FOLDER,  # Print to PDF saves here
    "low_ink_percent": 15,  # warn before printing when a cartridge is at or below this
    "thumbnail_rows": 1,
    "features": {},  # feature id -> enabled (missing = the feature's default)
    "feature_settings": {},  # feature id -> {option: value}
}


def default_path():
    """Settings file path (honours XDG_CONFIG_HOME)"""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "linprinter", "settings.json")


class SettingsManager:
    """Dictionary-style access to persisted settings with defaults"""

    def __init__(self, path=None):
        """Load settings from path (default ~/.config/linprinter/settings.json)"""
        self.path = path or default_path()
        self.values = dict(DEFAULTS)
        self.overrides = {}  # session-only values (e.g. --test-printer); never saved
        self.load()

    def load(self):
        """Merge stored values over defaults, accepting only known keys of the right type"""
        try:
            with open(self.path) as f:
                stored = json.load(f)
        except (OSError, ValueError):
            return  # first run or unreadable file: keep defaults
        for key, default in DEFAULTS.items():
            if key in stored and isinstance(stored[key], type(default)):
                self.values[key] = stored[key]

    def save(self):
        """Write settings atomically (temp file + rename)"""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.values, f, indent=2)
        os.replace(tmp, self.path)

    def get(self, key):
        """Value for key: session override, then saved value, then default"""
        if key in self.overrides:
            return self.overrides[key]
        return self.values.get(key, DEFAULTS.get(key))

    def override(self, key, value):
        """Use value for this session only; it is not written to disk"""
        self.overrides[key] = value

    def set(self, key, value):
        """Store a value and save immediately"""
        self.values[key] = value
        self.save()
        from utils.util_logging import get_logger

        get_logger("settings").debug("%s = %r", key, value)
