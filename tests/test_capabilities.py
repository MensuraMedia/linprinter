"""Capabilities, status and defaults from the real TR150 attributes (fixture)"""

import pytest

from backends import ipp
from backends.backend_base import capabilities_from_ipp, printer_status
from backends.test_printer import TestPrinter


@pytest.fixture(scope="module")
def attrs():
    t = TestPrinter()
    t.start()
    try:
        yield ipp.IppClient(t.uri).get_printer_attributes()
    finally:
        t.stop()


def test_tr150_capabilities(attrs):
    caps = capabilities_from_ipp(attrs)
    kws = [s.keyword for s in caps.sizes]
    assert "iso_a4_210x297mm" in kws and "na_letter_8.5x11in" in kws
    assert len(caps.sizes) >= 20
    assert caps.colors == ["color", "monochrome"]
    assert caps.qualities == ["draft", "normal", "high"]
    assert caps.copies_max == 99
    assert caps.sides == ["one-sided"]
    assert "photographic" in caps.types and "com.canon.mtgr" in caps.types
    assert caps.can_borderless("na_index-4x6_4x6in", "photographic") or caps.borderless
    assert caps.identify
    assert caps.custom_range


def test_margins(attrs):
    caps = capabilities_from_ipp(attrs)
    assert caps.margins_for("iso_a4_210x297mm", "stationery", borderless=True) == (0, 0, 0, 0)
    top, right, bottom, left = caps.margins_for("iso_a4_210x297mm", "stationery")
    assert top > 0 and left > 0


def test_printer_defaults_and_links(attrs):
    caps = capabilities_from_ipp(attrs)
    assert caps.default_size == "na_letter_8.5x11in"
    assert caps.default_type == "stationery"
    assert caps.default_color == "color"
    assert caps.default_quality == "normal"
    assert caps.alert == ""
    # the printer's own pages only when they are on this computer (ipp-usb)
    assert all(u.startswith(("http://127.0.0.1", "http://localhost")) for u in caps.links.values())
    assert set(caps.links) == {"settings", "ink"}


def test_no_network_links():
    caps = capabilities_from_ipp(
        {"printer-more-info": "http://192.168.1.20/index.html", "operations-supported": [2, 11]}
    )
    assert caps.links == {}


def test_status_and_markers(attrs):
    state, reasons, markers = printer_status(attrs)
    assert state == "idle"
    assert [m["name"] for m in markers] == ["Color", "Black"]
    assert [m["level"] for m in markers] == [60, 80]
