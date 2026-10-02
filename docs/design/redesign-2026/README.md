# The 2026 redesign (LinPrinter 0.3.0)

The approved design that 0.3.0 implements, and what the design adversary checks builds against.

| File | What it is |
|---|---|
| `mockup-App.dc.html` | The clickable mockup's source: every screen and state (`screen` = print-first, print-ready, print-more, print-needs, print-printing, print-printed, print-cant, activity, activity-empty, printer, printer-link, trouble-cable, trouble-result, settings-…). Open it in the claude.ai design canvas, or read its markup. |
| `reference/*.png` | The same screens in **Graphite Night**, rendered from real GTK 3 widgets by LinAppTemplate's demo app. |

## What the design decided

- **Four destinations** instead of seven: Print (with the live preview built in), Activity
  (Queue and Recent merged), Printer (health first, then upkeep and details, plus the
  Troubleshooter), Settings (About folded in). A status chip in the header on every page.
- **One status vocabulary**: Ready · Busy · Needs you · Can't reach, always an icon and a word.
- **Messages**: what happened · why (with evidence) · the next step. USB faults lead with
  *another cable*.
- **No silent automation**: no fallback onto a failing link; Reconnect and queue removal state
  their scope and ask first; only destructive actions are confirmed.
- **WCAG 2.2 AA**: contrast tested for every colour pair, targets ≥ 32 px, focus ring, names on
  every control, status never by colour alone.
- **One theme: Graphite Night** (user decision, 2026-10-02), from LinAppTemplate (github.com/MensuraMedia/linapptemplate, vendored as `src/lintheme/`).

## Intentional departures from the mockup source

| Mockup | Build | Why |
|---|---|---|
| Settings › Appearance with five themes | No Appearance section | Only Graphite Night exists |
| Mint Daylight shown first | Graphite Night everywhere | The user's choice |
| Ink gauges on a dark track | Light, paper-like track | Black ink was invisible on dark |
| Link test: 200 USB control reads | 20 small IPP questions | Needs no password; the USB-level test stays a tool (`tools/usb_linktest.py`) |
| Thumbnails as numbered boxes | Real page thumbnails | The real preview already renders them |
| "Remove queue" removes it | Shows and copies the command | Removing a system queue needs the administrator; LinPrinter never holds privileges |
| Output segments hug their labels | Every Output control fills the field column, equal segments; the stepper keeps compact −/+ | The user asked for uniform buttons (2026-10-02) |
| "up to 99" beside the stepper | A caption under the "Copies" label (also the tooltip) | Beside it, the stepper couldn't share the column's width |
| Pages "Range", row "Range" / "Page range" | Pages "Custom", row "Page list"; the page count is a caption under the label | The user asked for "custom page print (a specific page or number of pages)"; the box spans the column like the rest |
| Dropdowns follow GTK's default | Dropdowns ignore the mouse wheel; it scrolls the page | The user asked that scrolling never changes a dropdown |

Sources: the LinPrinter GUI Guide and Design Reference and the redesign mockups (claude.ai, 2026-10-02).
