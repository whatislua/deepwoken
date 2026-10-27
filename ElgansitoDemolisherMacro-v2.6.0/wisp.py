"""Auto wisp: reads Deepwoken's ritual letter box (the outlined box of C / X / V / Z letters you type
through when casting) and presses the letters for you.

How the box behaves (measured on a 1920x1080 recording): the letters rest in slots 80 px apart on
two rows. Pressing the leftmost letter slides the whole queue one slot left, and the pressed letter
turns grey and fades. Letters can be white or purple; both are pressed. So: press the leftmost
bright letter, wait until the queue visibly moves on, then press the next one.
"""
import cv2
import numpy as np

DEFAULT_AREA = [560, 120, 800, 320]   # where to look for the box (x, y, w, h at 1920x1080)
KEYS = "zxcv"


def find_box(gray):
    """(left, top, right, bottom) of the ritual box's bright outline inside the search area, or None."""
    g = gray.astype(np.int16)
    h, w = g.shape
    up, dn = np.roll(g, 2, axis=0), np.roll(g, -2, axis=0)
    line = (g - up > 12) & (g - dn > 12) & (g > 140)
    line[:2], line[-2:] = False, False
    rows = []
    min_run = int(w * 0.3)
    for y in range(h):
        r = line[y]
        if r.sum() < min_run:
            continue
        # longest run of line pixels in this row
        d = np.diff(np.concatenate(([0], r.view(np.int8), [0])))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        k = int(np.argmax(ends - starts))
        if ends[k] - starts[k] >= min_run:
            rows.append((y, starts[k], ends[k]))
    for i, (y0, a0, b0) in enumerate(rows):
        for y1, a1, b1 in rows[i + 1:]:
            if 0.25 * (b0 - a0) <= y1 - y0 <= 0.45 * (b0 - a0) and abs(a1 - a0) < 8 and abs(b1 - b0) < 8:
                return int(a0), int(y0), int(b0), int(y1)
    return None


def classify(mask):
    """'c', 'x', 'v' or 'z' for one glyph's binary mask (rows x cols), or None."""
    h, w = mask.shape
    if h < 8 or w < 6:
        return None

    def span(rows):
        cols = np.where(mask[rows].any(axis=0))[0]
        return (cols.max() - cols.min() + 1) if cols.size else 0

    def segments(row):
        r = mask[row].astype(np.int8)
        return int((np.diff(np.concatenate(([0], r, [0]))) == 1).sum())

    top = slice(0, max(h // 5, 1))
    bottom = slice(h - max(h // 5, 1), h)
    top_w, bottom_w = span(top), span(bottom)
    mid = mask[int(h * 0.38):int(h * 0.62)]
    centre = mask[int(h * 0.35):int(h * 0.65), int(w * 0.35):int(w * 0.65)].mean()
    right_mid = mid[:, int(w * 0.62):].mean()
    left_mid = mid[:, :int(w * 0.35)].mean()
    top_segs = max(segments(r) for r in range(0, max(h // 6, 1)))
    if right_mid < 0.08 and left_mid > 0.2 and centre < 0.15:
        return "c"  # first: the serif C's top tip can look like two strokes
    if top_segs >= 2 and bottom_w < 0.5 * top_w:
        return "v"
    if top_segs >= 2:
        return "x"
    if centre > 0.12 and top_w > 0.6 * w and bottom_w > 0.6 * w:
        return "z"
    return None


def read(frame):
    """(box, glyphs) where glyphs = [(x_centre, y_centre, letter)] for bright letters, left to right
    (frame coordinates). box is None when no ritual box is on screen."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    box = find_box(gray)
    if box is None:
        return None, []
    l, t, r, b = box
    inner = frame[t + 3:b - 2, l + 3:r - 2]
    hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)
    white = (hsv[..., 2] > 200) & (hsv[..., 1] < 55)
    purple = (hsv[..., 1] > 55) & (hsv[..., 2] > 150) & (hsv[..., 0] > 105) & (hsv[..., 0] < 155)
    mask = (white | purple).astype(np.uint8)
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask)
    size = (b - t)  # glyphs are ~20% of the box height
    glyphs = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (0.1 * size <= h <= 0.32 * size and 0.06 * size <= w <= 0.32 * size and area > 0.006 * size * size):
            continue
        letter = classify(lab[y:y + h, x:x + w] == i)
        if letter:
            glyphs.append((int(cents[i][0]) + l + 3, int(cents[i][1]) + t + 3, letter))
    glyphs.sort()
    return box, glyphs


class Tracker:
    """Decides when to press: the leftmost letter once it's been read the same twice in a row, then
    nothing until the queue moves on (that letter is gone or the leftmost one is much further right).
    If nothing moves for `retry_s`, the same letter is pressed again, at most twice."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.pending = None      # (letter, x) we pressed and are waiting to see go
        self.pressed_at = 0.0
        self.retries = 0
        self.candidate = None    # (letter, x) read last frame
        self.presses = 0

    def step(self, glyphs, now, retry_s=0.35, confirm=True):
        """The key to press now ('c' / 'x' / 'v' / 'z') or None."""
        if not glyphs:
            self.candidate = None
            if self.pending and now - self.pressed_at > 1.0:
                self.pending = None  # box empty for a while: that cast is over
            return None
        x, _, letter = glyphs[0]
        if self.pending:
            p_letter, p_x = self.pending
            moved_on = x > p_x + 30 or (letter != p_letter and abs(x - p_x) > 8)
            if moved_on:
                self.pending, self.retries = None, 0
            else:
                self.pending = (p_letter, min(p_x, x))  # it slides left a little before fading
                if now - self.pressed_at > retry_s and self.retries < 2 and letter == p_letter:
                    self.retries += 1
                    self.pressed_at = now
                    return letter
                return None
        seen = (letter, x)
        stable = self.candidate is not None and self.candidate[0] == letter and abs(self.candidate[1] - x) < 12
        self.candidate = seen
        if confirm and not stable:
            return None
        self.pending = seen
        self.pressed_at = now
        self.presses += 1
        return letter
