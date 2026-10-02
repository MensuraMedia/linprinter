"""USB link health from the kernel log, how discovery reports it, and tools/usb_linktest.py"""

import os

from backends import usb_link
from backends.backend_base import PrinterDevice
from modules.manager_print import PrintManager
from modules.manager_settings import SettingsManager

# The shape of a real evening with a TR150 on a failing link (serial removed)
LOG = """\
usb 3-3: new high-speed USB device number 91 using xhci_hcd
usb 3-3: New USB device found, idVendor=04a9, idProduct=18a4, bcdDevice= 2.06
usblp 3-3:1.0: usblp3: USB Bidirectional printer dev 91 if 0 alt 0 proto 2 vid 0x04A9 pid 0x18A4
usblp3: removed
usb 3-3: USB disconnect, device number 92
usb 3-3: device descriptor read/64, error -71
usb 3-3: device not accepting address 95, error -71
usb usb3-port3: Cannot enable. Maybe the USB cable is bad?
usb usb3-port3: unable to enumerate USB device
usb 3-4.2: USB disconnect, device number 8
"""


def test_parse_counts_per_port():
    stats = usb_link.parse(LOG)
    assert stats["3-3"]["errors"] == 4  # two -71 lines, "Cannot enable", "unable to enumerate"
    assert stats["3-3"]["disconnects"] == 1
    assert stats["3-3"]["ids"] == {"04a9:18a4"}
    assert stats["3-4.2"] == {"errors": 0, "disconnects": 1, "ids": set()}
    assert "usblp3" not in stats


def test_failing_needs_more_than_one_unplug():
    stats = usb_link.parse(LOG)
    assert usb_link.failing("3-3", stats)
    assert not usb_link.failing("3-4.2", stats)  # one disconnect is just an unplug
    assert not usb_link.failing("3-9", stats)
    assert usb_link.failing_ports(stats, "04a9:18a4") == ["3-3"]
    assert usb_link.failing_ports(stats, "", "3-3") == ["3-3"]
    assert usb_link.failing_ports(stats, "1234:5678") == []
    assert "another USB cable" in usb_link.advice("3-3", stats)


def test_kernel_log_unreadable_means_nothing_known(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("no journalctl")

    monkeypatch.setattr(usb_link.subprocess, "run", boom)
    assert usb_link.kernel_log() == ""
    assert usb_link.recent() == {}


def _manager(tmp_path, info=None):
    settings = SettingsManager(str(tmp_path / "settings.json"))
    if info:
        settings.set("last_printer_info", info)
    return PrintManager(settings, use_cups=False, probe_usb=False)


def test_missing_printer_with_failing_link_gets_an_entry(tmp_path):
    pm = _manager(
        tmp_path, {"key": "usb:x", "name": "Canon TR150 series", "usb": {"id": "04a9:18a4", "port": "3-1"}}
    )
    printers = []
    pm._link_notes(printers, usb_link.parse(LOG))
    assert [p.name for p in printers] == ["Canon TR150 series"]
    assert not printers[0].methods and "port 3-3" in printers[0].hint


def test_no_entry_when_the_link_is_fine(tmp_path):
    pm = _manager(
        tmp_path, {"key": "usb:x", "name": "Canon TR150 series", "usb": {"id": "04a9:18a4", "port": "3-1"}}
    )
    printers = []
    pm._link_notes(printers, {})
    assert printers == []


def test_misdirected_queue_note(tmp_path):
    printers = [PrinterDevice(key="usb:canontr150series", name="Canon TR150 series")]
    PrintManager._misdirected_notes(printers, [("Canon_TR150_series_USB", "serial:/dev/ttyS0?baud=115200")])
    assert "serial:/dev/ttyS0" in printers[0].notes[0]
    assert "baud" not in printers[0].notes[0]
    assert "lpadmin -x Canon_TR150_series_USB" in printers[0].notes[0]


def test_unidentified_failing_port_is_reported(tmp_path):
    """2026-10-01: the printer failed before it could even give its USB id"""
    log = "usb usb3-port4: Cannot enable. Maybe the USB cable is bad?\nusb 3-4: device descriptor read/64, error -71\n"
    stats = usb_link.parse(log)
    assert usb_link.unidentified_failing_ports(stats) == ["3-4"]
    pm = _manager(
        tmp_path, {"key": "usb:x", "name": "Canon TR150 series", "usb": {"id": "04a9:18a4", "port": "3-1"}}
    )
    printers = []
    pm._link_notes(printers, stats)
    assert "port 3-4" in printers[0].hint and "another USB cable" in printers[0].hint


def test_linktest_tool(tmp_path):
    import importlib.util
    import struct

    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "usb_linktest.py"
    )
    spec = importlib.util.spec_from_file_location("usb_linktest", path)
    lt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lt)
    assert len(lt.control_request(18, 0)) == 24 == struct.calcsize("=BBHHHI4xQ")
    assert lt.verdict(200, 0).startswith("healthy")
    assert lt.verdict(173, 27).startswith("FAILING") and "cable" in lt.verdict(173, 27)
    dev = tmp_path / "3-1"
    dev.mkdir()
    for name, value in {"idVendor": "04a9", "idProduct": "18a4", "busnum": "3", "devnum": "104"}.items():
        (dev / name).write_text(value + "\n")
    assert lt.find("04A9:18A4", str(tmp_path)) == [("/dev/bus/usb/003/104", "3-1")]
