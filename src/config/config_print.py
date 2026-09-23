"""
Print Configuration
Friendly names and groups for what printers report. Nothing here is
printer-specific: the Print page shows only what the chosen printer supports.
"""

import os

# Colour and quality (IPP print-color-mode / print-quality)
COLOR_MODES = {"color": "Color", "monochrome": "Black & White"}
QUALITIES = {"draft": "Draft", "normal": "Normal", "high": "High"}
DEFAULT_QUALITY = "normal"

# Page selection (done by LinPrinter: many printers have no page-ranges)
PAGE_CHOICES = {"all": "All", "range": "Range…", "odd": "Odd", "even": "Even", "current": "Current"}

# Fitting (Ghostscript renders onto the chosen paper)
SCALING = {"fit": "Fit to page", "none": "Actual size"}

# Paper-size groups; PWG self-describing names (RFC / PWG 5101.1) give each size
PAPER_GROUPS = [
    (
        "Documents",
        (
            "iso_a4",
            "na_letter",
            "na_legal",
            "iso_a5",
            "jis_b5",
            "iso_b5",
            "na_executive",
            "na_invoice",
            "iso_a6",
            "na_govt-letter",
            "oe_7x10",
        ),
    ),
    (
        "Photos",
        ("na_index-4x6", "oe_photo-l", "na_5x7", "om_square-photo", "oe_square-photo", "na_govt-letter"),
    ),
    (
        "Envelopes",
        (
            "na_number-10",
            "iso_dl",
            "iso_c5",
            "iso_c6",
            "na_monarch",
            "jpn_you4",
            "jpn_you6",
            "jpn_chou3",
            "jpn_chou4",
        ),
    ),
    ("Cards", ("om_business-card", "jpn_hagaki", "na_index-3x5", "om_card")),
]
FRIENDLY_SIZES = {
    "iso_a4": "A4",
    "iso_a5": "A5",
    "iso_a6": "A6",
    "jis_b5": "B5 (JIS)",
    "iso_b5": "B5",
    "na_letter": "Letter",
    "na_legal": "Legal",
    "na_executive": "Executive",
    "na_invoice": "Statement",
    "na_govt-letter": "8 × 10 in",
    "oe_7x10": "7 × 10 in",
    "na_index-4x6": "Photo 4 × 6 in",
    "oe_photo-l": "Photo L (3.5 × 5 in)",
    "na_5x7": "Photo 5 × 7 in",
    "om_square-photo": "Square photo",
    "oe_square-photo": "Square photo 5 × 5 in",
    "na_number-10": "Envelope #10",
    "iso_dl": "Envelope DL",
    "iso_c5": "Envelope C5",
    "iso_c6": "Envelope C6",
    "na_monarch": "Envelope Monarch",
    "jpn_you4": "Envelope You 4",
    "jpn_you6": "Envelope You 6",
    "jpn_chou3": "Envelope Chou 3",
    "jpn_chou4": "Envelope Chou 4",
    "om_business-card": "Business card",
    "jpn_hagaki": "Hagaki postcard",
    "na_index-3x5": "Index card 3 × 5 in",
}
DEFAULT_PAPER = ("iso_a4", "na_letter")  # the first one the printer offers, else its own default

# Paper types (IPP media-type), with vendor types given readable names
FRIENDLY_TYPES = {
    "auto": "Automatic",
    "stationery": "Plain paper",
    "photographic": "Photo paper",
    "photographic-glossy": "Photo paper (glossy)",
    "photographic-matte": "Photo paper (matte)",
    "envelope": "Envelope",
    "cardstock": "Card stock",
    "labels": "Labels",
    "transparency": "Transparency",
    "com.canon.mtglossy": "Glossy photo paper",
    "com.canon.mtgr": "Glossy photo paper (everyday)",
    "com.canon.mtmat": "Matte photo paper",
    "com.canon.mthires": "High-resolution paper",
    "com.canon.mtinkjet": "Inkjet paper",
    "com.canon.mtinkjeta": "Inkjet paper (address side)",
    "com.canon.mtgreeting": "Greeting card",
    "com.canon.mthagaki": "Hagaki",
    "com.canon.mthagakia": "Hagaki (address side)",
    "com.canon.mthagakiglossy": "Hagaki (glossy)",
    "com.canon.mthagakiglossya": "Hagaki (glossy, address side)",
}
TYPE_ORDER = ("stationery", "photographic", "envelope", "auto")  # listed first, then the rest

# Print to PDF: a built-in destination that saves exactly what would print
PDF_PRINTER_ID = "pdf:"
DEFAULT_PDF_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "prints")
PDF_SIZES = [
    "iso_a4_210x297mm",
    "na_letter_8.5x11in",
    "na_legal_8.5x14in",
    "iso_a5_148x210mm",
    "na_index-4x6_4x6in",
    "na_5x7_5x7in",
    "na_number-10_4.125x9.5in",
    "iso_dl_110x220mm",
]

# USB printers through ipp-usb listen on 127.0.0.1 from port 60000
IPP_USB_PORTS = range(60000, 60016)
IPP_PATHS = ("/ipp/print",)

# Network printing is not supported at this time (USB only, as in LinScanner)
NETWORK_PRINTING = False

# How often the printer's state is read (seconds)
STATUS_EVERY = 5
# Auto-reconnect: after this many failed status checks in a row, search again for the printer
# (a printer that sleeps, is switched off and on, or sits on a flaky USB port comes back by itself)
RECONNECT_AFTER_MISSES = 2
RECONNECT_EVERY = 20  # seconds between those quiet searches
STATUS_EVERY_WHILE_PRINTING = 1
