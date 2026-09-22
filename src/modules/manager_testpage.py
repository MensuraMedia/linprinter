"""
Test Page Manager
Built-in test pages for checking a printer (Printers → Test the printer):
  quality  colour and grey blocks, fine lines, a gradient, text sizes and a
           frame at the printable edge — shows streaks, gaps (blocked
           nozzles), colour casts, banding and whether margins are right
  lines    alignment page: thin horizontal and vertical line fields per
           ink, for spotting misaligned or missing nozzles
Drawn with Pillow at 300 dpi and saved as a one-page PDF, then printed like
any document (not added to Recent).
"""

import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from utils.util_paths import read_version

DPI = 300
KINDS = {
    "quality": "Print quality page",
    "lines": "Line and alignment page",
}
CMYK = [("Cyan", (0, 174, 239)), ("Magenta", (236, 0, 140)), ("Yellow", (255, 242, 0)), ("Black", (0, 0, 0))]
RGB = [("Red", (237, 28, 36)), ("Green", (0, 166, 81)), ("Blue", (46, 49, 146))]


def _font(size_pt, bold=False):
    """DejaVu Sans at size_pt (Pillow's default font if missing)"""
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, int(size_pt * DPI / 72))
    except OSError:
        return ImageFont.load_default()


def _mm(v):
    """Millimetres to pixels"""
    return int(round(v / 25.4 * DPI))


def _tint(rgb, amount):
    """rgb mixed with white: amount 1 = full colour, 0 = white"""
    return tuple(int(255 - (255 - c) * amount) for c in rgb)


def _header(d, x, y, title, info):
    """Title and the printer details; returns the y below it"""
    d.text((x, y), title, font=_font(18, True), fill="black")
    y += _mm(10)
    small = _font(8)
    for line in info:
        d.text((x, y), line, font=small, fill=(60, 60, 60))
        y += _mm(4.2)
    return y + _mm(3)


def _info_lines(printer_name, ticket, firmware=""):
    """Who printed what, when"""
    lines = [f"Printer: {printer_name}" + (f" · firmware {firmware}" if firmware else "")]
    if ticket:
        lines.append(
            f"Paper: {ticket.get('size', '?')} · {ticket.get('type') or 'default type'} · "
            f"{ticket.get('color', '?')} · quality {ticket.get('quality', '?')}"
            + (" · borderless" if ticket.get("borderless") else "")
        )
    lines.append(f"LinPrinter {read_version()} · {datetime.now():%Y-%m-%d %H:%M}")
    return lines


def quality_page(d, w, h, left, top, right, bottom, info):
    """Colour blocks, grey ramp, fine lines, gradient, text sizes"""
    x0, x1 = left + _mm(8), w - right - _mm(8)
    y = _header(d, x0, top + _mm(8), "LinPrinter test page", info)
    label = _font(7)

    # colour blocks at 100 / 50 / 25 %
    d.text(
        (x0, y),
        "Colour blocks (100 %, 50 %, 25 %): each should be even, with no white lines or streaks",
        font=label,
        fill="black",
    )
    y += _mm(5)
    colours = CMYK + RGB
    cell = (x1 - x0) // len(colours)
    for n, (name, rgb) in enumerate(colours):
        cx = x0 + n * cell
        for k, amount in enumerate((1, 0.5, 0.25)):
            d.rectangle(
                (cx + 4, y + k * _mm(9), cx + cell - 4, y + (k + 1) * _mm(9) - 6), fill=_tint(rgb, amount)
            )
        d.text((cx + 4, y + _mm(28)), name, font=label, fill="black")
    y += _mm(35)

    # grey ramp in 11 steps
    d.text(
        (x0, y),
        "Grey steps 0–100 %: every step should differ from its neighbours, with no colour tint",
        font=label,
        fill="black",
    )
    y += _mm(5)
    step = (x1 - x0) // 11
    for n in range(11):
        g = int(255 - 255 * n / 10)
        d.rectangle(
            (x0 + n * step, y, x0 + (n + 1) * step - 2, y + _mm(10)), fill=(g, g, g), outline=(160, 160, 160)
        )
        d.text((x0 + n * step + 6, y + _mm(11)), f"{n * 10}", font=label, fill="black")
    y += _mm(18)

    # fine lines per ink (1, 2 and 3 pixels at 300 dpi)
    d.text(
        (x0, y),
        "Fine lines: solid and unbroken; gaps mean blocked nozzles (run cleaning from the printer's maintenance page)",
        font=label,
        fill="black",
    )
    y += _mm(5)
    block_w = (x1 - x0) // 4
    for n, (name, rgb) in enumerate(CMYK):
        bx = x0 + n * block_w
        ly = y
        for width in (1, 2, 3):
            for _ in range(6):
                d.line((bx + 4, ly, bx + block_w - 8, ly), fill=rgb, width=width)
                ly += width + 5
        d.text((bx + 4, ly + 6), name, font=label, fill="black")
    y += _mm(28)

    # smooth gradient
    d.text((x0, y), "Gradient: smooth, without bands", font=label, fill="black")
    y += _mm(5)
    gw = x1 - x0
    for i in range(gw):
        t = i / max(1, gw - 1)
        rgb = (int(255 * (1 - t)), int(120 + 100 * abs(0.5 - t)), int(255 * t))
        d.line((x0 + i, y, x0 + i, y + _mm(9)), fill=rgb)
    y += _mm(15)

    # text sizes
    d.text((x0, y), "Text: sharp edges at every size", font=label, fill="black")
    y += _mm(5)
    for pt in (6, 8, 10, 12, 16):
        f = _font(pt)
        d.text(
            (x0, y), f"{pt} pt  The quick brown fox jumps over the lazy dog 0123456789", font=f, fill="black"
        )
        y += int(pt * 1.5 * DPI / 72)
    return y


def lines_page(d, w, h, left, top, right, bottom, info):
    """Line fields per ink and alignment crosses"""
    x0, x1 = left + _mm(8), w - right - _mm(8)
    y = _header(d, x0, top + _mm(8), "LinPrinter line and alignment page", info)
    label = _font(7)
    d.text(
        (x0, y),
        "Each field should be evenly striped. Missing or doubled lines, or steps at the joins, mean the heads need cleaning or alignment.",
        font=label,
        fill="black",
    )
    y += _mm(7)
    field_w = (x1 - x0 - _mm(6)) // 2
    field_h = _mm(32)
    for n, (name, rgb) in enumerate(CMYK):
        fx = x0 + (n % 2) * (field_w + _mm(6))
        fy = y + (n // 2) * (field_h * 2 + _mm(14))
        d.text((fx, fy), f"{name}: horizontal", font=label, fill="black")
        for ly in range(fy + _mm(5), fy + _mm(5) + field_h, 6):
            d.line((fx, ly, fx + field_w, ly), fill=rgb, width=2)
        vy = fy + field_h + _mm(8)
        d.text((fx, vy - _mm(3)), f"{name}: vertical", font=label, fill="black")
        for lx in range(fx, fx + field_w, 6):
            d.line((lx, vy + _mm(1), lx, vy + _mm(1) + field_h), fill=rgb, width=2)
    y += 2 * (field_h * 2 + _mm(14)) + _mm(4)
    # alignment crosses
    d.text((x0, y), "Crosses: the lines should meet exactly in the middle", font=label, fill="black")
    y += _mm(6)
    for n in range(5):
        cx = x0 + _mm(12) + n * (x1 - x0 - _mm(24)) // 4
        cy = y + _mm(10)
        d.line((cx - _mm(9), cy, cx + _mm(9), cy), fill="black", width=4)
        d.line((cx, cy - _mm(9), cx, cy + _mm(9)), fill=CMYK[n % 3][1], width=4)
    return y + _mm(24)


def make_test_page(kind, out, size_mm, margins_mm, printer_name, ticket=None, firmware=""):
    """Draw test page `kind` for paper size_mm (w, h) and margins (top, right, bottom, left); returns out"""
    w, h = (_mm(v) for v in size_mm)
    top, right, bottom, left = (_mm(max(v, 3)) for v in margins_mm)
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    # frame at the printable edge, with corner marks
    d.rectangle((left, top, w - right - 1, h - bottom - 1), outline=(120, 120, 120), width=5)
    for cx, cy in ((left, top), (w - right, top), (left, h - bottom), (w - right, h - bottom)):
        d.line((cx - _mm(3), cy, cx + _mm(3), cy), fill="black", width=4)
        d.line((cx, cy - _mm(3), cx, cy + _mm(3)), fill="black", width=4)
    info = _info_lines(printer_name, ticket, firmware)
    (lines_page if kind == "lines" else quality_page)(d, w, h, left, top, right, bottom, info)
    d.text(
        (left + _mm(8), h - bottom - _mm(8)),
        "The grey frame marks the printable edge: all four sides should be visible and even.",
        font=_font(7),
        fill=(90, 90, 90),
    )
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    img.save(out, "PDF", resolution=DPI)
    return out
