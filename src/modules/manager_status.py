"""
Status messages
Printer states (IPP printer-state-reasons) and job states in plain words,
with a level for the power / status icon: ok (green), warn (amber), error (red).
Reasons end in -report, -warning or -error (RFC 8011 §5.4.12); the level
follows the suffix, the words follow the reason.
"""

POWER_OFF = "Printer may be off. Check power settings."

MESSAGES = {
    "media-empty": "Load paper in the rear tray.",
    "media-needed": "Load paper in the rear tray.",
    "media-low": "Paper is running low.",
    "media-jam": "Paper jam. Remove the jammed sheet, then try again.",
    "door-open": "Close the printer's cover.",
    "cover-open": "Close the printer's cover.",
    "marker-supply-low": "Ink is low.",
    "marker-supply-empty": "Ink is empty. Replace the cartridge.",
    "marker-waste-almost-full": "The ink absorber is almost full.",
    "marker-waste-full": "The ink absorber is full. The printer needs servicing.",
    "toner-low": "Toner is low.",
    "toner-empty": "Toner is empty. Replace the cartridge.",
    "input-tray-missing": "The paper tray is missing.",
    "output-area-full": "Remove the printed pages from the output tray.",
    "offline": POWER_OFF,
    "shutdown": POWER_OFF,
    "timed-out": POWER_OFF,
    "connecting-to-device": "Connecting to the printer…",
    "paused": "The printer is paused.",
    "moving-to-paused": "The printer is pausing.",
    "cleaning": "The printer is cleaning its print head.",
    "spool-area-full": "The printer's memory is full. Wait for jobs to finish.",
    "other": "The printer reports a problem. Check its display or lights.",
}

JOB_WORDS = {
    "pending": "Waiting",
    "pending-held": "Held",
    "processing": "Printing",
    "processing-stopped": "Stopped",
    "canceled": "Cancelled",
    "aborted": "Failed",
    "completed": "Done",
}


def split_reason(reason):
    """(base reason, level) for a printer-state-reason keyword"""
    for suffix, level in (("-error", "error"), ("-warning", "warn"), ("-report", "ok")):
        if reason.endswith(suffix):
            return reason[: -len(suffix)], level
    base = reason
    level = (
        "error"
        if base
        in (
            "media-empty",
            "media-jam",
            "door-open",
            "cover-open",
            "offline",
            "shutdown",
            "marker-supply-empty",
        )
        else "warn"
    )
    return base, level


def describe(state, reasons, reachable=True):
    """(level, message) for the printer: ok / warn / error"""
    if not reachable:
        return "error", POWER_OFF
    worst, words = "ok", []
    order = {"ok": 0, "warn": 1, "error": 2}
    for reason in reasons:
        if reason == "none":
            continue
        base, level = split_reason(reason)
        if level == "ok" and base not in MESSAGES:
            continue
        text = MESSAGES.get(base, f"The printer reports: {base.replace('-', ' ')}.")
        if text not in words:
            words.append(text)
        if order[level] > order[worst]:
            worst = level
    if words:
        return worst, " ".join(words)
    if state == "stopped":
        return "error", "The printer has stopped. Check its display or lights."
    if state == "processing":
        return "ok", "Printing…"
    return "ok", "Ready"


def user_must_act(reasons):
    """True if a reason needs the user (paper, jam, cover, empty ink): don't try another method"""
    from backends.backend_base import USER_ACTION_REASONS

    return any(
        split_reason(r)[0] in USER_ACTION_REASONS and split_reason(r)[1] == "error" for r in reasons
    ) or any(r in USER_ACTION_REASONS for r in reasons)


def ink_warnings(markers, threshold):
    """Plain warnings for cartridges at or below threshold percent"""
    out = []
    for m in markers:
        level = m.get("level", -1)
        if 0 <= level <= threshold:
            out.append(f"{m['name']} ink is {'empty' if level == 0 else f'low ({level} %)'}.")
    return out
