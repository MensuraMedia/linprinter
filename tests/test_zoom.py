"""Zoom: the range on offer, and how a page is sized for it"""

from ui.components.component_preview import ZOOM_STEPS
from utils.util_display import MAX_RENDER_PIXELS, _fit_within


def test_zoom_range():
    assert ZOOM_STEPS[0] <= 0.25 and ZOOM_STEPS[-1] >= 16.0, "zoom goes from a quarter to at least 16x"
    assert ZOOM_STEPS == sorted(ZOOM_STEPS) and len(set(ZOOM_STEPS)) == len(ZOOM_STEPS)
    assert 1.0 in ZOOM_STEPS  # fit-to-window


def test_fit_within_shrinks_keeping_aspect():
    w, h = _fit_within((2480, 3508), 900, 1200)
    assert (w, h) == (848, 1200)
    assert abs(w / h - 2480 / 3508) < 0.01


def test_fit_within_enlarges_for_deep_zoom():
    """Unlike Image.thumbnail, zooming past the page's own resolution still grows the view"""
    assert _fit_within((496, 700), 3968, 5600) == (3968, 5600)


def test_fit_within_caps_the_pixels():
    w, h = _fit_within((2480, 3508), 40000, 56000)
    assert w * h <= MAX_RENDER_PIXELS * 1.01
    assert abs(w / h - 2480 / 3508) < 0.01


def test_fit_within_handles_empty_size():
    assert _fit_within((0, 0), 100, 100) == (0, 0)
