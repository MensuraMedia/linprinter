"""
App Context
Shared services handed to every page (settings, print manager, navigation,
theme) plus a tiny event hub so pages can react to each other without
importing each other.

Events: "printers-changed", "printer-selected", "printer-status", "document-changed",
"ticket-changed", "jobs-changed", "documents-changed", "features-changed",
"settings-changed", "open-document", "request-printer-refresh"
"""


class AppContext:
    """Service container + publish/subscribe event hub"""

    def __init__(self, settings, print_manager, nav_manager, theme_applicator):
        """Hold the shared services; window is set later by AppWindow"""
        self.settings = settings
        self.printing = print_manager
        self.nav = nav_manager
        self.theme = theme_applicator
        self.window = None  # set once the main window exists (dialog parent)
        self.features = None  # FeatureRegistry (optional modules); None = no features
        self.preview_page = 1  # the page shown in Preview (Pages → Current)
        self.log_path = None  # today's log file (Settings -> Diagnostics)
        self._listeners = {}

    def on(self, event, callback):
        """Subscribe callback to an event name"""
        self._listeners.setdefault(event, []).append(callback)

    def emit(self, event, *args):
        """Call every subscriber of event with args"""
        for callback in list(self._listeners.get(event, [])):
            callback(*args)
