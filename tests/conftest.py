"""Test setup: make src/ importable and expose fixture paths"""

import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

requires_gs = pytest.mark.skipif(shutil.which("gs") is None, reason="ghostscript not installed")
requires_ipptool = pytest.mark.skipif(shutil.which("ipptool") is None, reason="cups-ipp-utils not installed")
requires_display = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"), reason="no display"
)


def fixture_text(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


@pytest.fixture(autouse=True)
def private_user_data(tmp_path, monkeypatch):
    """Keep tests away from the real ~/.local/share/linprinter (recent list), settings and logs"""
    if "XDG_DATA_HOME" not in os.environ or not os.environ["XDG_DATA_HOME"].startswith(str(tmp_path)):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user-data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user-config"))
