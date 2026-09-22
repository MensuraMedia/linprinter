# LinPrinter: technical concept

Status: **concept for review**, 2026-09-22. Nothing is built yet.
- **Target:** the connected **Canon TR150 series**, designed so that any
  modern printer works the same way.
- **Name:** LinPrinter (decided).
- **Repository:** https://github.com/MensuraMedia/linprinter; local folder
  `~/projects/linprinter`.

---

## 1. Short answer

**Yes.** The same interface, the same processes and the same principles carry
over directly. Printing is simpler than scanning in the parts that were
hardest for LinScanner:
- there is no image acquisition;
- there are no feeder quirks to work around;
- there is no auto-detection of paper edges.

The same work (a universal backend, capability-driven options, status,
switchable feature modules, privacy, offline install, tests and docs) comes to
roughly **half of LinScanner's effort**.

About **60 % of LinScanner's code can be reused as it is**:
- the framework (sidebar, pages, themes, Phosphor icons);
- settings, logging with redaction, the feature registry, Recent, Preview
  thumbnails and zoom, and Quick Edit layers (text and signatures, reused
  here for stamps and watermarks);
- the installer pattern and the test harness.

Printing also has its own, smaller challenges:
- capabilities differ a lot between printers;
- options the TR150 lacks (duplex, page ranges, landscape) have to be done in
  the app;
- supply and error states need clear, plain-language messages.

---

## 2. The connected printer: what it actually offers

Everything below was queried from the printer itself on 2026-09-22, read-only
(`ipptool get-printer-attributes` against the ipp-usb endpoint). No guesses.
The UUID and device IDs are left out on purpose.

| Item | TR150 value | What it means for the app |
|---|---|---|
| Model / firmware | Canon TR150 series, firmware 2.060 | Shown in "Printers Found" |
| USB | `04a9:18a4`, IPP-over-USB (class 7/1/4) | Reached with no driver (IPP Everywhere), like LinScanner's B2 method |
| Endpoint | `ipp-usb` on **127.0.0.1:60000** (`interface = loopback`), `ipp://localhost:60000/ipp/print` | Local only; never on the network |
| CUPS | a temporary driverless queue, `Canon_TR150_series_USB` (IPP Everywhere); no permanent queue installed | The app can use it through CUPS, or talk IPP directly |
| Document formats | `image/pwg-raster`, `image/urf` (AirPrint), `image/jpeg`, `application/octet-stream` | PDFs are rendered to PWG raster (cups-filters does this) |
| Colour | `color`, `monochrome`, `auto`, `auto-monochrome` | Color / Black & White (/ Auto) |
| Quality | `draft`, `normal`, `high`; resolution 300 or 600 dpi | Draft / Normal / High, like LinScanner's Low / Medium / High |
| Sides | `one-sided` only | No automatic duplex: offer a **Manual two-sided** module (§6) |
| Copies | 1–99 | Copies spinner |
| Page ranges | **not supported** (`page-ranges-supported = false`) | The app selects pages itself before sending |
| Orientation | `portrait` only | The app rotates landscape pages itself |
| Scaling | `none`, `fill`, `fit`, `auto-fit`, `auto` | Actual size / Fit / Fill |
| Media sizes (22) | A4, A5, B5, Letter, Legal; photo L (3.5×5), 4×6, 5×7, 7×10, 8×10, square 5×5 and 89×89 mm; business card 55×91 mm; envelopes #10, DL, You4/6, Chou3/4; Hagaki; **custom 55×89 mm to 215.9×676 mm** | A grouped "Paper Size" list (Documents / Photos / Envelopes / Cards / Custom), like LinScanner's Document Size |
| Media types (15) | Plain (stationery), Photographic, Envelope, Auto, and Canon types: glossy, matte, hi-res, inkjet, greeting card, Hagaki (and glossy) | A "Paper Type" list with friendly names |
| Margins | 0 among the supported values (borderless) | A **Borderless** switch, shown only for sizes and types that allow it |
| Paper source | `auto`, `main` (rear sheet feeder); output face-up, last page first | Page-order handling for stacks and manual duplex |
| Ink | markers "Color" (tri-colour cartridge) and "Black", ink-cartridge type; levels 60 % and 80 % | Ink gauges with the cartridges' own colours, and low-ink warnings |
| Status | `printer-state`, `printer-state-reasons`, `printer-alert` | The power / status icon and plain messages (§7) |
| Operations | Print-Job, Validate-Job, Create-Job, Send-Document, Cancel-Job, Get-Jobs, Get-Job-Attributes, **Identify-Printer** (`flash`) | Validate options before sending; a job queue with Cancel; an "Identify" button that flashes the printer |
| Web pages | printer info and ink pages on 127.0.0.1:60000 (via ipp-usb) | An optional "Open printer's page" link |
| Kinds | document, envelope, photo, postcard | Profiles (§6) |

Software on this machine: CUPS 2.4.7, cups-filters 2.0.0, cups-ipp-utils
2.4.7 (`ipptool`, `ippfind`, `ippeveprinter`) and ipp-usb 0.9.24. All of it is
already in the repo's offline pool, because the TR150 installer depends on it.

---

## 3. Principles carried over from LinScanner

| LinScanner principle | In LinPrinter |
|---|---|
| **Universal through standards.** SANE covers 80+ drivers, eSCL covers driverless devices | **IPP Everywhere / AirPrint (driverless)** through CUPS and ipp-usb covers most printers made since about 2015. Older printers use CUPS drivers (Gutenprint, HPLIP, vendor PPDs), found automatically |
| **Capability-driven UI.** Scan Type comes from the device's sources | Every option comes from `*-supported` attributes. Unsupported options are hidden, or provided by the app (duplex, page ranges, rotation) |
| **Connection engine with ranked fallback.** No retry when the user must act | The same engine for printers (§4). Out of paper, jam, cover open or ink out never fall through to another method |
| **Remembered device and power status** | The same: the green or red `power` icon, with "Printer may be off. Check power settings." |
| **USB only, no network, no telemetry** | The same. ipp-usb stays on loopback, the app doesn't browse the network, and jobs never leave the computer (§9) |
| **Switchable, removable feature modules** | The same registry: `src/features/feature_*.py` (§6) |
| **Offline install, tests, docs, changelog, design doc before each build** | The same process; `ippeveprinter` plays the part of SANE's test scanner (§10) |
| **The framework, Default Blue theme, Phosphor icons, 10 pt buttons, half-width fields** | Identical. Shared code (§11) |

---

## 4. Architecture

```
┌ UI (GTK 3, gtk-python-dashboard-starter) ───────────────────────────────────┐
│ Print · Preview · Queue · Recent · Printers Found · Settings · About         │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ pages talk only to managers
┌ managers ────┴───────────────────────────────────────────────────────────────┐
│ manager_print   options → job ticket, submit, cancel                         │
│ manager_render  any input → PDF → page selection, n-up, rotation, overlays   │
│ manager_status  polls printer and jobs → plain-language states               │
│ manager_connection  printers grouped with ranked methods (as in LinScanner)  │
│ feature registry    manual duplex, n-up, watermark, profiles, copy, ...      │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ backends implement one interface: list, capabilities, submit, jobs, status
┌ backends ────┴───────────────────────────────────────────────────────────────┐
│ P1 CUPS driverless queue (IPP Everywhere over ipp-usb)   lp / lpstat / cancel │
│ P2 LinScanner-style own IPP client → 127.0.0.1:600xx     stdlib HTTP + IPP    │
│ P3 CUPS queue with a driver (Gutenprint, HPLIP, vendor)  lp -o …              │
│ T  virtual printer: ippeveprinter (tests, --test-printer)                      │
│ (network printers: disabled, as in LinScanner)                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Method ranking and fallback**, mirroring LinScanner's A1 → A3 → B2 → D1:

1. **P1 CUPS driverless** is preferred. CUPS converts the PDF (cups-filters
   `pdftopdf` → `pdftoraster`), spools it, and retries if the printer is
   briefly busy.
2. **P2 own IPP client** is used when CUPS isn't running or the queue is
   broken. It sends PWG raster made locally with Ghostscript (`-sDEVICE=pwgraster`),
   using Create-Job and Send-Document. Like LinScanner's eSCL client, it works
   even with CUPS stopped.
3. **P3 a CUPS queue with a driver**, for printers that don't speak driverless
   IPP.
- **No fallthrough** on `media-empty`, `media-jam`, `door-open`,
  `marker-supply-empty` or `cover-open`: the user must act. On `busy`,
  `timeout`, connection refused or a missing queue, the next method is tried.

**Discovery** is local only:
- `lpstat -e` finds driverless and permanent CUPS destinations.
- Probing 127.0.0.1:60000–60015 finds ipp-usb endpoints, as LinScanner does.
- The USB probe (sysfs; class 7 = printer) gives the "why it's a printer" and
  permission facts.
- Several entries for one physical printer (a CUPS queue plus a raw ipp-usb
  endpoint) are grouped by USB bus/device or by model, as in LinScanner.

---

## 5. Pages and controls

**Print** (the main page, laid out like LinScanner's Scan page):
- **Detect Printer:** **[Find]** [printer name ▾] (⏻) [Printers]. The icon is
  green when ready, red with a message otherwise; the fields are half width.
- **Document:** [Open…] or drag and drop (PDF, images, plain text), or the
  most recent LinScanner scan.
- **Print Options** (segmented buttons of equal width, as in Scan Options):

| Row | Choices (TR150) | Mapping |
|---|---|---|
| Copies | 1–99 | `copies` |
| Color | Color · Black & White | `print-color-mode` color / monochrome |
| Quality | Draft · Normal · High | `print-quality` 3 / 4 / 5 |
| Pages | All · Range… · Odd · Even · Current | done in the app (the printer has no `page-ranges`) |
| Paper Size | grouped list (half width) | `media` / `media-col.media-size` |
| Paper Type | Plain · Photo Glossy · Photo Matte · Hi-Res · Envelope · Card · Auto | `media-col.media-type` |
| Borderless | Off · On (photo sizes and types only) | `media-col` margins = 0 |
| Fit | Actual size · Fit · Fill | `print-scaling` none / fit / fill |
| Two-sided | Off · Manual (module) | done in the app |

- **Summary line:** "Will print: 3 copies · Color · High · A4 Photo Glossy ·
  borderless · pages 1–4", validated with **Validate-Job** before printing.
- **[Print]**, **[Cancel]**, a progress bar, and the status line (printing
  only).

**Preview.** Pages exactly as they will print: paper outline, margins or
borderless bleed, n-up layout, watermark. It reuses LinScanner's Preview:
display copies, zoom, 1 or 2 thumbnail rows, and the icon toolbar (rotate,
move, delete, add page, add text or stamp, signature, undo).

**Queue.** Jobs that are waiting, printing and done (Get-Jobs): name, pages,
state, time, and [Cancel]. Completed jobs are kept only as local history.

**Printers Found** (the counterpart of "Scan Devices Found"):
- identity, USB connection and the ranked methods;
- capabilities: sizes, types, colour, quality;
- **ink gauges** drawn in the cartridge colours (#39D2E7 / #D945DD / #DFD31D
  and black);
- state and reasons, firmware;
- **[Identify]** (the printer flashes);
- [Open printer's page] (local ipp-usb web page).

**Recent, Settings, About:** as in LinScanner. Settings adds the default
printer, default profile and low-ink warning level.

---

## 6. Feature modules (switchable, removable)

| Module | Default | What it does | Why the TR150 needs it |
|---|---|---|---|
| **Manual two-sided** | on | Prints the odd pages, shows "Put the stack back, printed side …", then prints the even pages in the right order | One-sided only; output is face-up, last page first, so the order is worked out for this tray |
| **Page selection** | on | Range, odd, even or current page, done by picking PDF pages | `page-ranges-supported = false` |
| **Auto-rotate / landscape** | on | Rotates landscape pages to portrait, fitted to the paper | Portrait only |
| **N-up / booklet** | off | 2, 4 or 6 pages per sheet; booklet folding order (together with manual two-sided) | Not offered by the printer |
| **Watermark / stamp** | off | "DRAFT", "COPY", "PAID"… or a signature, reusing LinScanner's Quick Edit layers | Common in PDF tools |
| **Ink saver** | off | Draft quality plus grey text, or lighter images | Cheaper cartridges |
| **Photo layouts** | off | Borderless 4×6 / 5×7, 2-up or 4-up photos, contact sheets | Photo sizes and types are supported |
| **Envelopes and cards** | off | Address layout for #10 / DL, business-card sheets | Envelope and card sizes are supported |
| **Copy** (LinScanner + LinPrinter) | off | Scan with the ES-400 II, then print on the TR150 in one click (a photocopier) | Both devices are connected |
| **Profiles** | off | "Everyday B&W draft", "Photo borderless glossy", "Envelope #10"… | Like LinScanner's scan profiles |
| **Ink alerts** | on | A warning before printing when a cartridge is under the threshold | `marker-levels` |
| **Print history** | on | The Recent page for printed documents | Like LinScanner's Recent |

---

## 7. Status and plain-language messages

`manager_status` polls **Get-Printer-Attributes** (state, reasons, marker
levels) every 5 s, or every 1 s while printing, and **Get-Jobs** while jobs
are active. The IPP reasons map to messages, as LinScanner's SANE status codes
do:

| IPP reason | Shown | Icon / action |
|---|---|---|
| no answer | "Printer may be off. Check power settings." | red power icon; no fallthrough |
| `media-empty` | "Load paper in the rear tray." | red; job held until the paper is loaded |
| `media-jam` | "Paper jam. Remove the jammed sheet." | red; no fallthrough |
| `marker-supply-low` / `-empty` | "Color / Black ink is low (20 %) / empty." | amber / red gauge |
| `door-open` / `cover-open` | "Close the printer's cover." | red |
| `other` / `printer-alert` | "The printer reports a problem: …" | red, details in the log |
| idle / processing | "Ready" / "Printing page 3 of 8" | green |

---

## 8. Job pipeline

```
input (PDF / image / text / LinScanner scan)
  → normalise to PDF      images: Pillow · text: an embedded monospace font · PDF: unchanged
  → page selection        range / odd / even / manual-duplex pass
  → transforms            rotate to portrait · n-up · watermark / signature layers · ink saver
  → Validate-Job          options checked against the printer (friendly error if not)
  → submit
      P1: lp -d <queue> -o media=… -o print-quality=… -o print-color-mode=… -o copies=… file.pdf
      P2: Ghostscript → PWG raster → IPP Create-Job + Send-Document (127.0.0.1:600xx)
  → monitor job           Get-Job-Attributes → progress, done, or a plain error
  → Recent / history      local only
```

Every step is a pure function on files in the session's temporary folder,
and every step is testable, as with LinScanner's export pipeline.

---

## 9. Privacy and security (the same commitment as LinScanner)

- **USB only.** ipp-usb is on loopback (checked: `interface = loopback`). The
  app doesn't browse the network (no mDNS or WS-Discovery), and network
  printers are "Not Supported", as in LinScanner.
- **Nothing leaves the computer.** There are no accounts, cloud or telemetry.
  Documents go only down the USB cable.
- **CUPS keeps job history.** CUPS may keep job details in `/var/spool/cups`.
  The app says so, and links to "Clear history" (`cancel -a -x`) for the
  user's own jobs.
- **Rights.** It runs as the normal user; printing needs no sudo. Only the
  installer asks, and only if packages are missing.
- **Logs** are redacted in the same way: serials and UUIDs become "…" and the
  home folder becomes "~". Document names are logged; document contents
  never are.

---

## 10. Compatibility and testing

**Compatibility (universal):**
- **Driverless IPP over USB** (ipp-usb) covers most inkjet and laser
  printers since about 2015: Canon, Epson, HP, Brother, Samsung, Xerox.
- **CUPS drivers:** Gutenprint (hundreds of models), HPLIP, splix, foo2zjs
  and vendor drivers cover older printers.
- The UI shows only what each printer reports, so no model is hard-coded.
- `bin/device-finder` already recognises printers (USB class 7).

**Testing without paper:**
- **`ippeveprinter`** (cups-ipp-utils, already installed) runs a virtual IPP
  Everywhere printer. It can store jobs as files and emulate chosen sizes,
  types and colour modes. It is the printing equivalent of SANE's `test`
  backend, for unit, integration and UI tests and `--test-printer`.
- Jobs are checked by their content: the page count, size and colour of the
  PWG raster or PDF it receives.
- Status mapping is tested with ippeveprinter's state and reason control, and
  with recorded attribute fixtures (the TR150 output from §2, with its IDs
  left out).
- On the real TR150: one page of each option combination, then ink,
  paper-out and jam handling, with the user.

---

## 11. Sharing code with LinScanner

| Option | Pros | Cons |
|---|---|---|
| **A. Separate app, shared package** (`linperipherals-common`: framework, theme, icons, logging, settings, feature registry, Recent, Preview, Quick Edit layers), used by both repositories | Clean, and each app stays small; fixes reach both | One more small repository and package |
| B. One combined app ("LinScanner" with Scan and Print sections) | One window; Copy is natural | A bigger app, more coupling, and LinScanner's focus blurs |
| C. Copy the code | Quickest start | Two copies drift apart |

**Recommended: A.**
- LinPrinter has its own repository (`MensuraMedia/linprinter`, decided). It
  can be included in linux-peripherals as a submodule, as LinScanner is.
- Move the shared parts into `linperipherals-common` once LinPrinter needs
  them.
- The **Copy** module then uses both apps' managers.

---

## 12. Dependencies (all already in the offline pool)

- cups, cups-filters, cups-ipp-utils, ipp-usb, ghostscript;
- python3-gi, gir1.2-gtk-3.0, python3-pil, librsvg2-common;
- the Phosphor icons and fonts shared with LinScanner.

No new packages are expected. `bin/test-offline linprinter` would prove it.

---

## 13. Roadmap (each step: design doc first, tests, docs, commit)

| Version | Scope |
|---|---|
| 0.1 | Print page: detect, power status, open a PDF or image; copies, colour, quality, size, type; Print and Cancel; CUPS driverless backend; ippeveprinter tests |
| 0.2 | Preview (shared); page selection; auto-rotate; Validate-Job; Queue page; Printers Found with ink gauges and Identify; plain status messages |
| 0.3 | Own IPP client (P2) and fallback; borderless; manual two-sided; profiles; Recent and print history |
| 0.4 | N-up and booklet; watermark and signature (Quick Edit layers); photo layouts; envelopes and cards; ink alerts |
| 0.5 | Copy (LinScanner → LinPrinter); shared `linperipherals-common` package |

Effort: about half of LinScanner's.
- The backend and status work are simpler.
- Preview and the framework are reused.
- The main new work is the render pipeline (n-up, manual duplex) and the
  IPP client.

---

## 14. Limits and risks (TR150)

- **No automatic duplex.** Manual two-sided needs the user to turn the stack,
  so the dialog must be very clear.
- **Unavailable functions.** Maintenance (nozzle check, head cleaning, head
  alignment) is not available over IPP on this model; it stays on the
  printer's own menu. There are no quiet mode or tray settings.
- **Ink levels are coarse** (10 % steps on most Canon models), and the colour
  cartridge reports one level for all three colours.
- **Borderless** works only for some sizes and types, so the UI must follow
  the printer's margin lists, not assume.
- **Auto power-off.** When the printer powers itself down, the red power icon
  and message cover it. Unlike scanners, printers usually wake up when a job
  arrives, so a job can also be queued and printed when the printer comes on.
- **Temporary queues.** The driverless queue name comes from CUPS, so the app
  stores the printer by USB ID and model, not by queue name (as LinScanner
  remembers scanners).

---

## 15. Decisions for you

Decided (2026-09-22):
- **Name:** LinPrinter.
- **Repository:** `MensuraMedia/linprinter` (public), local folder
  `~/projects/linprinter`.

Still open:
1. **Structure:** a separate app with a shared package (recommended), or
   Print inside LinScanner?
2. **First scope:** start with roadmap 0.1 + 0.2, or add a module early (for
   example Copy or Manual two-sided)?
3. **Licence:** the same LinScanner Community License (Noncommercial)?
4. **linux-peripherals:** include LinPrinter there as a submodule (as
   LinScanner is), so it installs offline from the pool?
