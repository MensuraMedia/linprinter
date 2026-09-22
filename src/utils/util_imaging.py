"""
Imaging helpers
Rotation for display. Print jobs are rendered by Ghostscript
(modules/manager_render.py); this module only prepares preview images.
"""

from PIL import Image


def flatten(page, img=None):
    """Page image with its rotation applied (print previews have no editing layers yet)"""
    if img is None:
        img = Image.open(page["path"])
        img.load()
    if page.get("rotation"):
        img = img.rotate(-page["rotation"], expand=True)
    return img
