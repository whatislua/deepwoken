"""Finds Deepwoken's Z / X / C / V key prompts on screen.

Templates live in templates/prompts/<ui scale>/<LETTER>.png (from DeepWarden).
Real prompts are a white letter on a dark box; the game also shows decoys on a
bright teal box, which must not be pressed, so the box colour is checked too.
"""
import glob
import os

import cv2
import numpy as np

import config

LETTERS = "ZXCV"
SCAN_SCALE = 0.5            # search a half-size image: 4x faster, still sharp enough
SIZE_STEPS = (0.85, 1.0, 1.15)
FAKE_BOX_BRIGHTNESS = 100   # real boxes are dark (V ~25-60), fake teal boxes ~130


class PromptFinder:
    def __init__(self):
        self.templates = []  # (letter, gray template at scan scale, full-size side)
        for path in glob.glob(os.path.join(config.APP_TEMPLATES, "prompts", "*", "*.png")):
            letter = os.path.splitext(os.path.basename(path))[0].upper()
            if letter not in LETTERS:
                continue
            data = np.fromfile(path, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE) if data.size else None
            if img is None:
                continue
            for step in SIZE_STEPS:
                size = max(int(round(img.shape[1] * SCAN_SCALE * step)), 8)
                self.templates.append((letter, cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA),
                                       size / SCAN_SCALE))
        if not self.templates:
            raise ValueError("no prompt pictures in templates/prompts")

    def find(self, frame_bgr):
        """Best match in the frame: (letter, score, (x, y) centre in frame px, is_fake) or None."""
        small = cv2.resize(frame_bgr, None, fx=SCAN_SCALE, fy=SCAN_SCALE, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        best = None
        for letter, tpl, side in self.templates:
            th, tw = tpl.shape
            if gray.shape[0] < th or gray.shape[1] < tw:
                continue
            res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            if best is None or score > best[1]:
                cx = (loc[0] + tw / 2) / SCAN_SCALE
                cy = (loc[1] + th / 2) / SCAN_SCALE
                best = (letter, float(score), (int(cx), int(cy)), side)
        if best is None:
            return None
        letter, score, (cx, cy), side = best
        return letter, score, (cx, cy), self._is_fake(frame_bgr, cx, cy, side)

    @staticmethod
    def _is_fake(frame, cx, cy, side):
        half = int(side / 2)
        box = frame[max(cy - half, 0):cy + half, max(cx - half, 0):cx + half]
        if box.size == 0:
            return False
        v = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)[..., 2]
        ring = np.concatenate([v[:3].ravel(), v[-3:].ravel(), v[:, :3].ravel(), v[:, -3:].ravel()])
        return float(np.median(ring)) > FAKE_BOX_BRIGHTNESS
