"""IPP codec round-trips and interoperability with CUPS' ipptool"""

import shutil
import subprocess

import pytest

from backends import ipp
from backends.test_printer import TestPrinter
from conftest import requires_ipptool


def test_request_round_trip():
    data = ipp.encode_request(
        0x0002,
        7,
        [
            (
                ipp.OPERATION,
                [
                    ("attributes-charset", ipp.CHARSET, ["utf-8"]),
                    ("attributes-natural-language", ipp.LANGUAGE, ["en"]),
                    ("printer-uri", ipp.URI, ["ipp://127.0.0.1:60000/ipp/print"]),
                ],
            ),
            (
                ipp.JOB,
                [
                    ("copies", ipp.INTEGER, [2]),
                    ("print-quality", ipp.ENUM, [5]),
                    ("media-col", ipp.BEG_COLLECTION, [[("media-type", ipp.KEYWORD, ["photographic"])]]),
                ],
            ),
        ],
    )
    code, rid, groups = ipp.decode_message(data)
    assert (code, rid) == (0x0002, 7)
    job = dict(groups)[ipp.JOB]
    assert job["copies"] == 2 and job["print-quality"] == 5
    assert job["media-col"]["media-type"] == "photographic"


def test_multiple_values_and_ranges():
    data = ipp.encode_response(
        0,
        1,
        [
            (
                ipp.PRINTER,
                [
                    ("print-quality-supported", ipp.ENUM, [3, 4, 5]),
                    ("copies-supported", ipp.RANGE, [(1, 99)]),
                    ("printer-resolution-supported", ipp.RESOLUTION, [(300, 300, 3), (600, 600, 3)]),
                ],
            )
        ],
    )
    _code, _rid, groups = ipp.decode_message(data)
    attrs = dict(groups)[ipp.PRINTER]
    assert ipp.values(attrs, "print-quality-supported") == [3, 4, 5]
    assert tuple(attrs["copies-supported"]) == (1, 99)
    assert len(ipp.values(attrs, "printer-resolution-supported")) == 2


def test_client_against_test_printer():
    t = TestPrinter()
    t.start()
    try:
        c = ipp.IppClient(t.uri)
        attrs = c.get_printer_attributes()
        assert attrs["printer-make-and-model"] == "Canon TR150 series"
        assert "image/pwg-raster" in ipp.values(attrs, "document-format-supported")
        c.identify()
        assert t.identified == 1
    finally:
        t.stop()


def test_unreachable_is_plain_error():
    with pytest.raises(ipp.IppError) as e:
        ipp.IppClient("ipp://127.0.0.1:9/ipp/print", timeout=2).get_printer_attributes()
    assert e.value.code == "unreachable"


@requires_ipptool
def test_ipptool_passes_against_test_printer():
    t = TestPrinter()
    t.start()
    try:
        test_file = "/usr/share/cups/ipptool/get-printer-attributes.test"
        if not shutil.which("ipptool"):
            pytest.skip("ipptool missing")
        out = subprocess.run(["ipptool", "-t", t.uri, test_file], capture_output=True, text=True, timeout=30)
        assert "[PASS]" in out.stdout, out.stdout + out.stderr
    finally:
        t.stop()
