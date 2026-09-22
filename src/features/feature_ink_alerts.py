"""
Ink alerts
Before printing, warns when a cartridge is at or below the low-ink level set
in Settings (15 % by default), or empty, so a long job isn't started on an
empty cartridge. The user can print anyway.
"""

from features import BaseFeature
from modules.manager_status import ink_warnings


class Feature(BaseFeature):
    """Warn about low ink before printing"""

    id = "ink_alerts"
    name = "Ink alerts"
    description = "Warns before printing when a cartridge is low or empty (level set in Settings)."
    default_enabled = True
    order = 10

    def before_print(self, ctx, printer, ticket, status):
        """Low-ink warnings for the chosen printer"""
        if printer.virtual:
            return []
        _level, _message, _state, _reasons, markers = status
        return ink_warnings(markers, int(ctx.settings.get("low_ink_percent")))
