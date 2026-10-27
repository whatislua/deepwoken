"""Reads Deepwoken's top-of-screen HUD: the region you're in ("The Depths", "Eastern
Luminant"...) and the PvP danger skull (red skull + number = in combat with that many players;
the white skull in the Depths is just the area's warning, not PvP).
"""
import re

import cv2
import numpy as np

import servername

REGION_BOX = [643, 8, 175, 26]      # 2nd column, 1st line (1920x1080)
SKULL_BOX = [930, 58, 64, 62]       # the danger skull under the crossed swords
NUMBER_OFFSET = (17, 6, 26, 26)     # number to the bottom-right of the skull, relative to the skull box's right/centre


def _until_gap(gray, thr, gap=12):
    """Columns up to the first wide gap after the text starts (the next HUD column comes after it)."""
    cols = (gray > thr).sum(axis=0) > 0
    xs = np.nonzero(cols)[0]
    if xs.size == 0:
        return gray
    run, end = 0, gray.shape[1]
    for x in range(xs[0], gray.shape[1]):
        run = 0 if cols[x] else run + 1
        if run >= gap:
            end = x - run + 1
            break
    return gray[:, max(xs[0] - 2, 0):end + 2]


def _prefixed(ink):
    """Draw a word in front: Windows OCR reads a lone number much better with context."""
    h = ink.shape[0]
    prefix = np.full((h, 260), 255, np.uint8)
    cv2.putText(prefix, "Count", (8, int(h * 0.8)), cv2.FONT_HERSHEY_SIMPLEX, h / 40, 0, max(2, h // 18))
    return cv2.copyMakeBorder(np.hstack([prefix, ink]), 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)


def read_region(region_bgr):
    """The area name, e.g. 'The Depths' or 'Eastern Luminant', or None."""
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    thr = max(170.0, float(np.median(gray)) + 45)
    gray = _until_gap(gray, thr)
    zoom = servername.zoom_for(gray, thr)
    gray = cv2.resize(gray, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_CUBIC)
    _, ink = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
    ink = cv2.copyMakeBorder(ink, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
    text = servername.run_ocr(ink)
    text = text.replace("I-l", "H").replace("n)", "m")
    text = re.sub(r"(?<=[a-z])(tn|ln)(?=[a-z])", "m", text)
    words = re.findall(r"[A-Z][a-z']+|of|the", text)
    name = " ".join(words[:4])
    return name if len(name) >= 4 else None


def red_skull(skull_bgr):
    """How much of the skull box is the PvP skull's red (0..1)."""
    hsv = cv2.cvtColor(skull_bgr, cv2.COLOR_BGR2HSV)
    red = ((hsv[..., 0] <= 8) | (hsv[..., 0] >= 170)) & (hsv[..., 1] > 90) & (hsv[..., 2] > 110)
    return float(red.mean())


def read_count(number_bgr):
    """The small number next to the red skull (players in combat with you), or None."""
    gray = cv2.cvtColor(number_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, ink = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    text = servername.run_ocr(_prefixed(ink)).replace("C0unt", "Count")
    text = text.split("Count", 1)[-1].translate(str.maketrans(
        {"I": "1", "l": "1", "|": "1", "!": "1", "O": "0", "o": "0", "S": "5", "s": "5", "Z": "2", "z": "2", "B": "8"}))
    m = re.search(r"\d{1,2}", text)
    return int(m.group()) if m else None


def read_combat(frame_bgr, skull_box=None, origin=(0, 0)):
    """(in_combat, count or None) from a captured frame that contains the skull box."""
    x, y, w, h = skull_box or SKULL_BOX
    ox, oy = origin
    skull = frame_bgr[y - oy:y - oy + h, x - ox:x - ox + w]
    if skull.size == 0 or red_skull(skull) < 0.04:
        return False, None
    dx, dy, nw, nh = NUMBER_OFFSET
    nx, ny = x - ox + w // 2 + dx, y - oy + h // 2 + dy
    number = frame_bgr[max(ny, 0):ny + nh, max(nx, 0):nx + nw]
    return True, read_count(number) if number.size else None


TOP_STRIP = [0, 0, 1300, 44]   # the HUD's first text line, wide enough for any screen size


def find_columns(strip_bgr, gap=14):
    """[(x0, x1)] of separate text blocks on the HUD's first line (white text)."""
    gray = cv2.cvtColor(strip_bgr, cv2.COLOR_BGR2GRAY)
    thr = max(170.0, float(np.median(gray)) + 45)
    cols = (gray > thr).sum(axis=0) > 0
    out, start, run = [], None, 0
    for x, on in enumerate(list(cols) + [False] * gap):
        if on:
            if start is None:
                start = x
            run = 0
        elif start is not None:
            run += 1
            if run >= gap:
                out.append((start, x - run + 1))
                start, run = None, 0
    return [(a, b) for a, b in out if b - a >= 25]


def auto_server_region(strip_bgr):
    """Find the server name and region anywhere on the top line: the server is the first block that
    reads as three capitalised words, the region is the block after it. (server, region)."""
    blocks = find_columns(strip_bgr)
    for i, (a, b) in enumerate(blocks[:8]):
        server = servername.read(strip_bgr[:, max(a - 2, 0):b + 2])
        if server and len(server.split()) == 3:
            region = None
            if i + 1 < len(blocks):
                c, d = blocks[i + 1]
                region = read_region(strip_bgr[:, max(c - 2, 0):d + 2])
            return server, region
    return None, None
