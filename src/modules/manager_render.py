"""
Render Manager
Turns what the user opens into what the printer receives:

  any input (PDF / image / text)  -> normalise to PDF
  -> page selection (all / range / odd / even / current)
  -> fit onto the chosen paper (landscape pages turn to portrait automatically)
  -> PWG raster (the IPP Everywhere format) for the printer, PDF for CUPS and
     for Print to PDF, PNG images for the print preview

Ghostscript does the rendering (-dPDFFitPage also rotates a landscape page
to fill portrait paper, which the TR150 needs: it only prints portrait).
Everything happens in the session's temporary folder.
"""

import os
import re
import shutil
import subprocess

from PIL import Image, ImageDraw

from utils.util_logging import get_logger

log = get_logger("render")

POINTS_PER_MM = 72 / 25.4
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif")
TEXT_TYPES = (".txt", ".text", ".log", ".md", ".csv")
OPENABLE = (".pdf",) + IMAGE_TYPES + TEXT_TYPES


class RenderError(Exception):
    """The document couldn't be prepared (plain message for the user)"""


def _gs(args, timeout=300):
    """Run Ghostscript; RenderError with its last message on failure"""
    if not shutil.which("gs"):
        raise RenderError("Printing needs Ghostscript (package ghostscript).")
    cmd = ["gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        raise RenderError(f"Ghostscript couldn't run: {e}")
    if r.returncode != 0:
        log.warning("gs failed (%s): %s", r.returncode, (r.stderr or r.stdout).strip()[-500:])
        raise RenderError("The document couldn't be rendered. It may be damaged or protected.")
    return r


# -- input ------------------------------------------------------------------------
def normalise(path, work_dir):
    """A PDF for any supported input (PDFs are used as they are)"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return path
    os.makedirs(work_dir, exist_ok=True)
    out = os.path.join(work_dir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    if ext in IMAGE_TYPES:
        return _images_to_pdf(path, out)
    if ext in TEXT_TYPES:
        return text_to_pdf(path, out)
    raise RenderError("LinPrinter can print PDF, image (PNG, JPEG, TIFF…) and plain text files.")


def _images_to_pdf(path, out):
    """Every frame of an image file as a PDF page (at its own resolution, 300 dpi if unknown)"""
    from PIL import ImageSequence

    try:
        with Image.open(path) as img:
            dpi = float(img.info.get("dpi", (300, 300))[0]) or 300
            frames = [f.convert("RGB") for f in ImageSequence.Iterator(img)]
    except OSError as e:
        raise RenderError(f"The image couldn't be opened: {e}")
    frames[0].save(out, "PDF", save_all=True, append_images=frames[1:], resolution=dpi)
    return out


def text_to_pdf(path, out, paper_mm=(215.9, 279.4), font_pt=10, dpi=150):
    """A plain text file as monospaced PDF pages (margins 20 mm, lines wrapped)"""
    from PIL import ImageFont

    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", int(font_pt * dpi / 72))
    except OSError:
        font = ImageFont.load_default()
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read().expandtabs(4)
    w, h = (int(v / 25.4 * dpi) for v in paper_mm)
    margin = int(20 / 25.4 * dpi)
    line_h = int(font_pt * 1.35 * dpi / 72)
    char_w = max(1, int(font.getlength("M")))
    cols = max(10, (w - 2 * margin) // char_w)
    lines = []
    for raw in text.splitlines() or [""]:
        while len(raw) > cols:
            lines.append(raw[:cols])
            raw = raw[cols:]
        lines.append(raw)
    per_page = max(1, (h - 2 * margin) // line_h)
    pages = []
    for start in range(0, len(lines), per_page):
        page = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(page)
        for n, line in enumerate(lines[start : start + per_page]):
            draw.text((margin, margin + n * line_h), line, fill="black", font=font)
        pages.append(page)
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=dpi)
    return out


def page_count(pdf):
    """Number of pages in a PDF"""
    r = _gs(
        ["-dNODISPLAY", "-dNOSAFER", "-c", f"({_ps_string(pdf)}) (r) file runpdfbegin pdfpagecount = quit"]
    )
    try:
        return int(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RenderError("The number of pages couldn't be read.")


def _ps_string(path):
    """A path escaped for a PostScript string"""
    return path.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# -- pages ------------------------------------------------------------------------
def select_pages(choice, count, text="", current=1):
    """1-based pages to print: choice all | odd | even | current | range (text like "1-3, 5")"""
    if count <= 0:
        return []
    if choice == "odd":
        return list(range(1, count + 1, 2))
    if choice == "even":
        return list(range(2, count + 1, 2))
    if choice == "current":
        return [min(max(current, 1), count)]
    if choice == "range":
        pages = []
        for part in re.split(r"[,\s]+", text.strip()):
            if not part:
                continue
            m = re.fullmatch(r"(\d*)-(\d*)", part)
            if m:
                a = int(m.group(1) or 1)
                b = int(m.group(2) or count)
                pages += (
                    list(range(max(1, a), min(count, b) + 1))
                    if a <= b
                    else list(range(min(count, a), max(1, b) - 1, -1))
                )
            elif part.isdigit() and 1 <= int(part) <= count:
                pages.append(int(part))
            else:
                raise RenderError(
                    f'"{part}" isn\'t a page range. Use numbers like 1-3, 5 (pages 1 to {count}).'
                )
        if not pages:
            raise RenderError(f"No pages in that range (the document has {count}).")
        return pages
    return list(range(1, count + 1))


# -- rendering --------------------------------------------------------------------
def _media_args(ticket):
    """Ghostscript arguments for the paper size and fitting"""
    w_mm, h_mm = ticket["size_mm"]
    args = [
        f"-dDEVICEWIDTHPOINTS={w_mm * POINTS_PER_MM:.2f}",
        f"-dDEVICEHEIGHTPOINTS={h_mm * POINTS_PER_MM:.2f}",
        "-dFIXEDMEDIA",
    ]
    if ticket.get("scaling", "fit") == "fit":
        args.append("-dPDFFitPage")  # scales to the paper; turns landscape pages to portrait
    return args


def render_pwg(pdf, pages, ticket, out):
    """PWG raster for the printer: 600 dpi, sRGB or sGray, only the chosen pages"""
    colour = 18 if ticket.get("color") == "monochrome" else 19  # cupsColorSpace: 18 sGray, 19 sRGB
    _gs(
        [
            "-sDEVICE=pwgraster",
            f"-r{ticket.get('dpi', 600)}",
            f"-dcupsColorSpace={colour}",
            "-dcupsBitsPerColor=8",
            *_media_args(ticket),
            f"-sPageList={','.join(str(p) for p in pages)}",
            f"-sOutputFile={out}",
            pdf,
        ],
        timeout=900,
    )
    return out


def render_pdf(pdf, pages, ticket, out):
    """A PDF of exactly what will print (Print to PDF, and the CUPS route)"""
    args = ["-sDEVICE=pdfwrite", *_media_args(ticket), f"-sPageList={','.join(str(p) for p in pages)}"]
    if ticket.get("color") == "monochrome":
        args += ["-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray"]
    _gs([*args, f"-sOutputFile={out}", pdf], timeout=600)
    return out


def render_preview(pdf, pages, ticket, out_dir, dpi=60):
    """PNG images of the chosen pages as they will print (paper, fit, colour), with the margins shown"""
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        if old.startswith("preview-") and old.endswith(".png"):
            os.remove(os.path.join(out_dir, old))
    device = "pnggray" if ticket.get("color") == "monochrome" else "png16m"
    pattern = os.path.join(out_dir, "preview-%03d.png")
    _gs(
        [
            f"-sDEVICE={device}",
            f"-r{dpi}",
            *_media_args(ticket),
            f"-sPageList={','.join(str(p) for p in pages)}",
            f"-sOutputFile={pattern}",
            pdf,
        ]
    )
    images = sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.startswith("preview-"))
    if not ticket.get("borderless"):
        for path in images:
            _shade_margins(path, ticket.get("margins_mm", (0, 0, 0, 0)), dpi)
    return images


def _shade_margins(path, margins_mm, dpi):
    """Grey the area the printer can't print on (top, right, bottom, left margins)"""
    top, right, bottom, left = (int(m / 25.4 * dpi) for m in margins_mm)
    if not any((top, right, bottom, left)):
        return
    img = Image.open(path).convert("RGB")
    w, h = img.size
    shade = Image.new("RGB", img.size, (205, 205, 205))
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    for box in ((0, 0, w, top), (0, h - bottom, w, h), (0, 0, left, h), (w - right, 0, w, h)):
        d.rectangle(box, fill=150)
    img = Image.composite(shade, img, mask)
    ImageDraw.Draw(img).rectangle((left, top, w - right - 1, h - bottom - 1), outline=(120, 120, 120))
    img.save(path)
