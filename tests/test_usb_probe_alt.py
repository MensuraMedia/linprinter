"""Driverless printers that hide IPP-over-USB on an alternate setting.

sysfs shows only each interface's current alternate setting. The Canon TR150
reports vendor-specific interfaces there and keeps 7/1/4 (IPP-over-USB) on
alternate setting 1, so a probe that trusts sysfs alone calls it a plain USB
printer and then tells the user to add a CUPS queue instead of pointing at the
ipp-usb service."""

import struct

from backends.usb_probe import UsbDevice, descriptor_interfaces
from modules.manager_print import unusable_hint


def interface_descriptor(number, alt, cls, sub, proto, endpoints=2):
    """A 9-byte USB interface descriptor"""
    return struct.pack("BBBBBBBBB", 9, 0x04, number, alt, endpoints, cls, sub, proto, 0)


def device_blob():
    """A TR150-shaped descriptor blob: a device descriptor, then the interfaces"""
    device = struct.pack("BB", 18, 0x01) + b"\x00" * 16
    config = struct.pack("BB", 9, 0x02) + b"\x00" * 7
    return (
        device
        + config
        + interface_descriptor(0, 0, 0x07, 0x01, 0x02)  # classic USB printer
        + interface_descriptor(1, 0, 0xFF, 0xFF, 0xFF)  # vendor-specific (what sysfs shows)
        + interface_descriptor(1, 1, 0x07, 0x01, 0x04)  # IPP-over-USB, alternate setting 1
        + interface_descriptor(2, 0, 0xFF, 0xFF, 0xFF)
        + interface_descriptor(2, 1, 0x07, 0x01, 0x04)
    )


def write_blob(tmp_path, blob):
    (tmp_path / "descriptors").write_bytes(blob)
    return str(tmp_path)


def test_reads_every_alternate_setting(tmp_path):
    found = descriptor_interfaces(write_blob(tmp_path, device_blob()))
    assert (0x07, 0x01, 0x04) in found, "IPP-over-USB is on an alternate setting"
    assert (0x07, 0x01, 0x02) in found
    assert found.count((0x07, 0x01, 0x04)) == 2  # interfaces 1 and 2


def test_missing_or_damaged_descriptors_are_not_fatal(tmp_path):
    assert descriptor_interfaces(str(tmp_path / "nothing-here")) == []
    assert descriptor_interfaces(write_blob(tmp_path, b"")) == []
    assert descriptor_interfaces(write_blob(tmp_path, b"\x00\x04\x00")) == []  # a zero length must not loop
    assert descriptor_interfaces(write_blob(tmp_path, b"\x09\x04\x00")) == []  # truncated


def a_printer(interfaces, alt_interfaces):
    return UsbDevice(
        bus=3,
        dev=79,
        vid="04a9",
        pid="18a4",
        manufacturer="Canon",
        product="TR150 series",
        speed_mbps=480,
        port_path="3-4",
        interfaces=interfaces,
        alt_interfaces=alt_interfaces,
    )


def test_the_printer_is_driverless_even_when_sysfs_hides_it():
    sysfs_only = [(0x07, 0x01, 0x02, "usblp"), (0xFF, 0xFF, 0xFF, "")]
    assert a_printer(sysfs_only, []).kinds == ["usb-printer"], "what sysfs alone can tell"
    both = a_printer(sysfs_only, [(0x07, 0x01, 0x02), (0xFF, 0xFF, 0xFF), (0x07, 0x01, 0x04)])
    assert both.kinds == ["ipp-usb", "usb-printer"]


def test_the_advice_matches_what_is_installed(monkeypatch):
    import modules.manager_print as M

    driverless = a_printer([(0x07, 0x01, 0x02, "")], [(0x07, 0x01, 0x04)])
    monkeypatch.setattr(M, "ipp_usb_installed", lambda: True)
    installed = unusable_hint(driverless)
    assert "Reconnect" in installed and "apt install" not in installed

    monkeypatch.setattr(M, "ipp_usb_installed", lambda: False)
    assert "apt install ipp-usb" in unusable_hint(driverless)

    plain = a_printer([(0x07, 0x01, 0x02, "usblp")], [(0x07, 0x01, 0x02)])
    assert "CUPS queue" in unusable_hint(plain)
