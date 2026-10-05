# Changelog

All notable changes to LinPrinter. Semantic versioning; newest first.

## 0.3.0 — 2026-10-02

- **The 2026 redesign, in Graphite Night.** Four destinations instead of seven: **Print** (the live
  preview built in), **Activity** (Queue and Recent merged: Now printing, History with the result of
  every print and Print again with its settings), **Printer** (health first: Ready · Busy · Needs you ·
  Can't reach, then ink, connection, upkeep, the printer's own defaults and details) and **Settings**
  (Printing, Privacy and diagnostics, About). A status chip in the header on every page.
- **Built on LinAppTemplate** (formerly lin-dashboard-theme; github.com/MensuraMedia/linapptemplate) (`src/lintheme`, vendored, 1.2.3): one set of tokens for colour,
  type, space and size; WCAG 2.2 AA contrast tested for every pair; targets of 32 px or more; a
  visible focus ring; every icon-only control named. Ubuntu font (`fonts-ubuntu`, a new dependency).
- **Print says why it can't print**, beside the button: "Open a document first", "Load paper first",
  "Fix the connection first". While printing, the button reads "Printing…", Cancel asks first, and the
  progress bar follows the printer's page count. The end says what happened and how long it took.
- **History tells the truth**: a cancelled job is "Cancelled", a job the printer stopped is "Stopped by
  the printer", and a print lost to the USB link is "Stopped: USB link dropped" — never "Printed".
- **Can't reach leads with the evidence and the cable**, with Troubleshoot and Test connection in
  place. The **Troubleshooter** walks six steps, cheapest first, and only calls a step the fix when
  the printer itself answers again. **Test connection** asks the printer 20 small questions (no
  password, nothing printed) and keeps the result on the Connection card.
- **The Printer page checks the printer every 5 s while it is open.** A stray system queue shows the
  exact command to remove it (copied on request; LinPrinter never holds administrator rights).
- Preview: a dashed printable-edge guide, no scroll bars at fit, an empty state that says what to do.
- **No fallback when the paper runs out at the last moment**: a job the printer refuses because it
  needs you is said in words ("Load paper in the rear tray"), never retried through the CUPS queue.
- **Uniform Output controls**: copies, colour, quality and pages share one width with equal segments.
  **Custom pages** (formerly Range): one page (`2`) or several (`1-3, 5`).
- **Dropdowns ignore the mouse wheel**: scrolling the options past Paper size or type scrolls the page
  instead of silently changing the choice (lintheme `no_wheel`, on every dropdown).
- Removed: the separate Preview, Queue, Recent, Printers and About pages (old `--page` names still
  open the matching new page), and the theme picker.

## 0.2.8 — 2026-10-01

- **A failing USB link is named, not hidden.** LinPrinter reads the last 10 minutes of the kernel log
  (`journalctl -k`) and counts connection errors (`error -71`, `Cannot enable`, failed addressing) and
  disconnects per USB port. A printer on a failing port gets a note on the Printers page and in
  `--list-printers`; a remembered printer that has dropped off the bus is still listed, with the
  reason, instead of leaving only Print to PDF: "The USB link to this printer keeps failing … That is
  the cable, the socket or the printer's USB port, not a driver."
- **No fallback onto the same broken link.** ipp-usb answers HTTP 503 when it can't move data over
  USB. That now reads "The printer's USB connection isn't carrying data … turn the printer off and on,
  or press Reconnect", and LinPrinter no longer falls back to the CUPS queue: a driverless queue goes
  through the same ipp-usb link. On 2026-10-01 that fallback spooled a 4 MB job onto a link that
  dropped every 30 seconds, and the job cut off mid-transfer left the printer hung.
- **CUPS queues are judged by where they print, not by their name.** A raw queue on
  `serial:/dev/ttyS0` called `Canon_TR150_series_USB` (the driverless queue's own name) was listed as
  a working method, because the driverless announcement with that name was read first - but `lp -d`
  reaches the permanent queue, which rejected every job. Permanent queues now decide their name; a
  cups-browsed `implicitclass://` queue resolves to the printer it stands for; a queue on `serial:`,
  `parallel:` or `file:` is reported on the matching printer with the `sudo lpadmin -x` command.
- **Cable first.** The TR150's failures turned out to be two faulty USB cables (a third cable: 0 failed
  requests where the others lost 13.5 %, and the document printed at once). Every USB message now leads
  with "try another USB cable", and a port that fails before its device can even identify itself is
  reported too ("A USB device on port 3-4 keeps failing to connect …") instead of an empty list.
- **`tools/usb_linktest.py`**: a read-only link test - 200 small descriptor reads through usbfs, failures
  counted, optionally compared with a known-good device on the same controller.
- **docs/USB-TROUBLESHOOTING.md**: the order to check things in, what each LinPrinter, kernel and ipp-usb
  message means, print-queue pitfalls, ipp-usb quirk matching (by model name, not USB id), and the
  2026-09-21 to 2026-10-02 TR150 record.
- **Licence file is `LICENSE.md`**, from the uniform CC BY-NC 4.0 rollout on main (a plain-language
  page linking the official legal code, replacing `LICENSE`). The package, the Debian copyright file,
  the About page, the README and the licence tests follow it.
- 81 tests (USB link parsing, queue sorting including the 2026-10-01 case, HTTP 503, no fallback,
  unidentified failing ports, the link-test tool).

## 0.2.7 — 2026-09-24

- **Licence changed to Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**,
  replacing the bespoke LinPrinter Community License (Noncommercial) 1.0. `LICENSE` carries a
  plain-language summary followed by the full official legal code; the README, the About page, the
  package description and the docs follow. Free to use, share and adapt for any noncommercial purpose
  with credit and a link to the licence; commercial use still needs written permission from
  MensuraMedia. The change is **not retroactive** — copies released earlier keep the terms they came
  with.
- tests/test_licence.py guards it: the licence names CC BY-NC 4.0, ships the full legal code rather
  than only the deed summary, keeps the copyright line, and no longer mentions the old licence.

## 0.2.6 — 2026-09-23

- **A cut-short answer is an error, not a crash.** When the USB link drops an IPP reply mid-message
  (`libusb_bulk_transfer: Input/Output Error` in the ipp-usb log), the decoder used to read a length
  field that wasn't there and raise `struct.error`, which nothing catches: a status check took the app
  down instead of reporting that the printer had stopped answering. Every length and value is now
  bounds-checked, and a reply that ends without its end-of-attributes tag is refused rather than
  returned as if whole - a half-read printer used to look like a printer with no paper sizes.
- **One lost extra no longer costs the printer.** Attributes are still asked for in one go (Canon
  answers a named `media-col-database` more fully than a plain "all"), but a cut-short reply now falls
  back to the small essential request and asks for the big extra separately. If only the extra fails,
  the printer keeps working and just has no borderless paper combinations.
- **Driverless printers hidden on an alternate setting are found.** sysfs shows only an interface's
  current alternate setting, and the Canon TR150 keeps IPP-over-USB (7/1/4) on alternate setting 1 of
  interfaces 1 and 2 while alternate setting 0 is vendor-specific. The probe now also parses the
  device's raw `descriptors` blob (world-readable, no root, no new dependency), so such a printer is
  no longer filed as a plain USB printer.
- **Honest advice when a printer can't be used yet.** A driverless printer on a system that *has*
  ipp-usb is now told the service isn't answering for it and pointed at Reconnect; only a system
  without ipp-usb gets the `apt install` line. A printer with no driverless interface still gets the
  CUPS-queue advice.
- `--list-printers` no longer hides a connected printer that has no working method - exactly the
  printer worth asking about. It prints `<name>  not ready — <reason>`.
- Corrected the Reconnect docstring: the installer adds no udev rule, deliberately.
- 64 tests (10 new).

## 0.2.5 — 2026-09-23

- **Reconnect**: re-attaches a printer that is plugged in but left unconfigured by the kernel (the
  "nothing sees it" state). A button next to **Find** when the mark is red, one per printer on the
  Printers page, and `run.sh --reconnect`.
  - Asks for the password through pkexec (the desktop's own dialog); no privileges are kept.
  - Touches exactly one device: the helper verifies the port still holds that printer (USB id) and
    that it is a printer, and refuses anything else, including an unrelated device that took the port.
  - The printer's USB identity (id and port) is remembered with the printer, so Reconnect works after a
    restart and follows the printer to another socket.
  - Installed by `install.sh` and the package: `/usr/local/lib/linprinter/linprinter-usb-reset` plus its
    polkit action. Without them, a plain pkexec prompt is used instead.
- tests/test_usb_reset.py: identity checks, refusals, moved printer, in-place reset.

## 0.2.4 — 2026-09-23

- **Zoom further into documents**: the maximum goes from 8× to **16×** (steps unchanged), previews are
  rendered at 140 dpi instead of 60, and zooming past a page's own resolution now keeps enlarging the
  view instead of silently stopping. One zoomed page is capped at 40 megapixels, so a big zoom can't
  eat memory.

## 0.2.3 — 2026-09-23

- **Keeps the printer connection by itself.** When the printer stops answering, the Print page now
  searches again quietly (after 2 failed checks, at most every 20 s), keeps your selection, and shows
  "<printer> is back" when it returns. A printer listed but unreachable counts as a failed check too.
  Never while printing, and never for Print to PDF.
- Troubleshooting: how to tell a bad USB port from a printer problem (`error -71`,
  `libusb_bulk_transfer: Input/Output Error` in the ipp-usb log).

## 0.2.2 — 2026-09-23

- **Open with LinPrinter**: right-click a document in the file manager and choose Open With →
  LinPrinter. `run.sh FILE…` opens the document on the Print page; the menu entry (installer and
  package) now has `Exec=… %F` and `MimeType=` for PDF, PNG, JPEG, TIFF, BMP, GIF and text.
- Tests for the command line and the menu entry's file types.

## 0.2.1 — 2026-09-22

- Installer package: `dist/linprinter_0.2.1_all.deb` (+ `SHA256SUMS`), built by `tools/build-deb.sh`
  (/opt/linprinter, `linprinter` command, menu entry for all users, depends on the app.json packages).
- `install.sh --package` installs it system-wide (checksum-verified, offline pool first, removes the
  duplicate per-user entry); `--uninstall` also removes the package.
- Tested offline in a clean ubuntu:24.04 container (no network): package and both installer modes.
- Screenshots: 17, from a sandbox home (report, borderless photo, text, Print to PDF, queue, recent,
  printers, setup and test, test pages, settings, about, paper out); README rewritten with a screenshot tour.
- UI polish: Profile row inside Print Options; paths shown with ~ (Printers, PDF summary and result);
  Recent columns fit the window; progress bar cleared when a new document is opened; Print to PDF
  capabilities read "1" copy and "any" paper type.
- Tests: packaging (install.sh and app.json lists equal; package checksum and contents) — 35 tests.

## 0.2.0 — 2026-09-22

First working release (roadmap 0.1 + 0.2 in docs/CONCEPT.md).

- Print page: Detect Printer (Find, printer list, power mark, plain status), Document (Open…, drag and drop),
  Print Options from the printer's own capabilities (copies, colour, quality, pages, paper size and type,
  borderless, fit), summary line, Print / Cancel / Preview, progress.
- Preview: pages as they will print (paper, margins shaded, grey for B&W, auto-rotate), zoom, 1/2-row thumbnails.
- Queue: jobs with state, pages done, method; Cancel job; auto-refresh.
- Recent: printed documents; open folder, print again, clear by age.
- Printers Found: methods, USB facts, capabilities, firmware, ink gauges, Identify.
- Setup and test: the printer's defaults (Use in LinPrinter), quality and line test pages, Look first,
  links to the printer's own settings / maintenance and ink pages (localhost, via ipp-usb).
- Print to PDF (default ~/Documents/prints).
- Direct IPP client (Validate-Job, Print-Job, Get-Jobs, Cancel-Job, Identify-Printer), CUPS fallback,
  no fallback when the user must act.
- Features: Ink alerts (on), Print profiles (off).
- Built-in TR150 test printer (--test-printer); ipptool passes against it.
- Settings (theme, PDF folder, low-ink level, network Not Supported, features, diagnostics), About.
- Installer with offline pool support, menu entry and icon; noncommercial licence.

## 0.0.1 — 2026-09-22

- Technical concept (docs/CONCEPT.md) and README.
