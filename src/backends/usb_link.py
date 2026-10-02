"""
USB Link
How the USB link to a printer has behaved lately, read from the kernel log:
error -71 (EPROTO, a transfer that failed electrically), failed enumeration
and disconnects, per port. No driver, setting or service cures these - they
come from the cable, the socket, power or the device's own USB port - so
LinPrinter says that in plain words instead of searching for a printer that
keeps vanishing.

Reads `journalctl -k`, which needs the adm or systemd-journal group; without
it the answer is simply "nothing known". Only port numbers and USB ids are
kept, never serial numbers.
"""

import re
import subprocess

WINDOW_MINUTES = 10
ERRORS_FAILING = 2  # connection errors in the window that count as a failing link
DISCONNECTS_FAILING = 3  # one unplug is one disconnect; three is a link that won't stay up

FAILURE = re.compile(
    r"error -71|Cannot enable|unable to enumerate|not accepting address|"
    r"can't set config|can't read configurations|device descriptor read"
)
# "usb 3-3: ..." (a device) or "usb usb3-port3: ..." (the root-hub port it sits on)
PORT = re.compile(r"\busb (?:usb(\d+)-port(\d+)|(\d+-[\d.]+)):")
IDS = re.compile(r"idVendor=([0-9a-f]{4}), idProduct=([0-9a-f]{4})")


def parse(text):
    """{port: {"errors", "disconnects", "ids"}} from kernel log lines"""
    out = {}
    for line in text.splitlines():
        m = PORT.search(line)
        if not m:
            continue
        port = m.group(3) or f"{m.group(1)}-{m.group(2)}"
        entry = out.setdefault(port, {"errors": 0, "disconnects": 0, "ids": set()})
        if FAILURE.search(line):
            entry["errors"] += 1
        elif "USB disconnect" in line:
            entry["disconnects"] += 1
        ids = IDS.search(line)
        if ids:
            entry["ids"].add(f"{ids.group(1)}:{ids.group(2)}")
    return out


def kernel_log(minutes=WINDOW_MINUTES):
    """Kernel messages of the last few minutes ("" if the journal can't be read)"""
    try:
        r = subprocess.run(
            ["journalctl", "-k", "-q", "--no-pager", "-o", "cat", "--since", f"-{minutes}min"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


def recent(minutes=WINDOW_MINUTES):
    """parse() of the recent kernel log"""
    return parse(kernel_log(minutes))


def failing(port, stats):
    """True if the link on this port has kept failing"""
    s = stats.get(port)
    return bool(s) and (s["errors"] >= ERRORS_FAILING or s["disconnects"] >= DISCONNECTS_FAILING)


def failing_ports(stats, usb_id="", port=""):
    """Failing ports that held this device (by USB id) or are its known port"""
    return [
        p
        for p, s in sorted(stats.items())
        if failing(p, stats) and (p == port or (usb_id and usb_id in s["ids"]))
    ]


def advice(port, stats, minutes=WINDOW_MINUTES):
    """What to tell the user about a failing link, in plain words"""
    s = stats.get(port) or {"errors": 0, "disconnects": 0}
    errors = f"{s['errors']} connection error" + ("" if s["errors"] == 1 else "s")
    drops = f"{s['disconnects']} disconnect" + ("" if s["disconnects"] == 1 else "s")
    return (
        f"The USB link to this printer keeps failing ({errors} and {drops} on port {port} "
        f"in the last {minutes} minutes). That is the "
        "cable, the socket or the printer's USB port, not a driver: use a short USB 2.0 cable "
        "straight into the computer, then turn the printer off and on."
    )
