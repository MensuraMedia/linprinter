# LinPrinter technical reference

## IPP (RFC 8010 / 8011, PWG 5100.14 IPP Everywhere)
- `backends/ipp.py` encodes and decodes the binary protocol: attribute groups, value tags, collections
  (begCollection / memberAttrName / endCollection), ranges, resolutions and dateTime. It posts over
  HTTP/1.1 with `Content-Type: application/ipp`, and streams documents with Content-Length.
- Operations used: Get-Printer-Attributes (with `media-col-database`), Validate-Job, Print-Job, Get-Jobs,
  Get-Job-Attributes, Cancel-Job, Identify-Printer.
- Job attributes: `copies`, `print-color-mode`, `print-quality` (3/4/5), `media-col` (`media-size` in
  hundredths of a millimetre, `media-type`, margins 0 for borderless), `print-scaling=none`.

## Rendering (Ghostscript)
- PWG raster for P1: `-sDEVICE=pwgraster -r600 -dcupsColorSpace=19|18 -dcupsBitsPerColor=8
  -dDEVICEWIDTHPOINTS/-dDEVICEHEIGHTPOINTS -dFIXEDMEDIA -dPDFFitPage -sPageList=…`. PDFFitPage also turns
  landscape pages to portrait, since the TR150 is portrait only.
- PDF for P2 and Print to PDF: pdfwrite, grey when monochrome.
- Previews: png16m / pnggray at 60 dpi, with the unprintable margins shaded.
- Images become PDF through Pillow, and text through DejaVu Sans Mono pages.

## Canon TR150 (from the device, read-only)
- Formats: pwg-raster, urf, jpeg. Colour, monochrome, auto. Draft, normal, high. 300 and 600 dpi.
  One-sided only. Copies 1–99. No page-ranges.
- 22 sizes (custom 55×89 to 215.9×676 mm), 15 media types (including com.canon.*). Borderless comes
  from media-col-database (824 entries, 88 borderless combinations).
- Markers: Color (tri-colour), Black. Identify: flash. Firmware 2.060.
- Operations: Print-Job, Validate-Job, Create-Job, Send-Document, Cancel-Job, Get-Job-Attributes,
  Get-Jobs, Get-Printer-Attributes, Close-Job, Identify-Printer. **No Set-Printer-Attributes**, so
  printer settings are changed on the printer's own page (`printer-more-info`,
  `printer-supply-info-uri` on localhost:60000 through ipp-usb).
- Defaults: letter, stationery, colour, normal, print-scaling auto.

## Setup and test
- `PrintManager.printer_defaults(printer)` maps `*-default` attributes to LinPrinter choices;
  `use_printer_defaults` stores them in settings.
- `manager_testpage.make_test_page(kind, …)` draws at 300 dpi for the ticket's paper and margins:
  - `quality`: CMYK+RGB blocks at 100/50/25 %, an 11-step grey ramp, 1/2/3 px lines for each ink, a
    gradient, 6–16 pt text, and a printable-edge frame;
  - `lines`: horizontal and vertical line fields for each ink, plus crosses.
- `print_test_page` prints it through the normal path at actual size on plain paper. It isn't added to
  Recent.
- Links to printer pages are kept only for `http(s)://localhost` / `127.0.0.1`.

## Status words
`manager_status.describe(state, reasons)` gives (level, message). Level is ok / warn / error, from the
reason suffix (-error / -warning / -report) and a list of reasons that stop printing. Unknown reasons
are shown in words. `user_must_act` blocks fallback for media-empty, media-jam, door-open, cover-open,
marker-supply-empty and input-tray-missing.

## USB link health and stray queues (0.2.8)
- `backends/usb_link.py` reads `journalctl -k --since -10min` and counts, per port, connection errors
  (`error -71`, `Cannot enable`, `not accepting address`, `can't set config`, descriptor read failures)
  and disconnects, plus the USB ids seen there. A port is failing at 2 errors or 3 disconnects. A
  printer on a failing port gets a note; a remembered printer that has dropped off the bus is listed,
  with no method, when its id or port is failing - instead of an empty list.
- ipp-usb answers HTTP 503 when it can't move data over USB. That is `IppError` / `PrintError` code
  **`link`**, which counts as "the user must act": no fallback, because a driverless CUPS queue goes
  through the same ipp-usb link (on 2026-10-01 the fallback spooled a job onto it, and the cut-off job
  left the printer hung).
- `backend_cups.sort_queues`: a permanent queue owns its name (`lp -d NAME` reaches it even while a
  driverless printer is announced as NAME), so `lpstat -v` is read first and its device URI decides.
  `implicitclass://NAME/` (cups-browsed) resolves to the printer announced as NAME. A queue on
  `serial:`, `parallel:` or `file:` is *misdirected*; a matching printer gets a note with the
  `lpadmin -x` command.
- A port that fails before its device delivers a descriptor has no USB id; when the remembered
  printer is missing, such a port is reported as "a USB device on port … keeps failing to connect".
- All USB advice leads with **another cable** (`usb_link.CABLE_ADVICE`): on 2026-10-02 two faulty
  cables were the cause of every TR150 failure. `tools/usb_linktest.py` measures a link: 200
  GET_DESCRIPTOR(device) control reads through usbfs (`USBDEVFS_CONTROL`), read-only, optionally
  against a known-good device on the same controller. See docs/USB-TROUBLESHOOTING.md.

## Test printer
`TestPrinter` is a ThreadingHTTPServer on 127.0.0.1:0 (HTTP/1.1). It serves
`resources/test-printer/tr150-attributes.json` (112 attributes with their tags; UUID zeroed, device-id
simplified). Print-Job saves the document in its spool and completes after `job_seconds`. `set_state()`
simulates paper-out and similar states. CUPS' `ipptool get-printer-attributes.test` passes against it.

## Packaging and installation
- `tools/build-deb.sh` builds `dist/linprinter_<version>_all.deb` (architecture all, xz). It contains:
  - `/opt/linprinter` (src, resources, VERSION, LICENSE, README, run.sh);
  - `/usr/bin/linprinter`, which runs `python3 /opt/linprinter/src/main.py`;
  - `/usr/share/applications/linprinter.desktop` with `StartupWMClass=linprinter`;
  - the hicolor 512 px icon, the copyright file (the licence) and the changelog.

  `Depends` is the `app.json` → `offline.apt` list. There are no maintainer scripts. `dist/SHA256SUMS`
  is written next to the package.
- `install.sh` has three modes:
  - default: per user, runs from the checkout;
  - `--package`: verifies the checksum, then `sudo dpkg -i`, and removes the per-user entry;
  - `--uninstall`: removes the per-user entry and icon, and the package if it's installed.

  Dependencies come from `../bin/offline-install` (the linux-peripherals pool) first, then apt.
  `LINPRINTER_ALLOW_ROOT=1` lets it run as root, for container tests only.
- Verified offline in `ubuntu:24.04 --network none`: the dependencies from the pool, then the package
  (`linprinter --version`, `--list-printers`), and both installer modes, including re-runs and uninstall.
