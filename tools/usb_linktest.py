#!/usr/bin/env python3
"""
USB link test: how many small, harmless requests to a USB device fail.

Reads the device's 18-byte device descriptor N times through usbfs and counts
failures (error -71 is a transaction that failed electrically, after the
controller's own three retries). It never sends a device anything that
changes it and never prints. Compare against a known-good device on the same
controller to tell a bad cable or device from a bad host:

  sudo python3 tools/usb_linktest.py 04a9:18a4               the printer
  sudo python3 tools/usb_linktest.py 04a9:18a4 --compare 1a40:0101

2026-10-02, Canon TR150: two faulty cables lost 13.5 % of these reads; a good
cable, same port, 0 %. A healthy link loses none. Needs root (or the lp group
for printers): usbfs nodes are not world-writable.

Standard library only (Linux usbfs ioctls, x86_64 / aarch64 layout).
"""

import argparse
import ctypes
import errno
import fcntl
import glob
import os
import struct
import sys
import time

USBDEVFS_CONTROL = 0xC0185500  # _IOWR('U', 0, struct usbdevfs_ctrltransfer) - 24 bytes on 64-bit
SYS_USB = "/sys/bus/usb/devices"


def find(usb_id, sys_root=SYS_USB):
    """[(node, port)] of the devices with this VID:PID"""
    vid, pid = usb_id.lower().split(":")
    found = []
    for d in sorted(glob.glob(os.path.join(sys_root, "*"))):
        try:
            with open(f"{d}/idVendor") as f:
                v = f.read().strip()
            with open(f"{d}/idProduct") as f:
                p = f.read().strip()
            if (v, p) != (vid, pid):
                continue
            with open(f"{d}/busnum") as f:
                bus = int(f.read())
            with open(f"{d}/devnum") as f:
                dev = int(f.read())
        except (OSError, ValueError):
            continue
        found.append((f"/dev/bus/usb/{bus:03d}/{dev:03d}", os.path.basename(d)))
    return found


def control_request(length, buf_addr, timeout_ms=1000):
    """usbdevfs_ctrltransfer for GET_DESCRIPTOR(device): IN, standard, device recipient"""
    return bytearray(struct.pack("=BBHHHI4xQ", 0x80, 6, 0x0100, 0, length, timeout_ms, buf_addr))


def verdict(ok, failed):
    """Plain words for a result"""
    total = ok + failed
    if total == 0:
        return "no answer at all"
    rate = 100 * failed / total
    if failed == 0:
        return "healthy (no failures)"
    if rate < 1:
        return f"marginal ({rate:.1f} % failed) - watch it"
    return f"FAILING ({rate:.1f} % failed) - try another cable first, then another socket"


def run(node, rounds):
    """(ok, failed, first errors) for `rounds` descriptor reads"""
    fd = os.open(node, os.O_RDWR)
    ok = failed = 0
    errors = []
    buf = ctypes.create_string_buffer(18)
    try:
        for _ in range(rounds):
            try:
                fcntl.ioctl(fd, USBDEVFS_CONTROL, control_request(18, ctypes.addressof(buf)), True)
                ok += 1
            except OSError as e:
                failed += 1
                if len(errors) < 3:
                    errors.append(e.strerror)
                if e.errno == errno.ENODEV:  # it dropped off the bus
                    break
    finally:
        os.close(fd)
    return ok, failed, errors


def report(usb_id, rounds):
    """Test every device with this id; True if all are healthy"""
    devices = find(usb_id)
    if not devices:
        print(f"{usb_id}: not on USB")
        return False
    healthy = True
    for node, port in devices:
        t0 = time.monotonic()
        try:
            ok, failed, errors = run(node, rounds)
        except PermissionError:
            print(f"{usb_id} on port {port}: permission denied - run with sudo")
            return False
        took = time.monotonic() - t0
        print(f"{usb_id} on port {port}: {ok} ok, {failed} failed in {took:.1f} s - {verdict(ok, failed)}")
        if errors:
            print(f"  errors: {', '.join(errors)}")
        healthy = healthy and failed == 0 and ok > 0
    return healthy


def main(argv=None):
    p = argparse.ArgumentParser(description="Count failed small requests on a USB link (read-only)")
    p.add_argument("usb_id", help="VID:PID of the device to test, e.g. 04a9:18a4")
    p.add_argument("--compare", metavar="VID:PID", help="a known-good device on the same controller")
    p.add_argument("--rounds", type=int, default=200)
    args = p.parse_args(argv)
    good = report(args.usb_id, args.rounds)
    if args.compare:
        report(args.compare, args.rounds)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
