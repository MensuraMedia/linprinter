"""Open with LinPrinter: the command line takes a document, and the menu entry advertises the types"""

import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


def test_command_line_accepts_files():
    from main import parse_args

    assert parse_args(["report.pdf"]).files == ["report.pdf"]
    assert parse_args([]).files == []
    assert parse_args(["--page", "queue", "a.png", "b.png"]).files == ["a.png", "b.png"]


@pytest.mark.parametrize("source", ["install.sh", os.path.join("tools", "build-deb.sh")])
def test_desktop_entry_declares_files_and_types(source):
    text = read(source)
    exec_line = re.search(r"^Exec=(.+)$", text, re.M).group(1)
    assert exec_line.endswith("%F"), f"{source}: the menu entry must pass the selected files"
    mimes = re.search(r"^MimeType=(.+)$", text, re.M).group(1).strip(";").split(";")
    assert "application/pdf" in mimes and "text/plain" in mimes
    for t in ("image/png", "image/jpeg", "image/tiff", "image/bmp", "image/gif"):
        assert t in mimes


def test_menu_types_match_what_the_app_can_open():
    from modules.manager_render import OPENABLE

    mimes = re.search(r"^MimeType=(.+)$", read("install.sh"), re.M).group(1)
    for ext, mime in (
        (".pdf", "application/pdf"),
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".tif", "image/tiff"),
        (".bmp", "image/bmp"),
        (".gif", "image/gif"),
        (".txt", "text/plain"),
    ):
        assert ext in OPENABLE and mime in mimes


# -- auto-reconnect ------------------------------------------------------------------------------
def test_auto_reconnect_decision():
    """The Print page searches again when the printer stops answering - not too eagerly"""
    from config.config_print import RECONNECT_AFTER_MISSES, RECONNECT_EVERY
    from modules.manager_print import PrintManager

    d = PrintManager.should_reconnect
    # answering normally: never
    assert not d("ok", 0, 999, busy=False)
    assert not d("warn", 5, 999, busy=False)
    # unreachable, but not yet often enough / too soon after the last try
    assert not d("error", RECONNECT_AFTER_MISSES - 1, 999, busy=False)
    assert not d("error", RECONNECT_AFTER_MISSES, RECONNECT_EVERY - 1, busy=False)
    # unreachable often enough and long enough since the last try
    assert d("error", RECONNECT_AFTER_MISSES, RECONNECT_EVERY, busy=False)
    # never while printing, never for Print to PDF
    assert not d("error", 9, 999, busy=True)
    assert not d("error", 9, 999, busy=False, virtual=True)
