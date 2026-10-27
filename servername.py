"""Reads the Deepwoken server name (e.g. "Terrific Brass Elk") from the top of the screen
with Windows' built-in text recognition (OCR).

It's the first line of the info block next to the Roblox menu buttons: white text,
which OCR reads well once enlarged and turned dark-on-white. This font's "m" is often
read as "tn" / "ln", so that's corrected, and readings are voted on over time.
"""
import asyncio
import re
from collections import Counter

import cv2
import numpy as np

DEFAULT_REGION = [452, 8, 188, 26]  # 1920x1080: stops before the next column of the HUD

_engine = None


def _ocr_engine():
    global _engine
    if _engine is None:
        from winrt.windows.media.ocr import OcrEngine
        _engine = OcrEngine.try_create_from_user_profile_languages()
        if _engine is None:
            raise RuntimeError("Windows text recognition isn't available")
    return _engine


async def _recognize(gray):
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.storage.streams import DataWriter
    bgra = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGRA)
    writer = DataWriter()
    writer.write_bytes(bgra.tobytes())
    bmp = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8,
                                                 bgra.shape[1], bgra.shape[0])
    return (await _ocr_engine().recognize_async(bmp)).text


def run_ocr(gray):
    """Text in a dark-on-white grayscale image."""
    return asyncio.run(_recognize(gray))


def zoom_for(gray, thr):
    """2x for normal-size text (~10 px at 1080p and up); more for the smaller text of smaller screens."""
    rows = np.nonzero((gray > thr).sum(axis=1) > 0)[0]
    height = (rows.max() - rows.min() + 1) if rows.size else 15
    return 2.0 if height >= 9 else float(np.clip(24 / max(height, 1), 2.0, 5.0))


def clean(text):
    text = text.replace("I-l", "H").replace("n)", "m")
    text = re.sub(r"(?<=[a-z])(tn|ln)(?=[a-z])", "m", text)
    words = re.findall(r"[A-Z][a-z]{2,}", text)
    return " ".join(words[:3]) if len(words) >= 2 else None


def read(region_bgr):
    """The server name in the captured region, or None."""
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    thr = max(170.0, float(np.median(gray)) + 45)  # works on dark and bright backgrounds
    gray = cv2.resize(gray, None, fx=(f := zoom_for(gray, thr)), fy=f, interpolation=cv2.INTER_CUBIC)
    _, ink = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
    ink = cv2.copyMakeBorder(ink, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
    return clean(asyncio.run(_recognize(ink)))


class ServerName:
    """Keeps the most common reading for the current server."""

    def __init__(self):
        self.job = None
        self.votes = Counter()

    def add(self, job, reading):
        if job != self.job:
            self.job, self.votes = job, Counter()
        if reading:
            self.votes[reading] += 1

    @property
    def name(self):
        return self.votes.most_common(1)[0][0] if self.votes else None
