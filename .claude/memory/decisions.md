# Decisions

## 2026-09-22 — Independent app, built like LinScanner
Separate repo (MensuraMedia/linprinter), same framework, licence (Noncommercial 1.0), feature registry,
USB-only privacy. Installer and app.json in the repo; offline install via the linux-peripherals pool (submodule).

## 2026-09-22 — Direct IPP first, CUPS second
P1 talks IPP Everywhere to ipp-usb on 127.0.0.1 (Validate-Job, Print-Job with PWG raster from Ghostscript).
Why: exact control of every job attribute (media-col, margins, quality), real job states and ink levels, and it
works without a CUPS queue. P2 (CUPS `lp`) covers printers that need a driver. No fallback when the printer
needs the user (media-empty, jam, cover/door open, ink empty) — another method would fail the same way.

## 2026-09-22 — LinPrinter selects pages and fits them itself
The TR150 has no page-ranges and prints portrait only; Ghostscript does page selection, fit-to-page and
auto-rotation, and jobs are sent with print-scaling=none.

## 2026-09-22 — Printer setup through what the printer allows
The TR150 has no Set-Printer-Attributes. LinPrinter reads its defaults (and can adopt them), prints its own
test pages, runs Identify, shows ink and alerts, and opens the printer's own settings / maintenance and ink
pages — only when they are on localhost (ipp-usb over USB), never network addresses.

## 2026-09-22 — Test printer instead of ippeveprinter
ippeveprinter needs IPv6, which is disabled on the development machine. A Python IPP server replays the real
TR150 attributes (identifiers removed); CUPS' ipptool passes against it. Tests never print on hardware.

## 2026-09-22 — Print to PDF default folder
~/Documents/prints (user's choice), changeable in Settings.

## 2026-09-22 — Installer package committed in the repository
`dist/linprinter_<version>_all.deb` + `SHA256SUMS` are committed (about 100 KB), so the repository alone
carries both the installer script and the installer package (the user's request). The package has no
maintainer scripts; Depends = app.json. `install.sh --package` verifies the checksum before installing.
