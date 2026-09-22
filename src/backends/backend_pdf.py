"""
Print to PDF (method PDF)
A built-in destination that saves exactly what would print (the chosen pages,
paper, fitting and colour) as a PDF in a folder, ~/Documents/prints by
default (Settings). Always available, no printer or paper needed.
"""

import os
from datetime import datetime

from backends.backend_base import PaperSize, PrintError, PrinterCapabilities, parse_pwg_size, size_group
from config.config_print import PDF_SIZES
from modules.manager_render import render_pdf


def pdf_capabilities():
    """What Print to PDF offers: common sizes, colour or black & white, borderless"""
    sizes = [PaperSize(kw, *parse_pwg_size(kw), size_group(kw)) for kw in PDF_SIZES]
    caps = PrinterCapabilities(
        sizes=sizes,
        types=[],
        colors=["color", "monochrome"],
        qualities=["normal"],
        copies_max=1,
        default_size=PDF_SIZES[0],
    )
    caps.borderless = {(s.keyword, None) for s in sizes}
    caps.margins = {(s.keyword, None): (0, 0, 0, 0) for s in sizes}
    return caps


def unique_path(folder, stem):
    """folder/stem.pdf, or stem-2.pdf, stem-3.pdf, … if taken"""
    path = os.path.join(folder, f"{stem}.pdf")
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem}-{n}.pdf")
        n += 1
    return path


class PdfBackend:
    """Saves print jobs as PDF files"""

    name = "pdf"
    code = "PDF"

    def submit(self, folder, ticket, caps, pdf, pages, work_dir, job_name):
        """Write the PDF; returns its path"""
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            raise PrintError(f"The folder {folder} can't be created: {e}", "user")
        stem = "".join(c for c in os.path.splitext(job_name)[0] if c not in '/\\:*?"<>|').strip() or "print"
        path = unique_path(folder, f"{stem}-{datetime.now():%Y%m%d-%H%M%S}")
        render_pdf(pdf, pages, ticket, path)
        return path

    def status(self, folder):
        """Ready when the folder can be written"""
        parent = folder if os.path.isdir(folder) else os.path.dirname(folder)
        return ("idle" if os.access(parent, os.W_OK) else "stopped"), [], []
