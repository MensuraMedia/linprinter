# LinPrinter

A document printer for Linux. Print PDFs, images and text on your USB
printer, and see beforehand exactly what will print. You can also follow
jobs, check ink, test and set up the printer, or print to PDF. It's a sibling
of [LinScanner](https://github.com/MensuraMedia/linscanner), built the same
way: the same interface, the same switchable feature modules, and the same
USB-only privacy.

![LinPrinter: the Print page](docs/screenshots/02-print-ready.png)

| | |
|---|---|
| Version | 0.3.0 (see [changelog.md](changelog.md)) |
| Verified printer | Canon TR150 series (USB, driverless) |
| Platform | Linux desktop (Linux Mint 22 / Ubuntu 24.04 and other Debian-based systems), GTK 3, Python 3.10+ |
| Connection | **USB cable only.** Wi-Fi and network printing are not supported at this time. |
| Install | `bash install.sh` (runs from this folder), or the installer package [`dist/linprinter_0.3.0_all.deb`](dist/) (system-wide). Both work offline with the linux-peripherals package pool. |
| Licence | [CC BY-NC 4.0](LICENSE.md): free to use, share and adapt with credit; commercial use needs our written permission |

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

Four places, in the rail on the left: **Print**, **Activity**, **Printer**, and **Settings**. The
header shows your printer's state on every page (Ready · Busy · Needs you · Can't reach); click it
to open Printer. One look throughout: the Graphite Night theme, shared with the other Lin\* apps.

| Area | What you get |
|---|---|
| **Print** | Four cards: **Printer** (its state in words, with the fix in place when it needs you), **Document**, **Paper** (size grouped, type, borderless where possible), **Output** (all the same width; copies, colour, quality, pages: all, **custom** — one page such as `2`, or pages such as `1-3, 5` or `3 to 5` — or the current one). **More options** adds odd/even pages, fit or actual size, and profiles. The **live preview** sits beside the options: your paper, the printer's margins shaded, zoom up to 16×, page thumbnails. The bar at the bottom says exactly what will print and holds **Print** (Ctrl+P); when printing isn't possible it says why beside the button. |
| **Documents** | PDF, PNG, JPEG, TIFF (multi-page), BMP, GIF and plain text. **Open…** (Ctrl+O), drop a file on the Print page, or **right-click it in your file manager → Open With → LinPrinter**. |
| **Activity** | **Now printing** with progress and **Cancel print** (asks first). **History**: what printed, or didn't and why, with the settings used; **Print again** opens it with the same settings; **Show file**; remove one entry or clear entries older than 30 days, 90 days or a year. |
| **Printer** | The printer's state, big and in words. **Ink and paper** (the cartridges' own colours, with the percentage in words). **Connection**: the USB port, how LinPrinter reaches it, connection errors from the last 10 minutes, and **Test connection** (20 small questions; nothing is printed or changed). **Look after the printer**: quality and line test pages, Look first, the printer's own settings page. The printer's **own defaults** (use them in LinPrinter), and the **details**. **Identify** makes it flash. |
| **Troubleshooter** | When the printer can't be reached: guided steps, cheapest first - power and cable, **another USB cable**, test the link, power-cycle, another socket, system print queues - each showing what LinPrinter measures right now, and stopping at the first step that works. |
| **Reconnect** | When the printer is plugged in but the system left it unusable, **Reconnect…** re-attaches that one printer (it asks first; your system asks for the password). See [section 6](#6-setting-up-and-testing-your-printer). |
| **Print to PDF** | In the printer list (**Change** on the Printer card). Saves to `~/Documents/prints` (change it in Settings). No printer needed. |
| **Feature modules** | **Ink alerts** (on) warns before printing when a cartridge is low; it never blocks printing. **Print profiles** (off) adds presets (Everyday, Draft, B&W document, Best quality, Photo 4×6 borderless, Envelope #10) plus your own. Switch either off in Settings → Printing. |
| **Reliable printing** | LinPrinter talks to the printer directly (IPP Everywhere over USB, through ipp-usb), with the CUPS queue as a backup, and checks each job with the printer first. It never sends a job another way when *you* need to act (paper, jam, cover, ink) or when the USB connection itself is failing; it tells you what to do instead. |
| **Comfort** | A window that snaps to screen halves and quarters (the preview folds away in a narrow window), keyboard shortcuts (Alt+1…4 for the four places, Ctrl+P, Ctrl+O, F5), dropdowns that never change when you scroll past them (the wheel scrolls the page), and the app icon in the panel and Alt+Tab. |

## 2. A tour in screenshots

The screenshots are made by `tools/walkthrough.py` with the built-in test
printer, which answers exactly like a Canon TR150. They are regenerated for
every release.

### Print

| Ready, with the live preview | More options and custom pages |
|---|---|
| ![Print](docs/screenshots/02-print-ready.png) | ![More options](docs/screenshots/02b-print-more-options.png) |
| **Printing** | **Printed** |
| ![Printing](docs/screenshots/03-printing.png) | ![Printed](docs/screenshots/03b-printed.png) |
| **A photo, borderless 4 × 6 in** | **Print to PDF** |
| ![Borderless photo](docs/screenshots/04-photo-borderless.png) | ![Print to PDF](docs/screenshots/06-print-to-pdf.png) |
| **More options: which pages, fit, profiles** | **A page list that needs a fix** |
| ![More options, end](docs/screenshots/02c-print-more-options-end.png) | ![Page list check](docs/screenshots/02d-page-list-check-it.png) |
| **Needs you: paper out** | **Paper out while printing (the job waits)** |
| ![Paper out](docs/screenshots/12-paper-out.png) | ![Paper out while printing](docs/screenshots/12b-paper-out-while-printing.png) |
| **Can't reach** | **The menu** |
| ![Can't reach](docs/screenshots/13-cant-reach.png) | ![Menu](docs/screenshots/15-menu.png) |

### Activity and the printer

| Activity: now printing and history | Activity: history with results |
|---|---|
| ![Activity](docs/screenshots/05-activity.png) | ![History](docs/screenshots/05b-activity-history.png) |
| **Activity: didn't print** | **Activity: nothing printed yet** |
| ![Didn't print](docs/screenshots/05c-activity-didnt-print.png) | ![Activity empty](docs/screenshots/05a-activity-empty.png) |
| **Printer: health, upkeep, details** | **Troubleshooter: fixed** |
| ![Printer](docs/screenshots/07-printer.png) | ![Troubleshooter fixed](docs/screenshots/07d-troubleshooter-fixed.png) |
| **Troubleshooter: another cable** | **Troubleshooter: test the link** |
| ![Troubleshooter](docs/screenshots/07b-troubleshooter-cable.png) | ![Link test](docs/screenshots/07c-troubleshooter-link-test.png) |
| **Printer: can't reach** | **First start** |
| ![Printer can't reach](docs/screenshots/14-printer-cant-reach.png) | ![First start](docs/screenshots/01-print-first-run.png) |

| Quality test page | Line and alignment page |
|---|---|
| ![Quality test page](docs/screenshots/08-test-page-quality.png) | ![Line test page](docs/screenshots/08-test-page-lines.png) |

### Settings

| Printing | Privacy and diagnostics | About |
|---|---|---|
| ![Settings](docs/screenshots/09-settings.png) | ![Privacy](docs/screenshots/10-settings-privacy.png) | ![About](docs/screenshots/11-settings-about.png) |

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

To check a printer, open **Printer** or run `./run.sh --list-printers`.

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

1. Plug the printer in with its USB cable and switch it on. On **Print**, the
   Printer card says **Ready** and the printer is chosen for you. If it says
   **Can't reach**, the card tells you what to do; **Troubleshoot** walks you
   through it, starting with the cable.
2. **Open…** a document (Ctrl+O), drop one on the page, or right-click it in your file manager and
   choose **Open With → LinPrinter**.
3. Choose the options. The preview beside them changes as you go, and the bar
   at the bottom says what will print, for example "1 copy · 3 pages - Black &
   white · Normal · Letter (8.5 × 11 in) · Plain paper · fit to page".
4. Press **Print** (Ctrl+P). The bar follows the job and ends with "Printed 3
   pages on … · 62 s"; **Activity** shows it too. **Cancel print** stops it
   (it asks first).
5. To print a document again, find it in **Activity** and press **Print
   again**: it opens with the settings it was printed with.

Tips:
- **Photos:** choose Paper Size *Photo 4 × 6 in*, Paper Type *Photo paper*,
  Quality *High* and Borderless *On*, or use the *Photo 4 × 6 borderless*
  profile. Borderless is offered only where the printer allows it.
- **Envelopes:** choose the envelope size and type, *Envelope #10* for
  example. The preview shows how the address lands.
- **Pages → Custom** prints the pages you list in **Page list**: one page (`2`), a run (`1-3`) or
  both (`1-3, 5, 8-10`). The count shows under the label; a list that doesn't fit the document says
  "Check it", and Print waits until it's fixed.
- **Pages → Current** prints the page selected in the preview.
- **Paper runs out while printing?** The header turns **Needs you**, the bar says what it's waiting
  for, and the job continues once you load paper. LinPrinter never sends it another way meanwhile.
- **Print to PDF** is in the printer list (**Change** on the Printer card). The file is saved as
  `<name>-<date-time>.pdf` in `~/Documents/prints`.

## 6. Setting up and testing your printer

Open **Printer** (or click the status in the header). It shows the chosen printer:

- **The printer's own defaults**: the colour, quality, paper size, paper type and
  fitting the printer itself uses. **Use these in LinPrinter** makes them the
  Print page's starting choices; you can still change them for each job.
- **Look after the printer**:
  - **Print quality page** has colour blocks at 100 / 50 / 25 %, 11 grey
    steps, fine lines for each ink, a gradient, text from 6 to 16 pt, and a
    frame at the printable edge. It shows streaks, gaps (blocked nozzles),
    colour casts, banding, and whether the margins are right.
  - **Print line page** has striped fields for each ink and alignment
    crosses, and shows missing nozzles and misalignment.
  - **Look first** puts the quality page on the Print page, so you can
    preview it or change the paper first.

  Each page asks before printing, uses one sheet of plain paper, and isn't
  added to Activity.
- **The printer's own settings page** (and **Ink details**, under Ink and paper)
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
  configuration". It is offered on the Print page's Printer card and on the Printer page whenever a USB
  printer isn't answering, and it asks before doing anything.

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
page**. If lines are broken, run cleaning from the **printer's own settings
page**, then print the **line page** to check.

## 7. Settings, files and command line

**Settings**, in three sections:
- **Printing**: the Print to PDF folder, the low-ink warning level, what to do at
  start (use the last printer, or search every time), and the optional features;
- **Privacy and diagnostics**: what stays on this computer (USB only, no network,
  no account, no telemetry, no AI), the files LinPrinter keeps, Save diagnostics
  and the log folder;
- **About**: version, what it prints, licence, system versions, credits, keyboard
  shortcuts.

| What | Where |
|---|---|
| Settings | `~/.config/linprinter/settings.json` |
| Print to PDF | `~/Documents/prints` (changeable) |
| Activity history | `~/.local/share/linprinter/recent.json` |
| Logs (14 days, redacted) | `~/.local/state/linprinter/logs/` |
| Jobs being prepared | `/tmp/linprinter-*/`, deleted when LinPrinter closes |
| Package install | `/opt/linprinter`, `/usr/bin/linprinter` |

```text
./run.sh                    start LinPrinter (or `linprinter` after a package install)
./run.sh --test-printer     built-in test printer + Print to PDF only (no hardware, nothing printed)
./run.sh --page printer     open on a page: print, activity, printer, settings (0.2 names still work)
./run.sh --list-printers    list the printers LinPrinter can reach, then exit
./run.sh FILE               open a document ready to print (what "Open With > LinPrinter" runs)
./run.sh --debug            verbose log, also in the terminal
./run.sh --version
```

## 8. Troubleshooting

USB problems: [docs/USB-TROUBLESHOOTING.md](docs/USB-TROUBLESHOOTING.md) (cable first, how to
measure the link, what each message means).

| You see | Try |
|---|---|
| **Can't reach** in the header and on the Printer card | Switch the printer on and check the USB cable; **Troubleshoot** walks through the checks, cable first. LinPrinter also keeps looking by itself (F5 searches now). `systemctl status ipp-usb` should show it running while the printer is plugged in. |
| The connection keeps dropping; the printer has to be found again and again | **Try another USB cable first**, straight into the computer - even one that worked for a while (two faulty cables caused a week of TR150 failures). LinPrinter says so itself: "The USB link to this printer keeps failing (… on port 3-3 …)" on the Printer page and in `--list-printers`, read from the kernel log. Measure the link with `sudo python3 tools/usb_linktest.py 04a9:18a4 --compare <a known-good VID:PID>`: any failures mean a bad link. No driver or setting fixes it. Full guide: [docs/USB-TROUBLESHOOTING.md](docs/USB-TROUBLESHOOTING.md). |
| "The printer's USB connection isn't carrying data (ipp-usb answered 503…)" | The printer is stuck, usually holding a job the link cut off. Turn it off and on (or press **Reconnect**). LinPrinter won't send the job to a CUPS queue instead: that queue goes through the same USB link. |
| "The system print queue … sends jobs to serial:/dev/ttyS0, not to this printer" | A queue with the printer's name points somewhere else, so Print in other programs fails. Remove it with the `sudo lpadmin -x …` command shown; CUPS makes a correct one when the printer is connected. |
| "Load paper in the rear tray." | Load paper and print again. LinPrinter won't send the job another way while the printer needs you. |
| "The printer stopped the job." | Check the printer's display or lights (jam, cover, ink), then print again. |
| Streaks or faded colours | Print the **quality page** (Printer → Look after the printer). If lines are broken, run cleaning from the printer's own settings page. |
| Only "Print to PDF" is listed | Run `./run.sh --list-printers`. Check `lsusb` shows the printer, and that `cups` and `ipp-usb` are installed (`bash install.sh`). |
| An option is missing | LinPrinter shows only what the printer reports. See Printer → Details. |
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
- **Kernel log:** to tell a failing USB cable or socket from a printer problem, LinPrinter reads the
  last 10 minutes of `journalctl -k` and keeps only USB port numbers, error counts and USB ids.
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
python3 -m pytest -q                                   # 81 tests (uses the built-in test printer)
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
  - [USB troubleshooting](docs/USB-TROUBLESHOOTING.md)
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
Attribution-NonCommercial 4.0 International**](LICENSE.md) licence (CC BY-NC 4.0).

- **You're welcome to** use it free of charge, and to share and adapt it for
  any noncommercial purpose - personal and household use, education, research
  and not-for-profit community work. Give credit, link to the licence, and say
  if you changed anything.
- **Commercial use** needs written permission from MensuraMedia first: selling
  it, bundling it into a paid product or service, or using it in the operations
  of a business. We're happy to talk - contact
  [MensuraMedia](https://github.com/MensuraMedia).
- The components LinPrinter builds on keep their own licences.

This is a summary, not a substitute: [`LICENSE.md`](LICENSE.md) sets out the
terms in plain words and links the official legal code
(https://creativecommons.org/licenses/by-nc/4.0/legalcode), which governs.
