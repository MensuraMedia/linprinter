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

## 2026-09-24 — Licence: CC BY-NC 4.0, with the full legal code
The user replaced the bespoke "LinPrinter Community License (Noncommercial) 1.0" with Creative Commons
Attribution-NonCommercial 4.0 International. `LICENSE` carries a plain-language summary (the user's
wording) followed by the **full official legal code**: Creative Commons states the deed summary is not
a substitute for the licence, so shipping the summary alone would have been weak. `tests/test_licence.py`
guards it. The change is **not retroactive** — copies released earlier keep the terms they came with.

## 2026-09-24 — Reconnect asks pkexec; the installer adds no udev rule
Re-attaching a USB device is machine-wide and needs root. LinPrinter never holds privileges: it asks
pkexec, which shows the desktop's own dialog and runs a narrow helper that verifies the port still
holds that printer (USB id) and that it is a printer. A udev rule would remove the password, but
granting a user permanent control of a device's USB attachment is the machine administrator's
decision, not an app installer's — so the installer does not add one.

## 2026-09-24 — A truncated IPP reply must be an error, never a fragment
Bounds-checking alone was not enough: a reply that happened to stop at an attribute boundary parsed
"successfully" and returned a partial attribute set, so a half-read printer looked like a printer with
no paper sizes. `decode_message` now requires the end-of-attributes tag. Attributes are still requested
in one go (Canon answers a named `media-col-database` more fully than a plain "all"), with a fallback
to the essentials so a dropped extra costs only the borderless combinations.
