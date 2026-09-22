"""
Feature modules
Optional features live here as feature_<name>.py files. The core never imports
them directly: it calls the FeatureRegistry at a few hook points, and every
hook call is isolated, so a feature that is disabled, deleted or broken can't
affect printing.

Hooks a feature may implement (all optional):
  before_print(ctx, printer, ticket, status) -> [warning, ...]   asked before printing; warnings are
                                                                 shown and the user confirms
  after_print(ctx, printer, ticket, result)                      after a job finished
  extend_print_page(page), extend_preview(page)                  add widgets to those pages
  settings_widget(ctx) -> Gtk.Widget | None                      per-feature settings (Settings page)
"""

import glob
import importlib
import importlib.util
import os
import time

from utils.util_logging import get_logger

log = get_logger("features")


class BaseFeature:
    """Base class for features; override the hooks you need"""

    id = "base"
    name = "Base feature"
    description = ""
    default_enabled = False
    order = 50  # page-processing order (lower runs first)

    def __init__(self, settings):
        """settings: the SettingsManager (feature options live under feature_settings[id])"""
        self.settings = settings

    def option(self, key, default):
        """This feature's stored option (or default)"""
        return (self.settings.get("feature_settings") or {}).get(self.id, {}).get(key, default)

    def set_option(self, key, value):
        """Store one of this feature's options"""
        all_opts = dict(self.settings.get("feature_settings") or {})
        mine = dict(all_opts.get(self.id, {}))
        mine[key] = value
        all_opts[self.id] = mine
        self.settings.set("feature_settings", all_opts)


class FeatureRegistry:
    """Discovers feature_*.py modules and dispatches hooks to the enabled ones"""

    def __init__(self, settings, folder=None):
        """Load every feature module in folder (default: this package)"""
        self.settings = settings
        self.features = []
        self.errors = []  # (module, message) for features that failed to load or run
        folder = folder or os.path.dirname(__file__)
        for path in sorted(glob.glob(os.path.join(folder, "feature_*.py"))):
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                module = self._load(name, path)
                self.features.append(module.Feature(settings))
            except Exception as e:  # a broken feature file must not stop the app
                self.errors.append((name, f"load failed: {e}"))
                log.exception("feature %s failed to load", name)
        self.features.sort(key=lambda f: f.order)
        log.info(
            "features loaded: %s | enabled: %s",
            ", ".join(f.id for f in self.features),
            ", ".join(f.id for f in self.features if self.is_enabled(f)) or "none",
        )

    @staticmethod
    def _load(name, path):
        """Import a feature module from exactly this file (not whatever shares its name)"""
        package_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.dirname(os.path.abspath(path)) == package_dir:
            return importlib.import_module(f"features.{name}")
        spec = importlib.util.spec_from_file_location(f"features_external.{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # -- state -----------------------------------------------------------------
    def is_enabled(self, feature):
        """Enabled per settings, else the feature's default"""
        states = self.settings.get("features") or {}
        return states.get(feature.id, feature.default_enabled)

    def set_enabled(self, feature_id, enabled):
        """Turn a feature on or off (persisted)"""
        states = dict(self.settings.get("features") or {})
        states[feature_id] = bool(enabled)
        self.settings.set("features", states)
        log.info("feature %s %s", feature_id, "enabled" if enabled else "disabled")

    def get(self, feature_id):
        """Feature by id (loaded, enabled or not), or None"""
        return next((f for f in self.features if f.id == feature_id), None)

    def enabled(self, hook=None):
        """Enabled features, optionally only those implementing a hook"""
        return [f for f in self.features if self.is_enabled(f) and (hook is None or hasattr(f, hook))]

    def _call(self, feature, hook, *args):
        """Call one hook, isolating failures; returns (ok, result)"""
        start = time.monotonic()
        try:
            result = getattr(feature, hook)(*args)
        except Exception as e:
            self.errors.append((feature.id, f"{hook}: {e}"))
            log.exception("feature %s: %s failed (skipped, the rest continues)", feature.id, hook)
            return False, None
        log.debug("feature %s: %s done in %.3f s", feature.id, hook, time.monotonic() - start)
        return True, result

    # -- hooks -----------------------------------------------------------------
    def before_print(self, ctx, printer, ticket, status):
        """Warnings from features before a job is sent (the user confirms them)"""
        warnings = []
        for f in self.enabled("before_print"):
            ok, result = self._call(f, "before_print", ctx, printer, ticket, status)
            if ok and result:
                warnings += list(result)
        return warnings

    def after_print(self, ctx, printer, ticket, result):
        """Notify features that a job finished"""
        for f in self.enabled("after_print"):
            self._call(f, "after_print", ctx, printer, ticket, result)

    def extend(self, hook, page):
        """Let features add widgets to a page (hook: extend_print_page / extend_preview).

        All features that implement the hook are asked; each decides visibility
        from is_enabled so toggling in Settings takes effect immediately."""
        for f in self.features:
            if hasattr(f, hook):
                self._call(f, hook, page)
