"""Reads your own health % off Deepwoken's health bar.

The bar moves a few pixels with its status label (HEALTHY, DROWNED...) and the
fill changes colour (orange, blue when drowned...), but the empty part is always
a dark grey track. So: find the rows whose left end is coloured fill, then the
fill ends where the first long run of track pixels starts. The fill isn't
perfectly linear with the % the game prints, so the raw fraction goes through
calibration points (raw fill -> real %) you can add from the app.
"""
import re

import cv2
import numpy as np

DEFAULT_REGION = [722, 880, 476, 50]  # 1920x1080: around the health bar, wider than it vertically
TRACK_RUN = 8   # px of track in a row that mark the end of the fill
LEFT_PROBE = (4, 40)  # columns at the bar's left end used to find the bar rows


def _track(hsv_row):
    return (hsv_row[:, 2] < 85) & (hsv_row[:, 1] < 70)


def _fill_like(hsv):
    return (hsv[..., 1] > 55) & (hsv[..., 2] > 90)


def _band(hsv):
    """Rows of the region that are the bar (left end coloured), as (top, bottom) or None."""
    a, b = LEFT_PROBE
    rows = _fill_like(hsv[:, a:b]).mean(axis=1) > 0.9
    best, start = None, None
    for y, on in enumerate(list(rows) + [False]):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if best is None or y - start > best[1] - best[0]:
                best = (start, y)
            start = None
    if best is None or not 10 <= best[1] - best[0] <= 40:
        return None
    return best


def fill_fraction(region_bgr):
    """Raw 0..1 fill of the bar in `region_bgr`, or None if no bar is visible."""
    if region_bgr is None or region_bgr.size == 0:
        return None
    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
    w = hsv.shape[1]
    band = _band(hsv)
    if band is None:
        return None
    top, bottom = band
    # Rows near the band's top and bottom edges stay clear of the "91% HEALTH" text.
    rows = [top + 1, top + 2, bottom - 3, bottom - 2]
    ends = []
    for r in rows:
        track = _track(hsv[r])
        end, run = w, 0
        for x, t in enumerate(track):
            run = run + 1 if t else 0
            if run >= TRACK_RUN:
                end = x - TRACK_RUN + 1
                break
        if end < w and track[end:].mean() < 0.6:
            continue  # this row hit something else (text, label); ignore it
        ends.append(end)
    if len(ends) < 2:
        return None
    ends.sort()
    # Text can only make a row's fill look longer, so trust the shortest pair that agrees.
    for a, b in zip(ends, ends[1:]):
        if b - a <= 4:
            return a / w
    return ends[0] / w


def calibrate(raw, points):
    """Map a raw fill fraction to a real 0..1 health fraction with piecewise-linear points."""
    pts = sorted({(round(a, 4), round(b, 4)) for a, b in points} | {(0.0, 0.0), (1.0, 1.0)})
    return float(np.clip(np.interp(raw, [p[0] for p in pts], [p[1] for p in pts]), 0.0, 1.0))


def read_percent(region_bgr, points):
    """(percent 0-100, raw fill) or (None, None) when the bar isn't on screen."""
    raw = fill_fraction(region_bgr)
    if raw is None:
        return None, None
    return round(calibrate(raw, points) * 100), raw


TEXT_REGION = [880, 884, 160, 36]   # around "91% HEALTH" (1920x1080), tall enough for the bar shifting
HEALTH_WORD_PX = 46                  # width of the word "HEALTH" + space at 1080p


def _white(img, loose=False):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    if loose:  # include the anti-aliased edges of the letters against a coloured bar
        return (hsv[..., 2] > 150) & (hsv[..., 1] < 115)
    return (hsv[..., 2] > 175) & (hsv[..., 1] < 80)


def read_text_percent(img):
    """The number in "N% HEALTH", read with Windows OCR, or None.

    The text band is the lowest band of white text; the number is that text minus the
    word HEALTH on the right. OCR is unreliable on a lone number, so a word is drawn in front of it.
    """
    import servername
    m = _white(img)
    rows = m.sum(axis=1)
    bands, start = [], None
    for y, v in enumerate(list(rows) + [0]):
        if v >= 3 and start is None:
            start = y
        elif v < 3 and start is not None:
            if 6 <= y - start <= 20:
                bands.append((rows[start:y].sum(), start, y))
            start = None
    if not bands:
        return None
    # The status label (HEALTHY / DROWNED) sits above; "N% HEALTH" is the lowest text band.
    _, top, bottom = max(bands, key=lambda b: b[1])
    cols = np.nonzero(m[top:bottom].sum(axis=0) >= 1)[0]
    if cols.size == 0 or cols.max() - cols.min() < HEALTH_WORD_PX + 8:
        return None
    x0, x1 = max(cols.min() - 2, 0), cols.max() - HEALTH_WORD_PX
    # Try a few versions of the image; the first one that reads as a number wins.
    for loose, scale in ((False, 4), (True, 4), (False, 3), (True, 3)):
        mask = _white(img, loose)[max(top - 2, 0):bottom + 2, x0:x1].astype(np.uint8) * 255
        mask = cv2.resize(mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        if loose:
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        ink = 255 - mask
        h = ink.shape[0]
        prefix = np.full((h, 260), 255, np.uint8)
        cv2.putText(prefix, "Count", (8, int(h * 0.8)), cv2.FONT_HERSHEY_SIMPLEX, h / 40, 0, max(2, h // 18))
        text = servername.run_ocr(cv2.copyMakeBorder(np.hstack([prefix, ink]), 30, 30, 30, 30,
                                                     cv2.BORDER_CONSTANT, value=255))
        text = text.replace("C0unt", "Count")
        tail = text.split("Count", 1)[-1].translate(
            str.maketrans({"I": "1", "l": "1", "|": "1", "O": "0", "o": "0", "S": "5"}))
        found = re.match(r"\s*(\d{1,3})", tail)
        if found and 0 <= int(found.group(1)) <= 100:
            return int(found.group(1))
    return None


TEXT_BELOW = 14  # under this %, the bar's fill is too short to measure well: read the text


def read_combined(bar_img, text_img, points):
    """(percent, raw fill): the bar normally, the "N% HEALTH" text when you're under 14%."""
    pct, raw = read_percent(bar_img, points)
    if pct is not None and pct < TEXT_BELOW:
        text = read_text_percent(text_img)
        if text is not None and abs(text - pct) <= 8:  # sanity check against the bar
            pct = text
    return pct, raw
