"""
Printer model
What a printer can do, normalised from its IPP attributes (IPP Everywhere),
so pages never deal with protocol details. Backends: backend_ipp (direct IPP
over ipp-usb), backend_cups (CUPS queues), backend_pdf (Print to PDF).
"""

import re
from dataclasses import dataclass, field

from backends.ipp import PRINTER_STATES, values
from config.config_print import FRIENDLY_SIZES, FRIENDLY_TYPES, PAPER_GROUPS, TYPE_ORDER

# printer-state-reasons that need the user to act: no fallback to another method
USER_ACTION_REASONS = (
    "media-empty",
    "media-needed",
    "media-jam",
    "door-open",
    "cover-open",
    "marker-supply-empty",
    "input-tray-missing",
)


class PrintError(Exception):
    """A print problem in plain words; code tells the engine whether to try another method"""

    def __init__(self, message, code="error"):
        super().__init__(message)
        self.code = code  # user | unreachable | busy | unsupported | rejected | error

    @property
    def needs_user(self):
        """True if the user must fix something (paper, jam, cover, ink)"""
        return self.code == "user"


@dataclass
class PaperSize:
    """One paper size the printer offers"""

    keyword: str  # e.g. "iso_a4_210x297mm"
    width_mm: float
    height_mm: float
    group: str = "Other"

    @property
    def label(self):
        """Friendly name, e.g. "A4 (210 × 297 mm)" """
        stem = "_".join(self.keyword.split("_")[:2])
        name = FRIENDLY_SIZES.get(
            stem,
            self.keyword.split("_")[1].replace("-", " ").title() if "_" in self.keyword else self.keyword,
        )
        m = re.search(r"_([\d.]+)x([\d.]+)(mm|in)$", self.keyword)  # the size as the printer names it
        dims = (
            f"{m.group(1)} × {m.group(2)} {m.group(3)}" if m else f"{self.width_mm:g} × {self.height_mm:g} mm"
        )
        return name if dims.replace(" ", "") in name.replace(" ", "") else f"{name} ({dims})"


def parse_pwg_size(keyword):
    """(width_mm, height_mm) from a PWG self-describing media name, or None"""
    m = re.search(r"_([\d.]+)x([\d.]+)(mm|in)$", keyword)
    if not m:
        return None
    w, h = float(m.group(1)), float(m.group(2))
    if m.group(3) == "in":
        w, h = w * 25.4, h * 25.4
    return round(w, 1), round(h, 1)


def size_group(keyword):
    """Documents / Photos / Envelopes / Cards / Other for a size keyword"""
    stem = "_".join(keyword.split("_")[:2])
    for group, stems in PAPER_GROUPS:
        if stem in stems:
            return group
    return "Other"


def type_label(keyword):
    """Friendly paper-type name"""
    return FRIENDLY_TYPES.get(keyword, keyword.split(".")[-1].replace("-", " ").capitalize())


@dataclass
class PrinterCapabilities:
    """Everything the Print page needs to know about one printer"""

    sizes: list = field(default_factory=list)  # [PaperSize]
    types: list = field(default_factory=list)  # media-type keywords
    colors: list = field(default_factory=list)  # "color", "monochrome"
    qualities: list = field(default_factory=list)  # "draft", "normal", "high"
    copies_max: int = 1
    sides: list = field(default_factory=lambda: ["one-sided"])
    scaling: list = field(default_factory=list)
    page_ranges: bool = False
    orientations: list = field(default_factory=lambda: [3])
    formats: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    borderless: set = field(default_factory=set)  # {(size keyword, type keyword)} that print edge to edge
    margins: dict = field(default_factory=dict)  # (size keyword, type) -> (top, right, bottom, left) mm
    default_size: str = ""
    default_type: str = ""
    default_color: str = ""  # the printer's own defaults (Printers → Printer's defaults)
    default_quality: str = ""
    default_scaling: str = ""
    alert: str = ""  # printer-alert-description when it isn't "Non-alert"
    links: dict = field(default_factory=dict)  # {"settings": uri, "ink": uri} on this computer only
    custom_range: tuple = ()  # ((min_w, min_h), (max_w, max_h)) mm
    identify: bool = False
    raw: dict = field(default_factory=dict)  # every attribute (Printers Found shows some)

    def size(self, keyword):
        """PaperSize by keyword (None if the printer doesn't offer it)"""
        return next((s for s in self.sizes if s.keyword == keyword), None)

    def can_borderless(self, size, media_type):
        """True if this size / type combination prints edge to edge"""
        return (size, media_type) in self.borderless or (size, "auto") in self.borderless

    def margins_for(self, size, media_type, borderless=False):
        """Unprintable margins in mm (top, right, bottom, left)"""
        if borderless:
            return (0, 0, 0, 0)
        return self.margins.get((size, media_type)) or self.margins.get((size, None)) or (5, 3.4, 5, 3.4)


def _dims(coll):
    """(w_mm, h_mm) from a media-size collection (hundredths of mm)"""
    try:
        return round(coll["x-dimension"] / 100, 1), round(coll["y-dimension"] / 100, 1)
    except (KeyError, TypeError):
        return None


def capabilities_from_ipp(attrs):
    """PrinterCapabilities from Get-Printer-Attributes"""
    caps = PrinterCapabilities(raw=dict(attrs))
    by_dims = {}
    for kw in values(attrs, "media-supported"):
        if kw.startswith("custom_min") or kw.startswith("custom_max"):
            continue
        dims = parse_pwg_size(kw)
        if dims:
            caps.sizes.append(PaperSize(kw, dims[0], dims[1], size_group(kw)))
            by_dims[dims] = kw
    lo = next(
        (parse_pwg_size(k) for k in values(attrs, "media-supported") if k.startswith("custom_min")), None
    )
    hi = next(
        (parse_pwg_size(k) for k in values(attrs, "media-supported") if k.startswith("custom_max")), None
    )
    caps.custom_range = (lo, hi) if lo and hi else ()
    for entry in values(attrs, "media-col-database"):
        kw = by_dims.get(_dims(entry.get("media-size", {})) or ())
        if not kw:
            continue
        mtype = entry.get("media-type")
        margins = tuple(entry.get(f"media-{s}-margin", 0) / 100 for s in ("top", "right", "bottom", "left"))
        if not any(margins):
            caps.borderless.add((kw, mtype))
        else:
            caps.margins.setdefault((kw, mtype), margins)
            caps.margins.setdefault((kw, None), margins)
    types = values(attrs, "media-type-supported")
    caps.types = [t for t in TYPE_ORDER if t in types] + [t for t in types if t not in TYPE_ORDER]
    modes = values(attrs, "print-color-mode-supported")
    caps.colors = [m for m in ("color", "monochrome") if m in modes] or ["monochrome"]
    q = {3: "draft", 4: "normal", 5: "high"}
    caps.qualities = [q[v] for v in values(attrs, "print-quality-supported") if v in q] or ["normal"]
    copies = attrs.get("copies-supported")
    caps.copies_max = int(copies[1]) if isinstance(copies, tuple) else 1
    caps.sides = values(attrs, "sides-supported") or ["one-sided"]
    caps.scaling = values(attrs, "print-scaling-supported")
    caps.page_ranges = bool(attrs.get("page-ranges-supported"))
    caps.orientations = values(attrs, "orientation-requested-supported") or [3]
    caps.formats = values(attrs, "document-format-supported")
    caps.sources = values(attrs, "media-source-supported")
    default = attrs.get("media-col-default") or {}
    caps.default_size = by_dims.get(_dims(default.get("media-size", {})) or (), "") or attrs.get(
        "media-default", ""
    )
    caps.default_type = default.get("media-type", "") if isinstance(default, dict) else ""
    caps.default_color = (
        attrs.get("print-color-mode-default", "")
        if attrs.get("print-color-mode-default") in caps.colors
        else ""
    )
    caps.default_quality = q.get(attrs.get("print-quality-default"), "")
    caps.default_scaling = attrs.get("print-scaling-default", "") or ""
    alert = " ".join(str(v) for v in values(attrs, "printer-alert-description"))
    caps.alert = "" if alert.strip().lower() in ("", "non-alert") else alert.strip()
    for key, name in (("settings", "printer-more-info"), ("ink", "printer-supply-info-uri")):
        uri = attrs.get(name) or ""
        if isinstance(uri, str) and re.match(r"https?://(localhost|127\.0\.0\.1)[:/]", uri):
            caps.links[key] = uri  # ipp-usb serves the printer's own pages locally; never a network address
    caps.identify = 0x003C in values(attrs, "operations-supported")
    return caps


def printer_status(attrs):
    """(state name, reasons, markers) from printer attributes; markers: [{name, color, level, type}]"""
    state = PRINTER_STATES.get(attrs.get("printer-state"), "unknown")
    reasons = [r for r in values(attrs, "printer-state-reasons") if r and r != "none"]
    names, levels = values(attrs, "marker-names"), values(attrs, "marker-levels")
    colors, kinds = values(attrs, "marker-colors"), values(attrs, "marker-types")
    markers = [
        {
            "name": n,
            "level": levels[i] if i < len(levels) else -1,
            "colors": re.findall(r"#[0-9A-Fa-f]{6}", colors[i]) if i < len(colors) else [],
            "type": kinds[i] if i < len(kinds) else "",
        }
        for i, n in enumerate(names)
    ]
    return state, reasons, markers


@dataclass
class PrinterDevice:
    """A physical printer and every way to reach it (best first), like LinScanner's PhysicalDevice"""

    key: str  # stable identity: normalised model (plus USB port when known)
    name: str  # e.g. "Canon TR150 series"
    methods: list = field(default_factory=list)  # [Method]
    caps: PrinterCapabilities = None
    usb: object = None  # usb_probe.UsbDevice when known
    firmware: str = ""
    hint: str = ""
    virtual: bool = False  # Print to PDF / the test printer
    restored: bool = False

    @property
    def id(self):
        """Stable id for the UI"""
        return self.key

    @property
    def label(self):
        """Display name"""
        return self.name


@dataclass
class Method:
    """One way to reach a printer: code (P1 direct IPP, P2 CUPS, PDF, T test), backend, target"""

    code: str
    backend: object
    target: str  # IPP URI, CUPS queue name or PDF folder

    LABELS = {
        "P1": "Driverless IPP over USB (ipp-usb)",
        "P2": "CUPS print queue",
        "PDF": "Print to PDF",
        "T": "Test printer",
    }

    @property
    def label(self):
        """e.g. "Driverless IPP over USB (ipp-usb) · ipp://127.0.0.1:60000/ipp/print" """
        return f"{self.LABELS.get(self.code, self.code)} · {self.target}"
