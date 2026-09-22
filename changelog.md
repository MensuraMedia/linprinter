# Changelog

All notable changes to LinPrinter. Semantic versioning; newest first.

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
