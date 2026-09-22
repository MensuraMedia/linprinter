"""
Layout Configuration
Centralized layout dimensions and spacing constants
"""


class Dimensions:
    """Layout dimension constants"""

    SIDEBAR_WIDTH = 150
    LOGO_AREA_WIDTH = 150
    LOGO_AREA_HEIGHT = 150
    LOGO_IMAGE_SIZE = 72
    NAV_BUTTON_HEIGHT = 28

    CONTENT_MARGIN = 28
    CONTENT_SPACING = 14

    WINDOW_DEFAULT_WIDTH = 1180
    WINDOW_DEFAULT_HEIGHT = 820

    THUMBNAIL_HEIGHT = 120  # preview page strip
    PREVIEW_MIN_HEIGHT = 160  # small, so the window can be snapped to a quarter of the screen


class Spacing:
    """Spacing constants"""

    NONE = 0
    SMALL = 6
    MEDIUM = 10
    LARGE = 16
    XLARGE = 24


class Layout:
    """Main layout configuration"""

    dimensions = Dimensions
    spacing = Spacing
