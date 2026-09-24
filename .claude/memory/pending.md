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
