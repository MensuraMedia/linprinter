"""
USB reconnect
Re-attaches a USB printer that the kernel left unconfigured (the classic
"printer is plugged in, nothing sees it" state: `bConfigurationValue` empty,
ipp-usb retrying "unable to find current configuration").

Detaching and re-attaching a USB device is a machine-wide kernel operation, so
it needs root. LinPrinter never holds privileges itself: it asks pkexec, which
shows the desktop's own password dialog, runs the small helper the installer
places in /usr/local/lib/linprinter, and exits. Nothing is left running.

If the installer's udev rule is in place, the device's `authorized` file is
writable by your user and no password is asked at all.
"""

import glob
import os
import re
import shutil
import subprocess
import time

from utils.util_logging import get_logger

log = get_logger("usb")

SYS_USB = "/sys/bus/usb/devices"
HELPER = "/usr/local/lib/linprinter/linprinter-usb-reset"
PRINTER_CLASS = "07"
PORT_RE = re.compile(r"\d+-\d+(\.\d+)*")  # "3-4", "3-3.2" - never an interface or a stray folder
SETTLE_SECONDS = 20  # how long to wait for the device to come back configured


def sysfs_path(port_path, sys_usb=SYS_USB):
    """/sys path of a USB device from its port ("3-4")"""
    return os.path.join(sys_usb, port_path)


def usb_id_at(port_path, sys_usb=SYS_USB):
    """ "vvvv:pppp" of the device on that port ("" if the port is empty)"""
    base = sysfs_path(port_path, sys_usb)
    try:
        with open(os.path.join(base, "idVendor")) as f:
            vid = f.read().strip()
        with open(os.path.join(base, "idProduct")) as f:
            pid = f.read().strip()
    except OSError:
        return ""
    return f"{vid}:{pid}"


def find_port(usb_id, sys_usb=SYS_USB):
    """Where that USB id is plugged in now ("" if nowhere). Survives a move to another port."""
    if not usb_id:
        return ""
    for base in sorted(glob.glob(os.path.join(sys_usb, "[0-9]*-*"))):
        if not PORT_RE.fullmatch(os.path.basename(base)):
            continue  # an interface (3-4:1.0) or something else: not a USB device
        if usb_id_at(os.path.basename(base), sys_usb).lower() == usb_id.lower():
            return os.path.basename(base)
    return ""


def is_usb_printer(port_path, sys_usb=SYS_USB):
    """True if that port holds a device with a USB printer interface (class 07)"""
    base = sysfs_path(port_path, sys_usb)
    if not os.path.isdir(base):
        return False
    for iface in glob.glob(os.path.join(base, f"{os.path.basename(base)}:*")):
        try:
            with open(os.path.join(iface, "bInterfaceClass")) as f:
                if f.read().strip() == PRINTER_CLASS:
                    return True
        except OSError:
            continue
    # an unconfigured device has no interfaces at all: trust the caller's port
    return not glob.glob(os.path.join(base, f"{os.path.basename(base)}:*"))


def configured(port_path, sys_usb=SYS_USB):
    """True when the kernel has set a configuration (the device is usable)"""
    try:
        with open(os.path.join(sysfs_path(port_path, sys_usb), "bConfigurationValue")) as f:
            return f.read().strip() not in ("", "0")
    except OSError:
        return False


def writable(port_path, sys_usb=SYS_USB):
    """True when this user may re-attach the device without a password (udev rule)"""
    return os.access(os.path.join(sysfs_path(port_path, sys_usb), "authorized"), os.W_OK)


def shell_command(port_path, sys_usb=SYS_USB):
    """The command that re-attaches the device (also shown to the user for a terminal)"""
    auth = os.path.join(sysfs_path(port_path, sys_usb), "authorized")
    return f"echo 0 > {auth}; sleep 2; echo 1 > {auth}"


def _run(argv, timeout=120):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return done.returncode, (done.stderr or done.stdout).strip()
    except subprocess.TimeoutExpired:
        return 1, "the password dialog timed out"
    except OSError as e:
        return 1, str(e)


def reset(port_path, usb_id="", sys_usb=SYS_USB):
    """Re-attach one printer's USB device. Returns (ok, message for the user).

    Only the device on that port is touched - never the whole bus, and never another
    device: the port must still hold the same printer (usb_id) and be a printer."""
    port_path = find_port(usb_id, sys_usb) or port_path  # it may have been moved to another port
    if not port_path:
        return False, "This printer isn't on USB, so there is nothing to re-attach."
    base = sysfs_path(port_path, sys_usb)
    if not os.path.isdir(base):
        return False, "The printer is not plugged in (the computer sees nothing on that port)."
    found = usb_id_at(port_path, sys_usb)
    if usb_id and found and found.lower() != usb_id.lower():
        return False, (
            f"Another device ({found}) is on that port now, so nothing was touched. "
            "Press 'Check for printers again' first."
        )
    if not is_usb_printer(port_path, sys_usb):
        return False, "That port holds something that isn't a printer, so nothing was touched."

    if writable(port_path, sys_usb):
        auth = os.path.join(base, "authorized")
        try:
            for value in ("0", "1"):
                with open(auth, "w") as f:
                    f.write(value)
                time.sleep(2)
            log.info("re-attached %s without a password (udev rule)", port_path)
        except OSError as e:
            return False, f"Could not re-attach the printer: {e}"
    elif shutil.which("pkexec"):
        if os.path.exists(HELPER):
            code, err = _run(["pkexec", HELPER, port_path, usb_id or found])
        else:
            code, err = _run(["pkexec", "/bin/sh", "-c", shell_command(port_path, sys_usb)])
        if code == 126:
            return False, "Cancelled: the printer was not re-attached."
        if code != 0:
            return False, f"Could not re-attach the printer: {err or 'permission refused'}"
        log.info("re-attached %s through pkexec", port_path)
    else:
        return False, (
            "This needs administrator rights and pkexec isn't installed. In a terminal:\n"
            f"  sudo sh -c '{shell_command(port_path, sys_usb)}'"
        )

    deadline = time.monotonic() + SETTLE_SECONDS
    while time.monotonic() < deadline:
        if configured(port_path, sys_usb):
            return True, "The printer is connected again."
        time.sleep(1)
    return False, (
        "The printer was re-attached but still isn't answering. Try another USB port and "
        "cable, or switch the printer off and on."
    )
