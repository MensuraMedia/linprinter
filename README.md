# LinPrinter

A document printer for Linux. Print PDFs, images and text on your USB
printer, and see beforehand exactly what will print. You can also follow
jobs, check ink, test and set up the printer, or print to PDF. It's a sibling
of [LinScanner](https://github.com/MensuraMedia/linscanner), built the same
way: the same interface, the same switchable feature modules, and the same
USB-only privacy.

![LinPrinter: the Print page](docs/screenshots/01-print.png)

| | |
|---|---|
| Version | 0.2.5 (see [changelog.md](changelog.md)) |
| Verified printer | Canon TR150 series (USB, driverless) |
| Platform | Linux desktop (Linux Mint 22 / Ubuntu 24.04 and other Debian-based systems), GTK 3, Python 3.10+ |
| Connection | **USB cable only.** Wi-Fi and network printing are not supported at this time. |
| Install | `bash install.sh` (runs from this folder), or the installer package [`dist/linprinter_0.2.5_all.deb`](dist/) (system-wide). Both work offline with the linux-peripherals package pool. |
| Licence | [CC BY-NC 4.0](LICENSE): free to use, share and adapt with credit; commercial use needs our written permission |

## Contents

1. [Features](#1-features)
2. [A tour in screenshots](#2-a-tour-in-screenshots)
3. [Compatibility](#3-compatibility)
4. [Installation](#4-installation)
5. [Using LinPrinter](#5-using-linprinter)
6. [Setting up and testing your printer](#6-setting-up-and-testing-your-printer)
7. [Settings, files and command line](#7-settings-files-and-command-line)
8. [Troubleshooting](#8-troubleshooting)
9. [Safety, security and privacy](#9-safety-security-and-privacy)
10. [Known limits and roadmap](#10-known-limits-and-roadmap)
11. [Development](#11-development)
12. [Credits](#12-credits)
13. [License](#13-license)

## 1. Features

| Area | What you get |
|---|---|
| **Detect Printer** | **Find**, the printer list, and a power mark. If the printer stops answering (asleep, switched off and on, or a bad USB port), LinPrinter searches again by itself every 20 seconds and says "<printer> is back" - no need to press Find: green when the printer is ready, amber when it needs attention, red when it's off or stopped. The message under it is plain, such as "Printer may be off. Check power settings." or "Load paper in the rear tray." LinPrinter remembers the printer, so the next start reaches it straight away. |
| **Documents** | PDF, PNG, JPEG, TIFF (multi-page), BMP, GIF and plain text. Open one with **Open…**, drop it on the Print page, or **right-click it in your file manager → Open With → LinPrinter**. |
| **Print Options** | Copies · Color or Black & White · Draft / Normal / High · Pages (All, a range such as `1-3, 5`, Odd, Even, Current) · Paper Size (grouped: documents, photos, envelopes, cards) · Paper Type (plain, photo, glossy, matte, envelopes, Hagaki …) · Borderless · Fit to page or Actual size. **Only the options your printer really has are offered.** A line under the options says exactly what will print. |
| **Preview** | The pages exactly as they will print: your paper, the printer's margins shaded, colour or grey, and pages turned to suit the paper. It zooms from a quarter size up to **16×** (Ctrl + wheel, or the buttons), with page navigation and 1- or 2-row thumbnails. Previews are rendered at 140 dpi, so zooming in shows real detail rather than a blur. |
| **Queue** | Waiting, printing and finished jobs, with the pages done, the time sent and how each job was sent. **Cancel job** stops a waiting or printing one. |
| **Recent** | Documents you've printed, newest first. The folder icon opens the folder; the document icon prints it again. Clear all entries, or those older than 5 / 10 / 20 / 30 days. |
| **Reconnect** | When a printer is plugged in but nothing sees it (the kernel left it unconfigured), **Reconnect** re-attaches that one printer. It appears next to **Find** when the mark is red, and on the Printers page. See [section 6](#6-setting-up-and-testing-your-printer). |
| **Printers Found** | Every printer and how LinPrinter reaches it, best way first. Also USB details, capabilities, firmware, **ink levels** drawn in the cartridges' own colours, and **Identify** (the printer flashes). |
| **Setup and test** | The printer's own **defaults** (and **Use in LinPrinter**); a **quality test page** and a **line / alignment page**; and the printer's own **settings / maintenance** and **ink** pages (cleaning, nozzle check, alignment, quiet mode …). See [section 6](#6-setting-up-and-testing-your-printer). |
| **Print to PDF** | Saves to `~/Documents/prints` (change it in Settings), with the same paper sizes and preview. No printer needed. |
| **Feature modules** | **Ink alerts** (on) warns before printing when a cartridge is low. **Print profiles** (off) adds one-click presets (Everyday, Draft, B&W document, Best quality, Photo 4×6 borderless, Envelope #10) plus your own. You can switch off or delete either one in Settings → Features. |
| **Reliable printing** | LinPrinter talks to the printer directly (IPP Everywhere over USB, through ipp-usb) and falls back to the CUPS queue. It checks each job with the printer first. It never retries another way when *you* need to act (paper out, jam, cover open, ink empty); it tells you what to do instead. |
| **Comfort** | Themes, a resizable window that snaps to screen halves and quarters, and the app icon in the panel and Alt+Tab. |

## 2. A tour in screenshots

The screenshots are made by `tools/walkthrough.py` with the built-in test
printer, which answers exactly like a Canon TR150. They are regenerated for
every release.

### Print and preview

| Print a report | Preview (1 row) | Preview (2 rows) |
|---|---|---|
| ![Print page](docs/screenshots/01-print.png) | ![Preview](docs/screenshots/02-preview.png) | ![Preview, two rows](docs/screenshots/02b-preview-two-rows.png) |

| Printing… | Printed | A photo, borderless 4 × 6 in | Photo preview |
|---|---|---|---|
| ![Printing](docs/screenshots/03-printing.png) | ![Printed](docs/screenshots/03b-printed.png) | ![Borderless photo](docs/screenshots/04-photo-borderless.png) | ![Photo preview](docs/screenshots/04b-photo-preview.png) |

### Jobs, PDF and history

| Queue | Print to PDF | Recent |
|---|---|---|
| ![Queue](docs/screenshots/05-queue.png) | ![Print to PDF](docs/screenshots/06-print-to-pdf.png) | ![Recent](docs/screenshots/09-recent.png) |

### Printers, setup and test

| Printers Found | Setup and test |
|---|---|
| ![Printers Found](docs/screenshots/07-printers.png) | ![Setup and test](docs/screenshots/07b-printer-setup.png) |

| Quality test page | Line and alignment page |
|---|---|
| ![Quality test page](docs/screenshots/08-test-page-quality.png) | ![Line test page](docs/screenshots/08-test-page-lines.png) |

### Settings, About and a problem

| Settings | About | Paper out |
|---|---|---|
| ![Settings](docs/screenshots/10-settings.png) | ![About](docs/screenshots/11-about.png) | ![Paper out](docs/screenshots/12-paper-out.png) |

## 3. Compatibility

LinPrinter is ever evolving: each release adds and verifies more printers
and systems.

| | |
|---|---|
| Printers | USB printers that print driverless (IPP Everywhere / AirPrint over IPP-USB). That covers most inkjet and laser printers since about 2015 from Canon, Epson, HP, Brother, Samsung, Xerox and others. |
| Older printers | Any USB printer with a working CUPS queue (Gutenprint, HPLIP, vendor drivers) |
| Verified | Canon TR150 series (USB, driverless): printing, ink, defaults, test pages and maintenance links |
| Systems | Linux Mint 22 (tested). Ubuntu 24.04 (the package is tested offline in a clean ubuntu:24.04). Other Debian-based systems with Python 3.10+, GTK 3, CUPS and Ghostscript. |
| Not yet | Wi-Fi / network printers, automatic two-sided printing, N-up and booklets |

To check a printer, open **Printers** or run `./run.sh --list-printers`.

**Requirements** (all distro packages, no pip): python3, python3-gi,
python3-gi-cairo, gir1.2-gtk-3.0, python3-pil, cups, cups-client,
cups-filters, cups-ipp-utils, ipp-usb, ghostscript, fontconfig,
fonts-dejavu-core, librsvg2-common. The list lives in [`app.json`](app.json);
`install.sh` and the package use the same one.

## 4. Installation

Two ways, both in this repository. Run them as your normal user; they ask
for sudo only when something must be installed.

| | Installer script (default) | Installer package |
|---|---|---|
| Command | `bash install.sh` | `bash install.sh --package`, or `sudo apt install ./dist/linprinter_0.2.5_all.deb` |
| Installs to | runs from this folder | `/opt/linprinter`, command `linprinter` |
| Menu entry | for you (`~/.local/share/applications`) | for every user |
| Updates | `git pull` | install the new `.deb` |
| Best for | trying it, development | everyday use, several users |

### Installer script

```bash
git clone https://github.com/MensuraMedia/linprinter.git
cd linprinter
bash install.sh
```

The installer:
- adds any missing packages;
- adds LinPrinter to the menu with its icon;
- checks that the app starts, CUPS is running, ipp-usb is present and the
  printer can be found.

Each step ends in **OK**, **FIXED** or **FAIL**, followed by a summary. It is
safe to run again.

### Installer package

```bash
bash install.sh --package
```

This mode:
- checks `dist/linprinter_<version>_all.deb` against `dist/SHA256SUMS`;
- installs the package system-wide;
- removes your per-user menu entry, so the menu doesn't list LinPrinter twice;
- runs the same checks as the default install.

You can also install the package directly with
`sudo apt install ./dist/linprinter_0.2.5_all.deb`: apt fetches any missing
dependency. To rebuild the package after a change, run
`bash tools/build-deb.sh`.

### Offline machine

LinPrinter is also the `linprinter/` submodule of MensuraMedia's
linux-peripherals collection, which carries an offline package pool with
every dependency (tested in a network-less container). When LinPrinter is
checked out there, both `bash install.sh` and `bash install.sh --package`
take the packages from that pool, with no internet needed.

### Manual

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil cups cups-filters cups-ipp-utils ipp-usb ghostscript fonts-dejavu-core librsvg2-common
./run.sh
```

### Uninstall

```bash
bash install.sh --uninstall   # removes the menu entry, icon and package (if installed); settings stay
```

## 5. Using LinPrinter

1. Plug the printer in with its USB cable and switch it on. On the
   **Print** page, the power mark turns green and the printer is chosen for
   you. If the mark is red, check the cable and power, then press **Find**.
2. **Open…** a document, drop one on the page, or right-click it in your file manager and choose
   **Open With → LinPrinter** (that opens LinPrinter with the document ready to print).
3. Choose the options. The line under them says what will print, for
   example "1 copy · Black & White · Normal · A4 (210 × 297 mm) · Plain paper
   · Fit to page · 3 page(s)".
4. Press **Preview** to see the pages, or **Print**. The progress bar and
   the status line follow the job, and the **Queue** shows it too. **Cancel**
   stops it.
5. To print a document again, find it in **Recent** and click its document
   icon.

Tips:
- **Photos:** choose Paper Size *Photo 4 × 6 in*, Paper Type *Photo paper*,
  Quality *High* and Borderless *On*, or use the *Photo 4 × 6 borderless*
  profile. Borderless is offered only where the printer allows it.
- **Envelopes:** choose the envelope size and type, *Envelope #10* for
  example. The preview shows how the address lands.
- **Pages → Current** prints the page selected in Preview.
- **Print to PDF** is in the printer list. The file is saved as
  `<name>-<date-time>.pdf` in `~/Documents/prints`.

## 6. Setting up and testing your printer

Open **Printers**. Each printer has a **Setup and test** section:

- **Printer's defaults**: the colour, quality, paper size, paper type and
  fitting the printer itself uses. **Use in LinPrinter** makes them the
  Print page's starting choices; you can still change them for each job.
- **Test the printer**:
  - **Print quality page** has colour blocks at 100 / 50 / 25 %, 11 grey
    steps, fine lines for each ink, a gradient, text from 6 to 16 pt, and a
    frame at the printable edge. It shows streaks, gaps (blocked nozzles),
    colour casts, banding, and whether the margins are right.
  - **Print line page** has striped fields for each ink and alignment
    crosses, and shows missing nozzles and misalignment.
  - **Look first** puts the quality page on the Print page, so you can
    preview it or change the paper first.

  Each page asks before printing, uses one sheet of plain paper, and isn't
  added to Recent.
- **Maintenance**: **Printer settings and maintenance** and **Ink details**
  open the printer's own pages. ipp-usb serves them on this computer over
  the USB cable, so nothing goes on the network. That is where you'll find
  cleaning, nozzle check, head alignment, quiet mode, the power-off timer and
  the printer's other settings. The TR150 (like most printers) doesn't let
  other programs change those settings directly. (With the built-in test
  printer these buttons are greyed out.)
- **Identify** makes the printer flash, and the **Ink** gauges show each
  cartridge.
- **Reconnect** re-attaches the printer when it's plugged in but nothing can see it - the state where
  `lsusb` lists it yet it has no working interfaces, and ipp-usb keeps retrying "unable to find current
  configuration". It appears on the Print page next to **Find** whenever a USB printer isn't answering.

  **Why it asks for a password.** Printing doesn't need one: your user talks to ipp-usb, a system
  service that already owns the printer. Re-attaching is different - it tells the *kernel* to detach and
  re-attach a device, which is machine-wide, so only root may do it. LinPrinter never holds privileges:
  it asks **pkexec**, which shows your desktop's own password dialog and runs a small helper that exits
  immediately.

  **It only ever touches that one printer.** The helper is given the printer's USB id, checks the port
  still holds *that* device and that it is a printer (or an unconfigured device with the matching id),
  and refuses anything else. Nothing else on USB is affected - your keyboard, drives and everything else
  keep working. The printer's USB identity is remembered with the printer, so Reconnect also works after
  a restart, or when the printer has been moved to another socket.

  From a terminal: `./run.sh --reconnect`. **Ink alerts** warns before printing when one is low.

A good routine: when prints look streaky or faded, print the **quality
page**. If lines are broken, run cleaning from **Printer settings and
maintenance**, then print the **line page** to check.

## 7. Settings, files and command line

**Settings**:
- theme (with colour swatches);
- Print to PDF folder;
- the low-ink warning level;
- network printing (shown as *Not Supported*);
- feature modules;
- diagnostics: open the log folder, or save a diagnostics zip on this
  computer.

| What | Where |
|---|---|
| Settings | `~/.config/linprinter/settings.json` |
| Print to PDF | `~/Documents/prints` (changeable) |
| Recent list | `~/.local/share/linprinter/recent.json` |
| Logs (14 days, redacted) | `~/.local/state/linprinter/logs/` |
| Jobs being prepared | `/tmp/linprinter-*/`, deleted when LinPrinter closes |
| Package install | `/opt/linprinter`, `/usr/bin/linprinter` |

```text
./run.sh                    start LinPrinter (or `linprinter` after a package install)
./run.sh --test-printer     built-in test printer + Print to PDF only (no hardware, nothing printed)
./run.sh --page printers    open on a page: print, preview, queue, recent, printers, settings, about
./run.sh --list-printers    list the printers LinPrinter can reach, then exit
./run.sh FILE               open a document ready to print (what "Open With > LinPrinter" runs)
./run.sh --debug            verbose log, also in the terminal
./run.sh --version
```

## 8. Troubleshooting

| You see | Try |
|---|---|
| Red power mark, "Printer may be off. Check power settings." | Switch the printer on, check the USB cable, press **Find** (LinPrinter also keeps looking by itself). `systemctl status ipp-usb` should show it running while the printer is plugged in. |
| The connection keeps dropping; the printer has to be found again and again | Almost always the **USB port or cable**, not the printer. Check with `journalctl -k -b \| grep "usb .*error -71"`: if one port keeps appearing, move the printer to another port directly on the computer, and try another cable. `/var/log/ipp-usb/*.log` showing `libusb_bulk_transfer: Input/Output Error` is the same fault. |
| "Load paper in the rear tray." | Load paper and print again. LinPrinter won't send the job another way while the printer needs you. |
| "The printer stopped the job." | Check the printer's display or lights (jam, cover, ink), then print again. |
| Streaks or faded colours | Print the **quality page** (Printers → Setup and test). If lines are broken, run cleaning from **Printer settings and maintenance**. |
| Only "Print to PDF" is listed | Run `./run.sh --list-printers`. Check `lsusb` shows the printer, and that `cups` and `ipp-usb` are installed (`bash install.sh`). |
| An option is missing | LinPrinter shows only what the printer reports. See Printers → Capabilities. |
| Installer says FAIL | Read the FAIL line; it names what's missing. Run `bash install.sh` again after fixing it. |
| Something else | Settings → Diagnostics → **Save diagnostics…**, then look at the zip or send it to whoever helps you. It stays on your computer until you share it. |

## 9. Safety, security and privacy

**Our commitment:** everything happens on this computer. LinPrinter never
sends your documents or any other information to anyone. There is no cloud,
no account, no telemetry and no update check.

- **Where your documents go:** only down the USB cable to your printer, or
  into your Print to PDF folder. Temporary job files are deleted when
  LinPrinter closes.
- **No network:** LinPrinter does not search the network for printers and
  ignores network print queues (`NETWORK_PRINTING = False`). It talks to
  ipp-usb only on `127.0.0.1`. The printer's own pages it opens are on
  `localhost` too, served over USB.
- **Logs** are redacted: serial numbers, device IDs and your home folder
  path are removed. Diagnostics are saved only where you choose.
- **Installation:**
  - The installer uses only your distribution's packages (or the
    linux-peripherals offline pool), never `curl | bash`.
  - The package is checked against `dist/SHA256SUMS` before it's installed.
  - The package has no maintainer scripts.

## 10. Known limits and roadmap

- USB only; Wi-Fi / network printing is not supported yet.
- The TR150 prints one-sided only and doesn't report page ranges, so
  LinPrinter selects the pages itself before sending.
- Planned: Fill-page scaling, N-up, booklets, manual two-sided and a custom
  paper size dialog (see [docs/CONCEPT.md](docs/CONCEPT.md) §13).
- Printer-side settings (cleaning, alignment, quiet mode) are changed on the
  printer's own page; the printer doesn't allow changing them over IPP.

## 11. Development

```bash
python3 -m compileall -q src                                                     # build
python3 -m black --check src tests tools && python3 -m pyflakes src tests tools  # lint
python3 -m pytest -q                                   # 35 tests (uses the built-in test printer)
python3 tools/walkthrough.py                           # scripted UI run → docs/screenshots/
bash tools/build-deb.sh                                # installer package → dist/ + SHA256SUMS
python3 tools/gen_api_docs.py                          # docs/api-reference.md
```

- The **test printer** (`src/backends/test_printer.py`) is a small IPP
  server on `127.0.0.1` that answers with the real TR150's attributes
  (`resources/test-printer/tr150-attributes.json`, identifiers removed).
  CUPS' `ipptool get-printer-attributes.test` passes against it. Tests and
  the walkthrough never print on real hardware.
- The walkthrough runs in a sandbox home folder, so screenshots never show
  your own files.
- Docs:
  - [architecture](docs/architecture.md)
  - [technical reference](docs/TECHNICAL.md)
  - [features](docs/FEATURES.md)
  - [design notes](docs/design/)
  - [API](docs/api-reference.md)
  - [concept](docs/CONCEPT.md)
- Contributor rules are in [CLAUDE.md](CLAUDE.md).

## 12. Credits

- Interface: gtk-python-dashboard-starter by mikesdatawork.
- Build process: MensuraMedia universal-instruction-set.
- Printing: CUPS and cups-filters (OpenPrinting), ipp-usb (OpenPrinting),
  IPP Everywhere (PWG).
- Rendering: Ghostscript (Artifex) and Pillow.
- Icons: [Phosphor Icons](https://phosphoricons.com) by Helena Zhang and
  Tobias Fried (MIT, see `resources/icons/phosphor/LICENSE`).

## 13. License

LinPrinter is shared under the [**Creative Commons
Attribution-NonCommercial 4.0 International**](LICENSE) licence (CC BY-NC 4.0).

- **You're welcome to** use it free of charge, and to share and adapt it for
  any noncommercial purpose - personal and household use, education, research
  and not-for-profit community work. Give credit, link to the licence, and say
  if you changed anything.
- **Commercial use** needs written permission from MensuraMedia first: selling
  it, bundling it into a paid product or service, or using it in the operations
  of a business. We're happy to talk - contact
  [MensuraMedia](https://github.com/MensuraMedia).
- The components LinPrinter builds on keep their own licences.

This is a summary, not a substitute: the [`LICENSE`](LICENSE) file carries the
full legal code, and https://creativecommons.org/licenses/by-nc/4.0/ has the
official deed.
