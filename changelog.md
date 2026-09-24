# Changelog

All notable changes to LinPrinter. Semantic versioning; newest first.

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
