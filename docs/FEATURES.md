# LinPrinter features

| Area | What | Where |
|---|---|---|
| Shell | Header with status chip (Ready · Busy · Needs you · Can't reach) and menu; rail with Print, Activity, Printer, Settings; Alt+1…4, Ctrl+P, Ctrl+O, F5; compact layout below 960 px | ui/app_window.py, ui/sidebar.py |
| Print: printer | Remembered printer reached first, status every 5 s, quiet re-search; state in words with its fix (banner + actions); Change popover (printers, Print to PDF, search again) | pages/page_print.py |
| Print: document | Open… (Ctrl+O), drag and drop, Open With; PDF, images, text | page_print, manager_render.normalise |
| Print: options | Paper (size grouped, type, borderless with reason), Output (copies, colour, quality, pages all/range/current), More options (odd/even, fit, profiles) | page_print, config_print |
| Print: preview | Live beside the options; margins shaded; zoom to 16×; thumbnails; current page | page_print, ui/components/component_preview.py |
| Print: action bar | Summary; Print with the reason when disabled; printing progress and Cancel (asks); printed end moment with Show in Activity / Print again; saved PDF with Show in folder | page_print, lintheme ActionBar |
| Printing | Direct IPP → CUPS; Validate-Job; followed to the end; no fallback when the user must act or the USB link fails | manager_print, backend_ipp, backend_cups |
| Activity | Now printing (progress, Cancel print); History with result and settings used, Print again (same settings), Show file, Remove, Clear older than 30/90/365 days | pages/page_activity.py, manager_documents |
| Printer | Hero status; Ink and paper; Connection (port, route, kernel-log link errors, Test connection, Reconnect…); Look after the printer (test pages, Look first, printer's own page); own defaults; Details; stray-queue banner with the command | pages/page_printer.py |
| Troubleshooter | Six steps, cheapest first (cable first), live evidence from the kernel log and the link test | pages/page_printer.py |
| Settings | Printing (PDF folder, low ink %, start behaviour, features), Privacy and diagnostics, About | pages/page_settings.py |
| Theme | Graphite Night only (lin-dashboard-theme, vendored); WCAG 2.2 AA contrast for every pair | src/lintheme/ |
| Print to PDF | ~/Documents/prints (Settings), unique names | backend_pdf |
| Feature: Ink alerts | Warns before printing at or below the low-ink level (on) | features/feature_ink_alerts.py |
| Feature: Print profiles | Built-in and saved presets on the Print page (off) | features/feature_profiles.py |
| Test printer | --test-printer, tests, walkthrough | backends/test_printer.py |
| Installer script | Per-user install from the checkout; offline pool first; OK / FIXED / FAIL summary | install.sh |
| Installer package | System-wide .deb (/opt/linprinter, `linprinter`), checksum-verified; `install.sh --package` | tools/build-deb.sh, dist/ |
| Screenshots | 17 screenshots from a sandbox home with the test printer | tools/walkthrough.py, docs/screenshots/ |
