"""
Display images for the Preview
A 600 dpi colour page is ~100 MB once decoded, so showing it straight from the
scan is slow. Each page gets a small display copy ("proxy", at most
PROXY_MAX_SIDE pixels, JPEG) made once, in the background as pages arrive.
The large view and the thumbnails are drawn from it; only a deep zoom goes
back to the original scan. Quick Edit layers and rotation are applied at
display time, so the proxy never goes stale.
"""

import hashlib
import json
import math
import os
import threading

from PIL import Image

PROXY_MAX_SIDE = 2200


class DisplayCache:
    """Proxy files for pages (thread-safe), kept in a cache folder"""

    def __init__(self, folder):
        """folder: where proxies are written (the session's temp folder)"""
        self.folder = folder
        self._lock = threading.Lock()
        self._proxies = {}  # original path -> (proxy path, reduce factor, original's mtime)
        self._page_locks = {}  # original path -> lock
        self._original = (None, None)  # (path, decoded image): one full-size page kept for zoom

    def proxy(self, path):
        """(proxy path, factor) for a page image, creating it if needed.

        One lock per page: the background warmer and the display never write
        the same proxy at once, and the file appears atomically (rename)."""
        with self._lock:
            page_lock = self._page_locks.setdefault(path, threading.Lock())
        with page_lock:
            return self._proxy_locked(path)

    def _proxy_locked(self, path):
        """proxy() body, with the page's lock held"""
        mtime = os.path.getmtime(path)
        with self._lock:
            known = self._proxies.get(path)
            if known and known[2] == mtime and os.path.exists(known[0]):
                return known[0], known[1]
        img = Image.open(path)
        factor = max(1, math.ceil(max(img.size) / PROXY_MAX_SIDE))
        img = img.reduce(factor) if factor > 1 else img
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        name = hashlib.sha1(os.path.abspath(path).encode()).hexdigest()[:16]
        os.makedirs(self.folder, exist_ok=True)
        proxy = os.path.join(self.folder, f"proxy-{name}.jpg")
        tmp = proxy + ".part"
        img.save(tmp, "JPEG", quality=90)
        os.replace(tmp, proxy)
        with self._lock:
            self._proxies[path] = (proxy, factor, mtime)
        return proxy, factor

    def warm(self, paths):
        """Create missing proxies in a background thread"""

        def work():
            for p in paths:
                try:
                    self.proxy(p)
                except OSError:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def original(self, path):
        """The full-size page image (the most recent one is kept)"""
        key = (path, os.path.getmtime(path))
        with self._lock:
            if self._original[0] == key:
                return self._original[1]
        img = Image.open(path)
        img.load()
        with self._lock:
            self._original = (key, img)
        return img

    def render(self, page, max_w, max_h, full_size=None):
        """The page as an RGB image fitting max_w x max_h, rotated and with Quick Edit layers.

        full_size: the page's (w, h) at scan resolution; when the target is
        bigger than the proxy, the original scan is used instead (deep zoom)."""
        from utils.util_imaging import flatten

        proxy, factor = self.proxy(page["path"])
        src = Image.open(proxy)
        rot = page.get("rotation", 0)
        need_w, need_h = (max_h, max_w) if rot in (90, 270) else (max_w, max_h)
        if full_size and (need_w > src.width * 1.05 or need_h > src.height * 1.05) and factor > 1:
            src, factor = self.original(page["path"]), 1
        dpi = (page.get("dpi") or 300) / factor  # keeps text sizes right on the smaller copy
        img = flatten(dict(page, dpi=dpi), img=src.copy() if src is not None else None)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((max(max_w, 1), max(max_h, 1)), Image.BILINEAR)
        return img.convert("RGB")

    def size(self, page):
        """Full-resolution (w, h) of a page after rotation"""
        with Image.open(page["path"]) as img:
            w, h = img.size
        return (h, w) if page.get("rotation", 0) in (90, 270) else (w, h)


def page_key(page):
    """Identity of what a page looks like (image and its version, rotation, Quick Edit layers)"""
    layers = json.dumps(page.get("overlays") or [], sort_keys=True)
    try:
        version = os.path.getmtime(page["path"])
    except OSError:
        version = 0
    return (page["path"], version, page.get("rotation", 0), hashlib.sha1(layers.encode()).hexdigest())
