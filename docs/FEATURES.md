# LinPrinter features

| Area | What | Where |
|---|---|---|
| Detect Printer | Find, printer list, power mark (spinner / ok / warn / error), plain message, remembered printer, status every 5 s | pages/page_print.py |
| Document | Open…, drag and drop; PDF, images, text | page_print, manager_render.normalise |
| Print Options | Copies, Color, Quality, Pages (All / Range / Odd / Even / Current), Paper Size (grouped), Paper Type, Borderless, Fit; summary line | page_print, config_print |
| Printing | Direct IPP → CUPS; Validate-Job; job followed to the end; Cancel; no fallback when the user must act | manager_print, backend_ipp, backend_cups |
| Preview | Exact pages, margins shaded, grey for B&W, rotated; zoom; 1/2-row thumbnails; sets Current page | pages/page_preview.py |
| Queue | Jobs table, Cancel job, Refresh, auto-refresh | pages/page_queue.py |
| Recent | Printed documents; folder, print again, delete, clear by age | pages/page_recent.py, manager_documents |
| Printers Found | Methods, USB facts, capabilities, firmware, ink gauges, Identify, check again | pages/page_printers.py |
| Setup and test | Printer's defaults + Use in LinPrinter; quality and line test pages; Look first; printer settings / maintenance and ink pages (localhost) | page_printers, manager_testpage, manager_print |
| Print to PDF | ~/Documents/prints (Settings), unique names | backend_pdf |
| Settings | Theme, PDF folder, low-ink %, network Not Supported, features, diagnostics | pages/page_settings.py |
| About | What it is, compatibility, privacy, licence, files, shortcuts, versions, credits | pages/page_about.py |
| Feature: Ink alerts | Warns before printing at or below the low-ink level (on) | features/feature_ink_alerts.py |
| Feature: Print profiles | Built-in and saved presets on the Print page (off) | features/feature_profiles.py |
| Test printer | --test-printer, tests, walkthrough | backends/test_printer.py |
