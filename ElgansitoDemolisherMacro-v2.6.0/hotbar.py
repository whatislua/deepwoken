"""Reads Deepwoken's hotbar (the numbered slots along the bottom) to see when a mantra is on cooldown.

A slot on cooldown is drawn darker than when it's ready. Each slot's ready brightness is learned while
you play (the brightest it's been lately), and a slot well below that counts as cooling. Defaults are
for a 1920x1080 screen: slot 1 centred at x 564, 72 px apart, the slot faces between y 1004 and 1058.
"""
import cv2

DEFAULT = {"x0": 564, "step": 72, "y": [1004, 1058], "half": 26}
COOLING_BELOW = 0.70   # under 70% of the slot's ready brightness = on cooldown
READY_ABOVE = 0.85     # back over 85% = ready (the gap avoids flicker on the way back up)


def capture_box(cfg):
    half = cfg.get("half", 26)
    return {"left": cfg["x0"] - half, "top": cfg["y"][0],
            "width": 9 * cfg["step"] + 2 * half, "height": cfg["y"][1] - cfg["y"][0]}


class HotbarReader:
    def __init__(self):
        self.base = {}    # slot -> learned ready brightness
        self.state = {}   # slot -> last state, for the in-between zone

    def read(self, frame, cfg, slots):
        """{slot: 'ready' | 'cooling'} for the hotbar slots asked for (1-10, where 10 is the 0 key)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        half, step = cfg.get("half", 26), cfg["step"]
        out = {}
        for n in slots:
            cx = half + (n - 1) * step
            v = float(gray[:, max(cx - half, 0):cx + half].mean())
            base = self.base.get(n, v)
            base = max(base * 0.9995, v)  # slowly forgets, so a changed slot picture re-learns
            self.base[n] = base
            if v < base * COOLING_BELOW:
                state = "cooling"
            elif v > base * READY_ABOVE:
                state = "ready"
            else:
                state = self.state.get(n, "ready")
            self.state[n] = state
            out[n] = state
        return out
