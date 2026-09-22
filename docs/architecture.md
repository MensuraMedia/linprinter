# LinPrinter architecture

```
src/
  main.py                 entry point: options, services, window (--test-printer, --list-printers, --page …)
  config/                 layout, themes, print vocabulary (config_print: sizes, types, groups, USB-only flag)
  ui/                     app window, sidebar (NAV_ITEMS), content area (PAGES), components (segmented, preview)
  pages/                  one BasePage per screen: print, preview, queue, recent, printers, settings, about
  modules/
    app_context.py        shared services + tiny event hub (ctx.on / ctx.emit)
    manager_print.py      PrintManager: discovery, status, tickets, preview, print_async, jobs, setup & tests
    manager_render.py     Ghostscript/Pillow: normalise to PDF, page count/selection, PWG raster, PDF, previews
    manager_testpage.py   built-in quality and line test pages
    manager_status.py     printer-state-reasons → plain words; ink warnings; "user must act"
    manager_documents.py  Recent list
    manager_settings.py   settings.json (XDG), session overrides
  backends/
    ipp.py                IPP/1.1 binary codec + HTTP/1.1 client (RFC 8010/8011)
    backend_ipp.py        P1: ipp-usb on 127.0.0.1 (and the test printer, T)
    backend_cups.py       P2: local USB CUPS queues via lp / lpstat / cancel
    backend_pdf.py        Print to PDF
    backend_base.py       PrinterDevice, Method, PrinterCapabilities (+ defaults, alert, local links), PrintError
    usb_probe.py          /sys USB facts (printer class, driver, speed) — no serials
    test_printer.py       IPP server replaying the real TR150 attributes
  features/               FeatureRegistry + feature_ink_alerts, feature_profiles (switchable, removable)
  utils/                  logging (redacted), paths, icons (Phosphor), display, imaging
```

## Flow of a print

```
PrintPage.on_print
  → features.before_print (warnings → confirm)
  → PrintManager.print_async(printer, ticket, pages)            [worker thread]
      for method in printer.methods (P1, P2 | PDF | T):
        status → user must act? raise, no fallback
        backend.submit:  P1/T  render_pwg → Validate-Job → Print-Job (streamed)
                         P2    render_pdf → lp -o …
                         PDF   render_pdf → ~/Documents/prints/<name>-<time>.pdf
        _follow(job) until completed / canceled / aborted
      add_recent
  → PrintPage.on_done → features.after_print → "jobs-changed", "documents-changed"
```

## Discovery

`PrintManager.discover()` merges:
1. P1: IPP printers at `ipp://127.0.0.1:60000–60015/ipp/print` (ipp-usb), capabilities from
   Get-Printer-Attributes;
2. P2: CUPS queues whose device URI is local (usb:, "(USB)" driverless, loopback), matched to P1 by model;
3. USB probe facts (class 7 printers, driver) or a hint when nothing answers;
4. Print to PDF, always last.

The chosen printer is remembered (`last_printer_info`), so the next start checks it first.

## Events (AppContext)

printers-changed, printer-selected, printer-status, ticket-changed, document-changed, open-document,
jobs-changed, documents-changed, settings-changed, features-changed, request-printer-refresh.
