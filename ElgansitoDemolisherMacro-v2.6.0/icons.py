"""Reads Deepwoken's cooldown bubbles (the small round icons under the health bar).

Each bubble's symbol is bright white when the move is ready and a dim brown
while it's on cooldown. Measured on a 1920x1080 recording: ready ~230, cooling
~105, with a short fade between. The row can shift a few pixels with the status
label, so each scan finds the row first: the y where the bubble centres are
brightest.
"""
import cv2
import numpy as np

DEFAULT = {"enabled": True, "x": [933, 951, 969, 987], "y": [928, 962]}
READY_AT = 170           # symbol brightness at or above this = ready
COOLING = (85, 150)      # a dim symbol is in this range; anything else = can't tell
HALF = 4                 # 9x9 px patch at each bubble centre


def capture_box(cfg):
    xs, (y0, y1) = cfg["x"], cfg["y"]
    left = min(xs) - HALF - 2
    return {"left": left, "top": y0, "width": max(xs) - left + HALF + 3, "height": max(y1 - y0, HALF * 2 + 2)}


class IconReader:
    def __init__(self):
        self.row = None  # last good y offset inside the capture box

    def read(self, frame, cfg):
        """['ready' | 'cooling' | None] per bubble, for a frame captured with capture_box(cfg)."""
        box = capture_box(cfg)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cols = [x - box["left"] for x in cfg["x"]]
        h = gray.shape[0]

        def levels(y):
            return [float(np.percentile(gray[y - HALF:y + HALF + 1, c - HALF:c + HALF + 1], 90)) for c in cols]

        gaps = [(a + b) // 2 for a, b in zip(cols, cols[1:])]

        def ringed(c, ys):
            # Each bubble has a thin outline: dark, bright (~185), dark, a few px above and below its centre.
            col = gray[:, c].astype(int)
            return any(0 < y < h - 1 and col[y] > 140 and col[y - 1] < 90 and col[y + 1] < 90 for y in ys)

        def panel_dark(y):
            # Older HUD: a dark panel (~40) between the bubbles. Newer HUD: no panel (the ground shows
            # through), so check for every bubble's outline instead. A bright floor or snow where the
            # bubbles are expected (other screen sizes) passes neither, so those reads aren't trusted.
            if all(np.percentile(gray[y - 1:y + 2, g - 1:g + 2], 90) < 90 for g in gaps):
                return True
            return all(ringed(c, range(y - 8, y - 4)) and ringed(c, range(y + 5, y + 9)) for c in cols)

        # Lock onto the row only when every bubble is lit (text above the row can also be bright,
        # but never at all four bubble columns), and keep it while some are dim.
        lit = [y for y in range(HALF, h - HALF) if min(levels(y)) >= 210 and panel_dark(y)]
        if lit:
            self.row = lit[len(lit) // 2]
        if self.row is None or not panel_dark(self.row):
            return [None] * len(cols)
        out = []
        for v in levels(self.row):
            if v >= READY_AT:
                out.append("ready")
            elif COOLING[0] <= v <= COOLING[1]:
                out.append("cooling")
            else:
                out.append(None)
        return out
