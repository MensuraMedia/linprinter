"""Reconnect: it targets one verified printer and nothing else"""

import os

import pytest

from backends import usb_reset as U


def make_device(root, port, vid, pid, ifaces=(("07", "01", "02"),), config="1"):
    """A fake /sys/bus/usb/devices entry (ifaces=() means 'unconfigured')"""
    base = root / port
    base.mkdir(parents=True)
    (base / "idVendor").write_text(vid + "\n")
    (base / "idProduct").write_text(pid + "\n")
    (base / "bConfigurationValue").write_text((config + "\n") if config else "")
    (base / "authorized").write_text("1\n")
    for n, (cls, sub, proto) in enumerate(ifaces):
        i = base / f"{port}:1.{n}"
        i.mkdir()
        for name, value in (("Class", cls), ("SubClass", sub), ("Protocol", proto)):
            (i / f"bInterface{name}").write_text(value + "\n")
    return base


@pytest.fixture
def sysfs(tmp_path):
    make_device(tmp_path, "3-4", "04a9", "18a4")  # the printer
    make_device(tmp_path, "3-5", "001f", "0b21", ifaces=(("01", "01", "00"),))  # audio dongle
    return str(tmp_path)


def test_finds_the_printer_by_usb_id(sysfs):
    assert U.find_port("04a9:18a4", sysfs) == "3-4"
    assert U.find_port("04A9:18A4", sysfs) == "3-4"  # case does not matter
    assert U.find_port("9999:9999", sysfs) == ""
    assert U.usb_id_at("3-5", sysfs) == "001f:0b21"


def test_recognises_printers_and_unconfigured_devices(sysfs, tmp_path):
    assert U.is_usb_printer("3-4", sysfs)
    assert not U.is_usb_printer("3-5", sysfs)
    make_device(tmp_path, "3-9", "04a9", "18a4", ifaces=(), config="")  # the broken state
    assert U.is_usb_printer("3-9", sysfs) and not U.configured("3-9", sysfs)
    assert U.configured("3-4", sysfs)


def test_uses_the_printer_wherever_it_is_now(sysfs):
    """A stale port is harmless: the USB id decides, so the audio dongle on 3-5 is never touched"""
    ok, message = U.reset("3-5", "04a9:18a4", sysfs)
    assert ok and "connected again" in message
    assert open(os.path.join(sysfs, "3-5", "authorized")).read().strip() == "1"  # untouched


def test_refuses_another_device_when_the_printer_is_gone(sysfs, tmp_path):
    os.rename(os.path.join(sysfs, "3-4"), os.path.join(sysfs, "gone"))
    ok, message = U.reset("3-5", "04a9:18a4", sysfs)
    assert not ok and "001f:0b21" in message and "nothing was touched" in message


def test_refuses_a_device_that_is_not_a_printer(sysfs):
    ok, message = U.reset("3-5", "", sysfs)
    assert not ok and "isn't a printer" in message


def test_refuses_an_empty_port(sysfs):
    ok, message = U.reset("3-8", "9999:9999", sysfs)
    assert not ok and "not plugged in" in message


def test_follows_the_printer_to_another_port(sysfs, tmp_path):
    """Plugged into a different socket: the remembered port is stale, the USB id still finds it"""
    make_device(tmp_path, "3-7", "04a9", "18a4")
    os.rename(os.path.join(sysfs, "3-4"), os.path.join(sysfs, "moved-away"))
    assert U.find_port("04a9:18a4", sysfs) == "3-7"


def test_resets_in_place_when_no_password_is_needed(sysfs):
    """With the udev rule (authorized writable) it just works, without pkexec"""
    ok, message = U.reset("3-4", "04a9:18a4", sysfs)
    assert ok and "connected again" in message
    assert (open(os.path.join(sysfs, "3-4", "authorized")).read().strip()) == "1"


def test_shell_command_names_one_device_only(sysfs):
    cmd = U.shell_command("3-4", sysfs)
    assert cmd.count("3-4/authorized") == 2 and "3-5" not in cmd
