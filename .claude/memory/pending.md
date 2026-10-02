# Pending

- User reports LinPrinter works well (2026-09-22). Still worth an itemised real-printer pass: quality test page,
  Color / B&W document, borderless 4×6 photo, envelope, Queue cancel.
- Fill-page scaling (SCALING has fit / none only).
- Custom paper size dialog (TR150: 55×89 to 215.9×676 mm).
- N-up, booklet, manual two-sided (roadmap 0.3+).
- Verify on another driverless USB printer and on a CUPS-driver-only printer.
- Wi-Fi / network printing: not supported; revisit only on request.
- Package: consider a signed apt repository only if the user wants auto-updates (not needed for offline use).

## Open after 0.2.7 (2026-09-24)

- **Awaiting the user's answer:** a "Set up this printer" button that creates the CUPS queue itself
  (`lpadmin` through the same polkit pattern as Reconnect), for when driverless IPP is dead but the
  classic USB printer interface is alive. Asked, not answered, not built (linux-peripherals #50).
- **Proposed:** fetch capabilities lazily — essentials during discovery, the full set when a printer is
  selected — so a ~119 KB `media-col-database` reply can't push the driverless method out of the
  5-second discovery budget (#52).
- **Backlog:** an ipp-usb quirk for the TR150 in `/etc/ipp-usb/quirks/` — `init-reset = none` and
  `usb-max-interfaces = 1`. Motivated by our own logs: ipp-usb reset the printer immediately before
  refusing it, and the fatal I/O error hit `USB[0]` while `USB[1]` was in use (#54, deferred).
- **The healthy path is still unverified end to end** — the TR150's USB link would not stay up long
  enough. The unit tests cover the decoding and fallback; a clean run against a working printer is owed.
- **No test page has ever been printed.** Never print on the real printer without the user present and
  asking.
- The host, not the app, is the likely villain for the USB faults: see `docs/HOST-USB.md` in
  linux-peripherals. Every high-speed device shares one root hub and cannot be moved off it.

## Open after 0.2.8 (2026-10-01)

- ~~TR150 USB link still failing on this host~~ RESOLVED 2026-10-02 (bad cables, see below). Was: (port 3-3, new cable: clean for 2 min, then failed to
  enumerate after a power cycle). LPM off (`usbcore.quirks=04a9:18a4:k`) changed nothing - it is set
  until reboot only. Next: the rear USB 2.0 socket; the printer on another computer (only clean test
  of the printer's own USB port). `~/projects/canon-printer/tr150-usb.sh` has the steps.
- ~~The user's document has not printed~~ printed 2026-10-02 00:54 (P1, 62 s).
- Correct `linux-peripherals/docs/HOST-USB.md` §6/§7: `init-reset` already defaults to `none` in
  ipp-usb 0.9.24, so test #1's reset rationale is moot; only `usb-max-interfaces = 1` remains.
- Misdirected-queue note not seen live yet (queue deleted before the fix).

## Link measured (2026-10-02 00:45) - SUPERSEDED at 00:52: it was the cables

`canon-printer/ipp-usb-direct.py linktest` (usbfs control requests, 200 each, no printing):
TR150 on 3-1: 27/200 descriptor reads and 23/200 SET_INTERFACE failed with -71 (13.5 % / 11.5 %,
after the xHCI's own 3 retries, so roughly half of all transactions are corrupted). The USB 2.0 hub
on 3-5, same controller, same 480 Mbit/s, one minute later: 0/200. Two cables and sockets 3-1, 3-3,
3-4 (and 3-5 in September) all fail. Conclusion: the TR150's USB port / interface; confirm on another
computer. No software path (ipp-usb, CUPS, cnijfilter2, direct usbfs) can carry a 62 MB job over it.
Also found: the legacy 7/1/2 channel speaks only `CMD:IVEC` (Canon's private language); ipp-usb
0.9.24 matches quirk sections by model name (`[Canon TR150 series]`), not `[04a9:18a4]`; with a
failing device it loops `libusb_set_configuration: Entity not found` every 2.5 s.
Left on the machine: `/etc/ipp-usb/quirks/canon-tr150.conf` (blacklist), ipp-usb stopped,
`usbcore.quirks=04a9:18a4:k` until reboot.

## RESOLVED (2026-10-02 00:52): both earlier cables were bad
The user tried a third cable. Same port 3-1, same printer: enumerated first try, the kernel configured
it itself, no -71, and `linktest` gave **0/200 and 0/200** (was 27/200 and 23/200 ten minutes
earlier). The 00:45 conclusion ("the printer's USB port") was wrong: the second cable's 2 clean
minutes at 23:18 made it look good. Lesson: a cable that works briefly is not cleared - measure it
(`linktest`) and compare against a known-good device before blaming the printer or the host.
HOST-USB.md's host theories need re-reading in this light.

## Open after 0.3.0 (2026-10-02, branch feat/0.3.0-redesign)

- Merge to main only when the user is satisfied with the redesign (their rule).
- Offline pool: run `../bin/make-offline-bundle linprinter && ../bin/test-offline linprinter` from the
  linux-peripherals checkout (new dependency `fonts-ubuntu`).
- lin-dashboard-theme: licence, git remote and first commit are the user's decision.
- The universal permissions file (blanket allow, `dontAsk`) was not deployed: the user's decision.
- Try the redesign on the real TR150 (user's go-ahead needed to print).
- Status asks for every attribute (~119 KB with media-col-database) each poll; a small request (printer-state, -reasons, marker-*, media-ready) would spare the USB link (code review, 2026-10-02).
- After a failed upload the status re-read is a full Get-Printer-Attributes (up to ~10 s on a dead link); use the small request from the item above.
