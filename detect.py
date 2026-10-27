"""Screen capture and the three ways of recognising something on screen.

  image       find a saved picture (template matching)
  pixel       one pixel is a given colour
  color_area  enough of an area is a given colour (good for flashes and effects)

Every detector produces a score and the score it needs, so the GUI can show
how close a test came.
"""
import cv2
import mss
import mss.tools
import numpy as np

import config

# mss 10 renamed mss.mss to mss.MSS.
MSS = getattr(mss, "MSS", None) or mss.mss

TYPES = {"image": "Find a picture", "pixel": "Pixel colour", "color_area": "Colour in an area"}


def read_image(path):
    # cv2.imread can't open paths with non-ASCII characters on Windows.
    data = np.fromfile(config.resolve(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    if img is None:
        raise ValueError(f"cannot read picture '{path}'")
    return img


def write_image(path, bgr):
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise ValueError("could not encode image")
    buf.tofile(config.resolve(path))


def grab(sct, box):
    """Capture a {left, top, width, height} box as a BGR array."""
    return cv2.cvtColor(np.array(sct.grab(box)), cv2.COLOR_BGRA2BGR)


def monitor_box(sct, index):
    monitors = sct.monitors
    mon = monitors[index if 0 < index < len(monitors) else 1]
    return {k: mon[k] for k in ("left", "top", "width", "height")}


class Detector:
    def __init__(self, spec):
        self.type = spec.get("type", "image")
        self.region = spec.get("region")
        if self.type not in TYPES:
            raise ValueError(f"unknown detector type '{self.type}'")
        if self.type == "image":
            path = spec.get("template")
            if not path:
                raise ValueError("no picture chosen")
            self.template = read_image(path)
            self.need = spec.get("threshold", 0.8)
        elif self.type == "pixel":
            self.point = spec["point"]
            self.color = spec["color"]
            self.need = 1 - spec.get("tolerance", 10) / 255
        else:
            if not self.region:
                raise ValueError("colour-in-area needs an area")
            self.color = spec["color"]
            self.tolerance = spec.get("tolerance", 30)
            self.need = spec.get("min_fraction", 0.15)

    def box(self, fallback):
        """The smallest screen box this detector needs captured."""
        if self.type == "pixel":
            return {"left": self.point[0], "top": self.point[1], "width": 1, "height": 1}
        if self.region:
            left, top, w, h = self.region
            return {"left": left, "top": top, "width": max(w, 1), "height": max(h, 1)}
        return fallback

    def measure(self, frame, origin):
        """Returns (found, score, screen position or None)."""
        ox, oy = origin
        if self.type == "pixel":
            x, y = self.point[0] - ox, self.point[1] - oy
            if not (0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]):
                raise ValueError(f"pixel {tuple(self.point)} is off the captured screen")
            b, g, r = (int(v) for v in frame[y, x])
            diff = max(abs(r - self.color[0]), abs(g - self.color[1]), abs(b - self.color[2]))
            score = 1 - diff / 255
            return score >= self.need, score, tuple(self.point)

        area, ax, ay = self._crop(frame, ox, oy)
        if self.type == "image":
            th, tw = self.template.shape[:2]
            if area.shape[0] < th or area.shape[1] < tw:
                return False, 0.0, None
            res = cv2.matchTemplate(area, self.template, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            score = max(float(score), 0.0)
            pos = (ax + loc[0] + tw // 2, ay + loc[1] + th // 2)
            return score >= self.need, score, pos

        want = np.array(self.color[::-1], dtype=np.int16)  # stored RGB, frame is BGR
        mask = (np.abs(area.astype(np.int16) - want) <= self.tolerance).all(axis=2)
        score = float(mask.mean()) if mask.size else 0.0
        pos = None
        if score >= self.need:
            ys, xs = np.nonzero(mask)
            pos = (ax + int(xs.mean()), ay + int(ys.mean()))
        return score >= self.need, score, pos

    def _crop(self, frame, ox, oy):
        if not self.region:
            return frame, ox, oy
        left, top, w, h = self.region
        x0, y0 = max(left - ox, 0), max(top - oy, 0)
        x1, y1 = min(left - ox + w, frame.shape[1]), min(top - oy + h, frame.shape[0])
        return frame[y0:y1, x0:x1], ox + x0, oy + y0

    def check_now(self, monitor_index=1):
        with MSS() as sct:
            box = self.box(monitor_box(sct, monitor_index))
            return self.measure(grab(sct, box), (box["left"], box["top"]))


def describe_score(det, score):
    if det.type == "color_area":
        return f"{score:.0%} of area (needs {det.need:.0%})"
    return f"{score:.2f} (needs {det.need:.2f})"
