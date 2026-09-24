"""A cut-short answer must be an error, not a crash.

On 2026-09-23 the Canon TR150 answered Get-Printer-Attributes with 119 KB and the
USB link dropped it mid-message (`libusb_bulk_transfer: Input/Output Error` in the
ipp-usb log). The decoder read a length field that wasn't there and raised
struct.error, which nothing catches, so a status check crashed instead of
reporting that the printer stopped answering."""

import struct

import pytest

from backends import ipp
from backends.ipp import IppError, decode_message


def collection_message():
    """A printer answer whose attributes include a nested collection (media-col shape)"""
    out = bytearray(struct.pack(">bbhi", 2, 0, 0x0000, 1))
    out.append(ipp.PRINTER)

    def attribute(tag, name, value):
        out.append(tag)
        out.extend(struct.pack(">h", len(name)) + name.encode())
        out.extend(struct.pack(">h", len(value)) + value)

    attribute(ipp.KEYWORD, "printer-state-reasons", b"none")
    attribute(ipp.BEG_COLLECTION, "media-col-database", b"")
    attribute(ipp.MEMBER, "", b"media-size")
    attribute(ipp.BEG_COLLECTION, "", b"")
    attribute(ipp.MEMBER, "", b"x-dimension")
    attribute(ipp.INTEGER, "", struct.pack(">i", 21590))
    attribute(ipp.END_COLLECTION, "", b"")
    attribute(ipp.END_COLLECTION, "", b"")
    out.append(ipp.END)
    return bytes(out)


def test_a_whole_answer_still_decodes():
    code, request_id, groups = decode_message(collection_message())
    attrs = dict(groups[0][1])
    assert code == 0 and request_id == 1
    assert attrs["printer-state-reasons"] == "none"
    assert attrs["media-col-database"]["media-size"]["x-dimension"] == 21590


@pytest.mark.parametrize("message", [collection_message()])
def test_every_truncation_is_reported_not_crashed(message):
    """Cut the answer at every byte: each one must raise IppError and nothing else"""
    for cut in range(1, len(message)):
        with pytest.raises(IppError):
            decode_message(message[:cut])


def test_the_message_says_what_happened():
    with pytest.raises(IppError) as caught:
        decode_message(collection_message()[:-6])
    assert "cut short" in str(caught.value)
    assert caught.value.code == "error"


def test_the_full_request_is_tried_first(monkeypatch):
    """Canon answers a named media-col-database more fully than a plain "all\" """
    client = ipp.IppClient("ipp://127.0.0.1:60000/ipp/print")
    asked = []
    monkeypatch.setattr(client, "_attributes", lambda requested: asked.append(tuple(requested)) or {})
    client.get_printer_attributes()
    assert asked == [("all", "media-col-database")], "one request when the link is healthy"


def test_a_cut_short_answer_falls_back_to_the_essentials(monkeypatch):
    """The printer stays usable when only the huge extra can't be read"""
    client = ipp.IppClient("ipp://127.0.0.1:60000/ipp/print")
    asked = []

    def fake(requested):
        asked.append(tuple(requested))
        if "media-col-database" in requested:  # the big one, whole or alone
            raise IppError(ipp.TRUNCATED, code="error")
        return {"printer-make-and-model": "Canon TR150 series", "printer-state": 3}

    monkeypatch.setattr(client, "_attributes", fake)
    attrs = client.get_printer_attributes()
    assert attrs["printer-make-and-model"] == "Canon TR150 series"
    assert asked == [("all", "media-col-database"), ("all",), ("media-col-database",)]


def test_the_printer_is_still_reported_unreachable_when_nothing_answers(monkeypatch):
    """A fallback must not turn a dead printer into a working one"""
    client = ipp.IppClient("ipp://127.0.0.1:60000/ipp/print")

    def dead(requested):
        raise IppError("The printer didn't answer (timed out).", code="unreachable")

    monkeypatch.setattr(client, "_attributes", dead)
    with pytest.raises(IppError):
        client.get_printer_attributes()
