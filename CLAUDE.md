# CLAUDE.md — LinPrinter

## Overview
Document printer for Linux (GTK 3 + driverless IPP over USB, CUPS fallback, Print to PDF), plus printer
setup and testing (the printer's defaults, test pages, Identify, ink, its maintenance pages). Must run from
distro packages only (no pip) and install offline from the linux-peripherals pool (`../offline/`) when it
is checked out there as the `linprinter/` submodule.

## Repository
- Own repo: https://github.com/MensuraMedia/linprinter (public). Also a git submodule of MensuraMedia/linux-peripherals (private) at `linprinter/`.
- Never commit printer serials, UUIDs, MAC-like suffixes, device IDs, hostnames or personal paths (public repo). The test fixture has its UUID zeroed.

## Architecture
- Python 3.10+, GTK 3 via PyGObject, Pillow, Ghostscript (`gs`), IPP spoken directly (`src/backends/ipp.py`)
- Structure from gtk-python-dashboard-starter: `src/{config,ui,pages,modules,utils,backends,features}`
- Details: @docs/architecture.md · @docs/TECHNICAL.md

## Build & Runtime Standards (Enforced)
```bash
# Build
python3 -m compileall -q src
# Test
python3 -m pytest -q
# Lint
python3 -m black --check src tests tools && python3 -m pyflakes src tests tools
# Run
./run.sh            # ./run.sh --test-printer for no hardware
```

## Project Conventions
- File prefixes as in the framework: `config_*`, `manager_*`, `page_*`, `component_*`, `backend_*`, `util_*`, `feature_*`.
- UI never talks to a printer directly: pages → `modules/manager_print.py` → `backends/backend_*.py`.
- Methods, best first: P1 direct IPP (ipp-usb on 127.0.0.1) → P2 CUPS queue; PDF (Print to PDF); T (test printer). Never fall back when the user must act (`USER_ACTION_REASONS`).
- Offer only what the printer reports (`PrinterCapabilities` from Get-Printer-Attributes); printer-specific words in `config/config_print.py`.
- Anything blocking runs off the GTK thread (`PrintManager._in_thread`); results return via `GLib.idle_add`.
- Colours only from `config/config_themes.py`; exceptions: ink gauge (cartridge colours) and test pages.
- New pages: subclass `pages/page_base.BasePage`, add one line to `ui/content_area.PAGES` and `ui/sidebar.NAV_ITEMS`.
- Optional functionality goes in `src/features/feature_<name>.py`; the core only calls `FeatureRegistry` hooks.
- USB only: nothing may use the network (`NETWORK_PRINTING = False`); IPP only to loopback; printer web pages only on localhost; no telemetry. Keep README §8 true.
- Never print on real hardware from tests or tools; use `TestPrinter`. Printing on the user's printer needs their go-ahead.
- Dependencies: distro packages only; add new ones to `app.json` → `offline`, then `../bin/make-offline-bundle linprinter && ../bin/test-offline linprinter`.

## Memory & Workflow (universal-instruction-set)
- Plan first for changes touching 3+ files; wait for approval.
- Every change: an entry in `changelog.md` **and** `changelog.json` (append-only, ISO time, < 120 chars), before committing.
- Features and fixes: a change manifest in `.claude/memory/changes/YYYY-MM-DD_*.md` (root cause for fixes).
- Decisions: `.claude/memory/decisions.md`. Open items: `.claude/memory/pending.md`. Session logs: `.claude/memory/sessions/`.
- Build → Lint → Test must pass before a commit; report failures, don't auto-fix silently.
- Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`). Semantic versioning in `VERSION`.

## References
- @docs/architecture.md
- @.claude/memory/decisions.md
- @.claude/memory/MEMORY.md
