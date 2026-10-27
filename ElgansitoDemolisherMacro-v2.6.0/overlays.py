"""Standalone always-on-top overlays you can drag anywhere on screen."""
import math
import os
import time
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

import combat

READY = QColor("#34d399")
TEXT = QColor("#e6e8ee")
MUTED = QColor("#8b93a5")
LANDED = QColor("#fde047")
CY_YELLOW = QColor("#f3e600")
CY_CYAN = QColor("#2de2e6")
CY_RED = QColor("#ff3c5f")


def hp_color(frac):
    if frac > 0.60:
        return QColor("#34d399")
    if frac > 0.35:
        return QColor("#fbbf24")
    if frac > 0.15:
        return QColor("#fb923c")
    return QColor("#ef4444")


def cyber_hp_color(frac):
    if frac > 0.60:
        return QColor("#2de2e6")
    if frac > 0.35:
        return QColor("#f3e600")
    if frac > 0.15:
        return QColor("#ff9f1c")
    return QColor("#ff3c5f")


def widget_catalog(cfg):
    """(id, title, description) for every overlay that can be placed."""
    items = [
        ("status", "Status pill", "Shows whether macros are on and the game is focused."),
        ("macros", "Macro list", "Your macros, their hotkeys, and which one is running."),
        ("party", "Party HP", "Your HP and your friends' HP as bars, shared between Elgansito Demolisher Macro users."),
        ("builder", "BUILDER 101", "Your build's talents, top-right; ticked ones disappear."),
    ]
    if os.environ.get("ELGANSITO_LITE") == "1":  # Lite has no Party HP or Builder
        items = [i for i in items if i[0] not in ("party", "builder")]
    for cd in cfg.get("cooldowns", []):
        items.append((f"cooldown:{cd['name']}", f"{cd['name']} bar",
                      f"Live {cd['name'].lower()} cooldown bar. Flashes when it lands."))
    return items


class Overlay(QWidget):
    def __init__(self, controller, wid, w, h):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.controller = controller
        self.wid = wid
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle(wid)
        self.resize(w, h)
        self.apply_style()

    def apply_style(self):
        ov = self.controller.cfg["overlay"]
        self.setWindowOpacity(ov.get("opacity", 0.92))
        locked = ov.get("locked", False)
        if bool(self.windowFlags() & Qt.WindowTransparentForInput) != locked:
            visible = self.isVisible()
            self.setWindowFlag(Qt.WindowTransparentForInput, locked)
            if visible:
                self.show()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()
        elif e.button() == Qt.RightButton:
            menu = QMenu(self)
            menu.addAction("Hide", lambda: self.controller.hide_overlay(self.wid))
            menu.addAction("Open control panel", self.controller.show_main)
            menu.exec(e.globalPosition().toPoint())

    def moveEvent(self, e):
        self.controller.overlay_moved(self.wid, self.x(), self.y())
        # Snap to nearby bars a moment after you stop dragging.
        if not getattr(self, "_snapping", False) and self.controller.cfg["overlay"].get("snap", True):
            if not hasattr(self, "_snap_timer"):
                self._snap_timer = QTimer(self, singleShot=True, interval=250, timeout=self.snap)
            self._snap_timer.start()

    def snap(self):
        """Line up with the closest other overlay: same left edge, stacked just above or below it."""
        gap = int(self.controller.cfg["overlay"].get("line_gap", 6))
        reach = 16
        x, y = self.x(), self.y()
        best = None
        for other in self.controller.overlays.values():
            if other is self or not other.isVisible():
                continue
            ox, oy, ow, oh = other.x(), other.y(), other.width(), other.height()
            for ny in (oy + oh + gap, oy - self.height() - gap, oy):
                if abs(y - ny) <= reach and abs(x - ox) <= max(reach, ow // 3):
                    d = abs(y - ny) + abs(x - ox)
                    if best is None or d < best[0]:
                        best = (d, ox, ny)
        if best and (best[1], best[2]) != (x, y):
            self._snapping = True
            self.move(best[1], best[2])
            self._snapping = False

    def background(self, p):
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 10, 10)
        p.fillPath(path, QColor(12, 14, 19, 220))
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.drawPath(path)


class CooldownOverlay(Overlay):
    """A cooldown bar. Styles: card (name + time), flat (plain thick bar), neon (angled glowing bar like
    the Cyberpunk one), image (your own skin pictures). Optional text like "AUTOPARRY METER READY"."""

    def __init__(self, controller, wid):
        super().__init__(controller, wid, 250, 50)
        self.name = wid.split(":", 1)[1]
        self.cache = {}  # scaled skin pictures and shapes, rebuilt only when the size or files change

    def text_cfg(self):
        return self.controller.cfg["overlay"].get("bar_text", {})

    def paintEvent(self, e):
        ov = self.controller.cfg["overlay"]
        style = ov.get("bar_style", "flat")
        txt = self.text_cfg()
        text_on = txt.get("enabled", False) and style != "card"
        text_h = int(txt.get("size", 9)) + 8 if text_on and txt.get("position", "above") == "above" else 0
        if style == "card":
            size = (250, 50)
        else:
            bar_h = int(ov.get("flat_height", 12))
            if style == "edge":
                bar_h = max(bar_h, 16)  # the frame, track and // marks need a little room
            size = (int(ov.get("flat_width", 178)), bar_h + text_h)
        if (self.width(), self.height()) != size:
            self.resize(*size)
            return
        p = QPainter(self)
        cd = self.controller.engine.cooldown(self.name)
        if style == "card":
            self.paint_card(p, cd)
            return
        bar = QRectF(0.5, text_h + 0.5, self.width() - 1, self.height() - text_h - 1)
        t = combat.now()
        frac = 0.0 if cd is None else max(min(1 - cd.remaining(t) / cd.span(), 1), 0)
        flash = 0.0 if cd is None else max(0.0, 1 - (t - cd.landed_at) / 0.6)
        colour = QColor(cd.color) if cd is not None else QColor("#69b9e8")
        if style == "neon":
            self.paint_neon(p, bar, frac, flash, colour)
        elif style == "image":
            self.paint_image(p, bar, frac, flash, colour)
        elif style == "edge":
            self.paint_edge(p, bar, frac, flash, colour)
            if text_on and not text_h:
                self.edge_plate(p, cd, t, bar)
        else:
            self.paint_flat(p, bar, frac, flash, colour)
        if text_on:
            self.paint_text(p, cd, t, bar, text_h)

    # ---- text -----------------------------------------------------------------
    def status_text(self, cd, t):
        if cd is None:
            return "?"
        if t - cd.landed_at < 0.6:
            return "LANDED"
        left = cd.remaining(t)
        return "READY" if left == 0 else f"{left:.1f}s"

    def paint_text(self, p, cd, t, bar, text_h):
        txt = self.text_cfg()
        label = (cd.label if cd is not None and getattr(cd, "label", "") else self.name)
        status = self.status_text(cd, t)
        text = txt.get("template", "{NAME} {STATUS}").format(
            NAME=label.upper(), name=label, STATUS=status if status[:1].isdigit() else status.upper(), status=status)
        p.setFont(QFont(txt.get("font", "Bahnschrift"), int(txt.get("size", 9)), QFont.Bold))
        colour = QColor(txt.get("color", "#ffffff"))
        if text_h:
            area = QRectF(2, 0, self.width() - 4, text_h - 2)
            align = Qt.AlignLeft | Qt.AlignVCenter
        else:
            area = bar
            align = Qt.AlignCenter
        p.setPen(QColor(0, 0, 0, 200))  # small shadow so it reads on any background
        p.drawText(area.translated(1, 1), align, text)
        p.setPen(colour)
        p.drawText(area, align, text)

    # ---- styles -----------------------------------------------------------------
    def paint_flat(self, p, rect, frac, flash, colour):
        """A plain thick bar in the cooldown's own colour, filling up as it recharges."""
        p.fillRect(rect, QColor(30, 34, 42, 235))
        if frac > 0:
            p.fillRect(QRectF(rect.x(), rect.y(), rect.width() * frac, rect.height()), colour)
        if flash > 0:
            glow = QColor(255, 255, 255)
            glow.setAlphaF(0.75 * flash)
            p.fillRect(rect, glow)
        outline = self.controller.cfg["overlay"].get("flat_outline", 1)
        if outline:
            p.setPen(QPen(QColor(8, 10, 14), outline, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            p.setBrush(Qt.NoBrush)
            p.drawRect(rect.adjusted(outline / 2 - 0.5, outline / 2 - 0.5, 0.5 - outline / 2, 0.5 - outline / 2))

    def neon_shape(self, rect):
        key = ("neon", rect.width(), rect.height(), rect.y())
        if key not in self.cache:
            h, x, y, w = rect.height(), rect.x(), rect.y(), rect.width()
            c = min(h * 0.5, 14)
            outer = QPainterPath()
            outer.moveTo(x + c, y)
            outer.lineTo(x + w - c, y)
            outer.lineTo(x + w, y + h / 2)
            outer.lineTo(x + w - c, y + h)
            outer.lineTo(x + c, y + h)
            outer.lineTo(x, y + h / 2)
            outer.closeSubpath()
            self.cache[key] = (outer, c)
        return self.cache[key]

    def paint_neon(self, p, rect, frac, flash, colour):
        """Angled ends, dark track, glowing fill with a slanted front edge and // marks at the ends."""
        p.setRenderHint(QPainter.Antialiasing)
        inset = rect.adjusted(3, 3, -3, -3)
        outer, c = self.neon_shape(rect)
        glow = QColor(colour)
        glow.setAlpha(70)
        p.setPen(QPen(glow, 4))
        p.setBrush(QColor(10, 14, 12, 235))
        p.drawPath(outer)
        p.setPen(QPen(colour, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(outer)
        inner, ci = self.neon_shape(inset)
        if frac > 0:
            fill_w = inset.width() * frac
            slant = min(inset.height(), 12)
            front = QPainterPath()
            front.moveTo(inset.x(), inset.y())
            front.lineTo(inset.x() + fill_w + slant / 2, inset.y())
            front.lineTo(inset.x() + fill_w - slant / 2, inset.y() + inset.height())
            front.lineTo(inset.x(), inset.y() + inset.height())
            front.closeSubpath()
            grad = QLinearGradient(inset.x(), 0, inset.x() + fill_w, 0)
            grad.setColorAt(0, colour.darker(130))
            grad.setColorAt(1, colour.lighter(130))
            p.fillPath(inner.intersected(front), grad)
        if flash > 0:
            white = QColor(255, 255, 255)
            white.setAlphaF(0.7 * flash)
            p.fillPath(inner, white)
        # the "//" marks inside each angled end
        p.setPen(QPen(colour, max(1.5, rect.height() / 9)))
        for sx in (rect.x() + c * 0.55, rect.x() + rect.width() - c * 0.55 - c * 0.5):
            for k in (0, 1):
                x0 = sx + k * c * 0.3
                p.drawLine(QPointF(x0, rect.y() + rect.height() * 0.7), QPointF(x0 + c * 0.25, rect.y() + rect.height() * 0.3))

    def edge_shapes(self, rect):
        """Frame, inner track and hatching for the Edgerunner bar, cached per size."""
        key = ("edge", rect.width(), rect.height(), rect.y())
        if key not in self.cache:
            m = 2.5  # room for the glow
            x, y, w, h = rect.x() + m, rect.y() + m, rect.width() - 2 * m, rect.height() - 2 * m
            c = h * 0.5
            frame = QPainterPath()
            frame.moveTo(x + c, y)
            frame.lineTo(x + w - c, y)
            frame.lineTo(x + w, y + h / 2)
            frame.lineTo(x + w - c, y + h)
            frame.lineTo(x + c, y + h)
            frame.lineTo(x, y + h / 2)
            frame.closeSubpath()
            pad = max(h * 0.2, 2.5)
            ix, iy, iw, ih = x + c * 1.9, y + pad, w - c * 3.8, h - 2 * pad
            s = ih * 0.8  # slant of the right-hand end
            track = QPainterPath()
            track.moveTo(ix, iy)
            track.lineTo(ix + iw, iy)
            track.lineTo(ix + iw - s, iy + ih)
            track.lineTo(ix, iy + ih)
            track.closeSubpath()
            hatch = QPainterPath()
            step = max(ih * 0.7, 4)
            k = ix - ih
            while k < ix + iw:
                hatch.moveTo(k, iy + ih)
                hatch.lineTo(k + ih, iy)
                k += step
            self.cache[key] = (frame, track, hatch, (ix, iy, iw, ih, s), (x, y, w, h, c))
        return self.cache[key]

    def paint_edge(self, p, rect, frac, flash, colour):
        """Edgerunner style, after the Cyberpunk bar: black angled frame with a neon outline and glow,
        // marks at both ends, a hatched dark track and a bright fill with a slanted front edge."""
        p.setRenderHint(QPainter.Antialiasing)
        frame, track, hatch, (ix, iy, iw, ih, s), (x, y, w, h, c) = self.edge_shapes(rect)
        for width, alpha in ((5, 40), (3, 70)):
            glow = QColor(colour)
            glow.setAlpha(alpha)
            p.setPen(QPen(glow, width))
            p.setBrush(Qt.NoBrush)
            p.drawPath(frame)
        p.setPen(QPen(colour, 1.3))
        p.setBrush(QColor(6, 8, 6, 245))
        p.drawPath(frame)
        p.fillPath(track, QColor(26, 34, 31, 240))
        p.save()
        p.setClipPath(track)
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.drawPath(hatch)
        if frac > 0:
            fw = (iw - s) * frac + s * min(frac * 4, 1)
            fill = QPainterPath()
            fill.moveTo(ix, iy)
            fill.lineTo(ix + fw, iy)
            fill.lineTo(ix + fw - s, iy + ih)
            fill.lineTo(ix, iy + ih)
            fill.closeSubpath()
            grad = QLinearGradient(ix, 0, ix + fw, 0)
            grad.setColorAt(0, colour.lighter(115))
            grad.setColorAt(0.75, colour)
            grad.setColorAt(1, colour.darker(135))
            p.fillPath(fill, grad)
            shine = QLinearGradient(0, iy, 0, iy + ih)
            shine.setColorAt(0, QColor(255, 255, 255, 70))
            shine.setColorAt(0.45, QColor(255, 255, 255, 0))
            p.fillPath(fill, shine)
        if flash > 0:
            white = QColor(255, 255, 255)
            white.setAlphaF(0.7 * flash)
            p.fillPath(track, white)
        p.restore()
        p.setPen(QPen(QColor(colour.red(), colour.green(), colour.blue(), 120), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(track)
        # the double // at each end
        p.setPen(QPen(colour, max(1.6, h / 8), Qt.SolidLine, Qt.FlatCap))
        gap = max(c * 0.32, 3)
        for sx in (x + c * 0.75, x + w - c * 0.75 - gap * 1.6):
            for k in (0, 1):
                x0 = sx + k * gap
                p.drawLine(QPointF(x0, y + h * 0.72), QPointF(x0 + h * 0.28, y + h * 0.28))

    def edge_plate(self, p, cd, t, bar):
        """With text inside the bar, the Edgerunner style puts it on a small slanted plate in the middle."""
        txt = self.text_cfg()
        p.setFont(QFont(txt.get("font", "Bahnschrift"), int(txt.get("size", 9)), QFont.Bold))
        label = (cd.label if cd is not None and getattr(cd, "label", "") else self.name)
        status = self.status_text(cd, t)
        text = txt.get("template", "{NAME} {STATUS}").format(
            NAME=label.upper(), name=label, STATUS=status if status[:1].isdigit() else status.upper(), status=status)
        tw = p.fontMetrics().horizontalAdvance(text) + 18
        th = min(bar.height() - 4, p.fontMetrics().height() + 2)
        cx, cy = bar.center().x(), bar.center().y()
        plate = QPainterPath()
        plate.moveTo(cx - tw / 2 + 5, cy - th / 2)
        plate.lineTo(cx + tw / 2, cy - th / 2)
        plate.lineTo(cx + tw / 2 - 5, cy + th / 2)
        plate.lineTo(cx - tw / 2, cy + th / 2)
        plate.closeSubpath()
        p.fillPath(plate, QColor(6, 8, 6, 235))

    def skin(self, which, size):
        sk = self.controller.cfg["overlay"].get("skin", {})
        path = sk.get(which, "")
        key = (which, path, size)
        if key not in self.cache:
            pix = QPixmap(path) if path and os.path.exists(path) else QPixmap()
            self.cache[key] = pix.scaled(size[0], size[1], Qt.IgnoreAspectRatio, Qt.SmoothTransformation) \
                if not pix.isNull() else pix
        return self.cache[key]

    def paint_image(self, p, rect, frac, flash, colour):
        """Your skin: an 'empty' picture of the bar, and optionally a 'full' one. The full picture is
        revealed from left to right inside the fill area as the cooldown recharges. With only the
        empty picture, a colour fill is drawn inside the fill area and the picture goes on top as a frame."""
        sk = self.controller.cfg["overlay"].get("skin", {})
        size = (int(rect.width()), int(rect.height()))
        empty, full = self.skin("empty", size), self.skin("full", size)
        x0, y0, x1, y1 = (v / 100 for v in sk.get("fill_area", [4, 22, 96, 78]))
        area = QRectF(rect.x() + rect.width() * x0, rect.y() + rect.height() * y0,
                      rect.width() * (x1 - x0), rect.height() * (y1 - y0))
        reveal = QRectF(area.x(), area.y(), area.width() * frac, area.height())
        if not full.isNull():
            if not empty.isNull():
                p.drawPixmap(rect.topLeft(), empty)
            p.save()
            p.setClipRect(reveal)
            p.drawPixmap(rect.topLeft(), full)
            p.restore()
        else:
            p.fillRect(area, QColor(20, 24, 28, 230))
            p.fillRect(reveal, colour)
            if not empty.isNull():
                p.drawPixmap(rect.topLeft(), empty)
            else:
                p.setPen(QPen(colour, 1))
                p.drawRect(rect)
        if flash > 0:
            white = QColor(255, 255, 255)
            white.setAlphaF(0.6 * flash)
            p.fillRect(area, white)

    def paint_card(self, p, cd):
        self.background(p)
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.setPen(TEXT)
        name_w = p.fontMetrics().horizontalAdvance(self.name)
        p.drawText(QRectF(14, 6, 150, 20), Qt.AlignVCenter | Qt.AlignLeft, self.name)
        if cd is None:
            return
        # Little on/off tags for resets triggered by another key, e.g. "BD" for Blade Dancer.
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        x = 14 + name_w + 8
        for r in cd.resets:
            if r.key == cd.key:
                continue
            tag = "".join(w[0] for w in r.name.split("(")[0].split() if w[0].isalpha()).upper()[:3] or "R"
            w = p.fontMetrics().horizontalAdvance(tag) + 10
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(READY if r.armed else QColor(60, 66, 80)))
            p.drawRoundedRect(QRectF(x, 10, w, 13), 4, 4)
            p.setPen(QColor(12, 14, 19) if r.armed else MUTED)
            p.drawText(QRectF(x, 10, w, 13), Qt.AlignCenter, tag)
            x += w + 4
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        t = combat.now()
        left = cd.remaining(t)
        since_land = t - cd.landed_at
        flash = max(0.0, 1 - since_land / 0.6)
        if flash > 0:
            status, colour = "LANDED", LANDED
        elif left == 0:
            status, colour = "READY", READY
        else:
            status, colour = f"{left:.1f}s", TEXT
        p.setPen(colour)
        p.drawText(QRectF(self.width() - 100, 6, 86, 20), Qt.AlignVCenter | Qt.AlignRight, status)

        bar = QRectF(14, 31, self.width() - 28, 8)
        track = QPainterPath()
        track.addRoundedRect(bar, 4, 4)
        p.fillPath(track, QColor(38, 43, 54))
        frac = 1 - left / cd.span()
        if frac > 0:
            fill = QPainterPath()
            fill.addRoundedRect(QRectF(bar.x(), bar.y(), bar.width() * frac, bar.height()), 4, 4)
            p.fillPath(fill, READY if left == 0 else QColor(cd.color))
        if flash > 0:
            glow = QColor(LANDED)
            glow.setAlphaF(0.7 * flash)
            p.fillPath(track, glow)
        if cd.cancel_cooldown:
            cleft = cd.cancel_remaining(t)
            if cleft:
                w = bar.width() * cleft / cd.cancel_cooldown
                p.fillRect(QRectF(bar.x(), bar.bottom() + 3, w, 2), QColor("#c084fc"))



class StatusOverlay(Overlay):
    def __init__(self, controller, wid):
        super().__init__(controller, wid, 190, 32)

    def paintEvent(self, e):
        p = QPainter(self)
        self.background(p)
        eng = self.controller.engine
        if not eng.active:
            dot, text = MUTED, "Macros OFF"
        elif eng.game_focused():
            dot, text = READY, "Macros ON"
        else:
            dot, text = QColor("#f59e0b"), "ON - game not focused"
        p.setBrush(dot)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(12, 11, 10, 10))
        p.setPen(TEXT)
        p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        p.drawText(QRectF(30, 0, self.width() - 36, self.height()), Qt.AlignVCenter, text)


class MacrosOverlay(Overlay):
    ROW = 22

    def __init__(self, controller, wid):
        super().__init__(controller, wid, 230, 40)

    def paintEvent(self, e):
        macros = self.controller.engine.macros
        want_h = 34 + self.ROW * max(len(macros), 1)
        if self.height() != want_h:
            self.resize(self.width(), want_h)
            return
        p = QPainter(self)
        self.background(p)
        on = self.controller.engine.active
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(READY if on else MUTED)
        p.drawText(QRectF(14, 6, 200, 20), Qt.AlignVCenter, "MACROS ON" if on else "MACROS OFF")
        p.setFont(QFont("Segoe UI", 9))
        if not macros:
            p.setPen(MUTED)
            p.drawText(QRectF(14, 30, 200, 20), Qt.AlignVCenter, "no macros")
        for i, m in enumerate(macros):
            y = 30 + i * self.ROW
            key = QRectF(14, y + 2, 46, 17)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(38, 43, 54))
            p.drawRoundedRect(key, 4, 4)
            p.setPen(TEXT)
            p.drawText(key, Qt.AlignCenter, m.hotkey.replace("mouse_", "M-").upper())
            p.setPen(LANDED if m.running else (TEXT if on else MUTED))
            p.drawText(QRectF(68, y, self.width() - 80, self.ROW), Qt.AlignVCenter, m.name)


class PartyOverlay(Overlay):
    """You and each friend as HP bars, plus the latest party messages. Styles: cyber (default) or classic."""
    HEADER = 26
    CHAT_ROW = 16
    CHAT_SHOW = 25.0  # seconds a message stays on the overlay

    def __init__(self, controller, wid):
        super().__init__(controller, wid, 400, 70)
        self.cache = {}

    def chat_lines(self):
        n = int(self.controller.cfg["overlay"].get("party_chat_lines", 3))
        if n <= 0:
            return []
        now = time.time()
        recent = [m for m in list(self.controller.engine.party_link.chat) if now - m[0] < self.CHAT_SHOW]
        return recent[-n:]

    def paintEvent(self, e):
        ov = self.controller.cfg["overlay"]
        cyber = ov.get("party_style", "cyber") == "cyber"
        self.bar_h = max(int(ov.get("party_bar", 12)), 3)
        self.info_size = max(int(ov.get("party_info_size", 10)), 7)  # server / region line
        self.ROW = 34 + self.info_size + self.bar_h if cyber else 42 + self.bar_h
        rows = list(self.controller.engine.party)
        chat = self.chat_lines()
        chat_h = (8 + self.CHAT_ROW * len(chat)) if chat else 0
        want = (max(int(ov.get("party_width", 400)), 220),
                self.HEADER + 8 + self.ROW * max(len(rows), 1) + chat_h)
        if (self.width(), self.height()) != want:
            self.resize(*want)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if cyber:
            self.paint_cyber(p, rows)
        else:
            self.paint_classic(p, rows)
        if chat:
            self.paint_chat(p, chat, cyber)

    # -- cyber
    def frame_path(self):
        key = ("frame", self.width(), self.height())
        if key not in self.cache:
            self.cache.clear()
            w, h, c = self.width() - 1, self.height() - 1, 12
            path = QPainterPath()
            path.moveTo(0.5 + c, 0.5)
            path.lineTo(w, 0.5)
            path.lineTo(w, h - c)
            path.lineTo(w - c, h)
            path.lineTo(0.5, h)
            path.lineTo(0.5, 0.5 + c)
            path.closeSubpath()
            self.cache[key] = path
        return self.cache[key]

    def paint_cyber(self, p, rows):
        w = self.width()
        frame = self.frame_path()
        p.fillPath(frame, QColor(8, 11, 16, 232))
        # faint scanlines
        p.setPen(QPen(QColor(45, 226, 230, 9), 1))
        for y in range(2, self.height(), 3):
            p.drawLine(1, y, w - 2, y)
        p.setPen(QPen(QColor(45, 226, 230, 110), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(frame)
        # yellow corner accents
        p.setPen(QPen(CY_YELLOW, 2))
        p.drawLine(QPointF(1, 13), QPointF(13, 1))
        p.drawLine(QPointF(13, 1), QPointF(70, 1))
        p.drawLine(QPointF(w - 2, self.height() - 14), QPointF(w - 14, self.height() - 2))

        pcfg = self.controller.cfg.get("party", {})
        link = self.controller.engine.party_link
        connected = link.status == "connected"
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(CY_YELLOW)
        p.drawText(QRectF(16, 6, 140, 16), Qt.AlignVCenter, "// PARTY.HP")
        if not pcfg.get("enabled"):
            status = "○ OFFLINE"
        elif connected:
            status = "● LINKED"
        else:
            status = "○ " + link.status.upper()
        p.setFont(QFont("Consolas", 7))
        p.setPen(CY_CYAN if connected else MUTED)
        status = p.fontMetrics().elidedText(status, Qt.ElideRight, w - 150)
        p.drawText(QRectF(130, 6, w - 144, 16), Qt.AlignVCenter | Qt.AlignRight, status)
        p.setPen(QPen(QColor(45, 226, 230, 60), 1))
        p.drawLine(QPointF(14, self.HEADER - 1), QPointF(w - 14, self.HEADER - 1))
        if not rows:
            p.setFont(QFont("Consolas", 8))
            p.setPen(MUTED)
            p.drawText(QRectF(16, self.HEADER + 8, w - 32, 20), Qt.AlignVCenter, "> turn on in the Party HP page_")
            return
        pulse = 0.5 + 0.5 * math.sin(time.time() * 6)
        for i, row in enumerate(rows):
            self.paint_cyber_row(p, row, self.HEADER + 6 + i * self.ROW, pulse)

    def paint_cyber_row(self, p, row, y, pulse):
        w = self.width()
        name, frac, online, is_you = row["name"], row["hp"], row["online"], row["you"]
        low = online and frac is not None and frac < 0.5
        if low:
            # Under 50%: the row pulses red so it catches your eye.
            glow = QColor(255, 60, 95)
            glow.setAlphaF(0.10 + 0.20 * pulse)
            p.fillRect(QRectF(6, y - 3, w - 12, self.ROW - 4), glow)
            p.fillRect(QRectF(6, y - 3, 3, self.ROW - 4), CY_RED)
        if not online:
            status, colour = "OFFLINE", MUTED
        elif frac is None:
            status, colour = "??", MUTED
        else:
            status, colour = f"{frac:.0%}", cyber_hp_color(frac)
        # name, then the YOU and PVP tags
        p.setFont(QFont("Bahnschrift", 10, QFont.DemiBold))
        p.setPen(TEXT if online else MUTED)
        room = w - 110
        tags = (40 if is_you else 0) + (60 if online and row.get("combat") else 0)
        label = p.fontMetrics().elidedText(name, Qt.ElideRight, room - tags)
        p.drawText(QRectF(16, y, room, 18), Qt.AlignVCenter, label)
        x = 16 + p.fontMetrics().horizontalAdvance(label) + 8
        p.setFont(QFont("Consolas", 7, QFont.Bold))
        if is_you:
            x = self.tag(p, x, y, "YOU", CY_YELLOW, QColor(8, 11, 16))
        if online and row.get("combat"):
            self.tag(p, x, y, "PVP" + (f" x{row['count']}" if row.get("count") else ""), CY_RED, QColor(255, 255, 255))
        p.setFont(QFont("Consolas", 11, QFont.Bold))
        p.setPen(colour)
        p.drawText(QRectF(w - 96, y, 80, 18), Qt.AlignVCenter | Qt.AlignRight, status)
        # second line: server and region, cyan when they're in your server
        line_h = self.info_size + 8
        if online:
            self.paint_info(p, row, is_you, QRectF(16, y + 19, w - 32, line_h))
        self.paint_cyber_bar(p, QRectF(16, y + 22 + line_h, w - 32, self.bar_h), frac if online else None, colour)

    def paint_info(self, p, row, is_you, area):
        """Server name (bright), region (softer) and a SAME SERVER tag, big enough to read at a glance."""
        p.setFont(QFont("Bahnschrift", self.info_size, QFont.DemiBold))
        fm = p.fontMetrics()
        x = area.x()
        same = row.get("same") and not is_you
        pieces = [(row.get("server") or "server unknown", CY_CYAN if same else QColor(236, 240, 245))]
        if row.get("region"):
            pieces.append(("  ·  " + row["region"], QColor(170, 186, 204)))
        for text, colour in pieces:
            room = area.right() - x - (100 if same else 0)
            if room <= 10:
                break
            text = fm.elidedText(text, Qt.ElideRight, int(room))
            p.setPen(QColor(0, 0, 0, 220))  # shadow so it reads over bright scenery
            p.drawText(QRectF(x + 1, area.y() + 1, room, area.height()), Qt.AlignVCenter, text)
            p.setPen(colour)
            p.drawText(QRectF(x, area.y(), room, area.height()), Qt.AlignVCenter, text)
            x += fm.horizontalAdvance(text)
        if same:
            p.setFont(QFont("Consolas", max(self.info_size - 2, 7), QFont.Bold))
            self.tag(p, x + 8, area.y() + (area.height() - 19) / 2, "SAME SERVER", CY_CYAN, QColor(8, 11, 16))

    def tag(self, p, x, y, text, bg, fg):
        """A small slanted label; returns where the next one goes."""
        tw = p.fontMetrics().horizontalAdvance(text) + 12
        shape = QPainterPath()
        shape.moveTo(x + 4, y + 3)
        shape.lineTo(x + tw, y + 3)
        shape.lineTo(x + tw - 4, y + 16)
        shape.lineTo(x, y + 16)
        shape.closeSubpath()
        p.fillPath(shape, bg)
        p.setPen(fg)
        p.drawText(QRectF(x, y + 3, tw, 13), Qt.AlignCenter, text)
        return x + tw + 6

    def paint_cyber_bar(self, p, bar, frac, colour):
        """Slanted track with 10% segment ticks and a glowing fill."""
        s = min(bar.height(), 10)
        track = QPainterPath()
        track.moveTo(bar.x() + s, bar.y())
        track.lineTo(bar.right(), bar.y())
        track.lineTo(bar.right() - s, bar.bottom())
        track.lineTo(bar.x(), bar.bottom())
        track.closeSubpath()
        p.fillPath(track, QColor(20, 26, 34, 240))
        if frac:
            fill_w = (bar.width() - s) * frac
            fill = QPainterPath()
            fill.moveTo(bar.x() + s, bar.y())
            fill.lineTo(bar.x() + s + fill_w, bar.y())
            fill.lineTo(bar.x() + fill_w, bar.bottom())
            fill.lineTo(bar.x(), bar.bottom())
            fill.closeSubpath()
            glow = QColor(colour)
            glow.setAlpha(80)
            p.setPen(QPen(glow, 4))
            p.setBrush(Qt.NoBrush)
            p.drawPath(fill)
            grad = QLinearGradient(bar.x(), 0, bar.x() + fill_w + s, 0)
            grad.setColorAt(0, colour.darker(140))
            grad.setColorAt(1, colour.lighter(115))
            p.fillPath(fill, grad)
        p.setPen(QPen(QColor(8, 11, 16, 200), 2))
        for k in range(1, 10):
            x = bar.x() + (bar.width() - s) * k / 10
            p.drawLine(QPointF(x + s, bar.y()), QPointF(x, bar.bottom()))
        p.setPen(QPen(QColor(45, 226, 230, 90), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(track)

    # -- messages
    def paint_chat(self, p, chat, cyber):
        w = self.width()
        font = "Consolas" if cyber else "Segoe UI"
        top = self.height() - 6 - self.CHAT_ROW * len(chat)
        p.setPen(QPen(QColor(45, 226, 230, 60) if cyber else QColor(255, 255, 255, 30), 1))
        p.drawLine(QPointF(14, top - 3), QPointF(w - 14, top - 3))
        for i, (_, name, text, mine) in enumerate(chat):
            y = top + i * self.CHAT_ROW
            p.setFont(QFont(font, 8, QFont.Bold))
            who = ("YOU" if mine else name) + ">"
            p.setPen(CY_CYAN if mine else CY_YELLOW)
            nw = p.fontMetrics().horizontalAdvance(who) + 6
            p.drawText(QRectF(16, y, nw, self.CHAT_ROW), Qt.AlignVCenter, who)
            p.setFont(QFont(font, 8))
            p.setPen(TEXT)
            body = p.fontMetrics().elidedText(text, Qt.ElideRight, w - 32 - nw)
            p.drawText(QRectF(16 + nw, y, w - 32 - nw, self.CHAT_ROW), Qt.AlignVCenter, body)

    # -- classic (the v1 look)
    def paint_classic(self, p, rows):
        self.background(p)
        pcfg = self.controller.cfg.get("party", {})
        link = self.controller.engine.party_link
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(READY if link.status == "connected" else MUTED)
        p.drawText(QRectF(14, 6, 120, 16), Qt.AlignVCenter, "PARTY HP")
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(MUTED)
        p.drawText(QRectF(110, 6, self.width() - 124, 16), Qt.AlignVCenter | Qt.AlignRight,
                   link.status if pcfg.get("enabled") else "off")
        if not rows:
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(14, self.HEADER + 8, self.width() - 28, 20), Qt.AlignVCenter,
                       "turn on in the Party HP page")
            return
        pulse = 0.5 + 0.5 * math.sin(time.time() * 6)
        for i, row in enumerate(rows):
            name, frac, online, is_you = row["name"], row["hp"], row["online"], row["you"]
            y = self.HEADER + 4 + i * self.ROW
            low = online and frac is not None and frac < 0.5
            if low:
                # Under 50%: the whole row pulses red so it catches your eye.
                glow = QColor(239, 68, 68)
                glow.setAlphaF(0.12 + 0.22 * pulse)
                path = QPainterPath()
                path.addRoundedRect(QRectF(6, y - 2, self.width() - 12, self.ROW - 4), 6, 6)
                p.fillPath(path, glow)
            p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            p.setPen(TEXT if online else MUTED)
            label = name + ("  (you)" if is_you else "")
            room = self.width() - 100 - (60 if online and row.get("combat") else 0)
            label = p.fontMetrics().elidedText(label, Qt.ElideRight, room)
            p.drawText(QRectF(14, y, room, 18), Qt.AlignVCenter, label)
            if online and row.get("combat"):
                # In PvP combat: a red tag with how many players are on them.
                x = 14 + p.fontMetrics().horizontalAdvance(label) + 8
                tag = "PVP" + (f" x{row['count']}" if row.get("count") else "")
                p.setFont(QFont("Segoe UI", 7, QFont.Bold))
                tw = p.fontMetrics().horizontalAdvance(tag) + 10
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(220, 38, 38))
                p.drawRoundedRect(QRectF(x, y + 3, tw, 13), 4, 4)
                p.setPen(QColor(255, 255, 255))
                p.drawText(QRectF(x, y + 3, tw, 13), Qt.AlignCenter, tag)
            if not online:
                status, colour = "offline", MUTED
            elif frac is None:
                status, colour = "?", MUTED
            else:
                status, colour = f"{frac:.0%}", hp_color(frac)
            p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            p.setPen(colour)
            p.drawText(QRectF(self.width() - 86, y, 72, 18), Qt.AlignVCenter | Qt.AlignRight, status)
            # Second line: server and region, green when they're in your server.
            p.setFont(QFont("Segoe UI", 8))
            if online:
                parts = [row.get("server") or "server unknown"]
                if row.get("region"):
                    parts.append(row["region"])
                text = "  ·  ".join(parts)
                if row.get("same") and not is_you:
                    text += "  ·  same server"
                p.setPen(READY if row.get("same") else MUTED)
                text = p.fontMetrics().elidedText(text, Qt.ElideRight, self.width() - 28)
                p.drawText(QRectF(14, y + 17, self.width() - 28, 14), Qt.AlignVCenter, text)
            bar = QRectF(14, y + 34, self.width() - 28, self.bar_h)
            if self.controller.cfg["overlay"].get("bar_style", "flat") == "flat":
                # Same look as the flat Parry / Dodge lines: square, solid, thin dark outline.
                p.fillRect(bar, QColor(30, 34, 42))
                if online and frac:
                    p.fillRect(QRectF(bar.x(), bar.y(), bar.width() * frac, bar.height()), colour)
                p.setPen(QPen(QColor(8, 10, 14), 1))
                p.setBrush(Qt.NoBrush)
                p.drawRect(bar)
            else:
                track = QPainterPath()
                track.addRoundedRect(bar, 4, 4)
                p.fillPath(track, QColor(38, 43, 54))
                if online and frac:
                    fill = QPainterPath()
                    fill.addRoundedRect(QRectF(bar.x(), bar.y(), bar.width() * frac, bar.height()), 4, 4)
                    p.fillPath(fill, colour)


class BuilderOverlay(Overlay):
    """BUILDER 101: the talents of your build you still need, top-right of the screen."""
    ROW = 18

    def __init__(self, controller, wid):
        super().__init__(controller, wid, 260, 80)

    def paintEvent(self, e):
        b = self.controller.cfg.get("builder", {})
        talents = b.get("talents", [])
        have = set(b.get("obtained", []))
        todo = [t for t in talents if t not in have]
        seen = set(self.controller.engine.builder_seen)
        shown = todo[:int(b.get("max_rows", 12))]
        want_h = 50 + self.ROW * max(len(shown), 1) + (16 if len(todo) > len(shown) else 0)
        if self.height() != want_h:
            self.resize(self.width(), want_h)
            return
        p = QPainter(self)
        self.background(p)
        p.setPen(QColor("#c084fc"))
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(QRectF(12, 6, 140, 16), Qt.AlignVCenter, "BUILDER 101")
        p.setPen(MUTED)
        p.drawText(QRectF(120, 6, self.width() - 132, 16), Qt.AlignVCenter | Qt.AlignRight,
                   f"{len(have)}/{len(talents)}" if talents else "no build")
        p.setFont(QFont("Bahnschrift", 9, QFont.DemiBold))
        p.setPen(TEXT)
        name = p.fontMetrics().elidedText(b.get("name") or "paste a build in Builder", Qt.ElideRight, self.width() - 24)
        p.drawText(QRectF(12, 22, self.width() - 24, 18), Qt.AlignVCenter, name)
        p.setFont(QFont("Bahnschrift", 9))
        for i, t in enumerate(shown):
            y = 44 + i * self.ROW
            on_screen = t in seen
            p.setPen(LANDED if on_screen else QColor(200, 208, 220))
            p.drawText(QRectF(12, y, self.width() - 24, self.ROW), Qt.AlignVCenter,
                       ("▶ " if on_screen else "· ") + t)
        if len(todo) > len(shown):
            p.setPen(MUTED)
            p.drawText(QRectF(12, 44 + len(shown) * self.ROW, self.width() - 24, 16), Qt.AlignVCenter,
                       f"+{len(todo) - len(shown)} more")


class CardHighlight(QWidget):
    """A glowing frame around a talent card: yellow when it's in your build, red when it isn't.
    Clicks go straight through."""
    TAG = 26   # room above the card for the label

    def __init__(self, talent, kind="in"):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.talent = talent
        self.kind = kind

    def place(self, rect):
        """rect = the card's frame, in screen coordinates."""
        x, y, w, h = rect
        self.setGeometry(x - 4, y - self.TAG, w + 8, h + self.TAG + 4)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pulse = 0.55 + 0.45 * math.sin(time.time() * 5)
        frame = QRectF(3, self.TAG, self.width() - 6, self.height() - self.TAG - 3)
        out = self.kind == "out"
        colour = CY_RED if out else CY_YELLOW
        if out:
            p.fillRect(frame, QColor(255, 60, 95, 38))  # a red wash over cards to get rid of
        for width, alpha in ((9, 40), (5, 90)):
            glow = QColor(colour)
            glow.setAlphaF(alpha / 255 * ((0.6 + 0.4 * pulse) if not out else 0.8))
            p.setPen(QPen(glow, width))
            p.drawRoundedRect(frame, 6, 6)
        p.setPen(QPen(colour, 2))
        p.drawRoundedRect(frame, 6, 6)
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        text = "NOT IN BUILD" if out else "IN YOUR BUILD"
        tw = p.fontMetrics().horizontalAdvance(text) + 18
        tag = QPainterPath()
        x0 = (self.width() - tw) / 2
        tag.moveTo(x0 + 6, 2)
        tag.lineTo(x0 + tw, 2)
        tag.lineTo(x0 + tw - 6, 22)
        tag.lineTo(x0, 22)
        tag.closeSubpath()
        p.fillPath(tag, colour)
        p.setPen(QColor(255, 255, 255) if out else QColor(8, 11, 16))
        p.drawText(QRectF(x0, 2, tw, 20), Qt.AlignCenter, text)


def make_overlay(controller, wid):
    if wid.startswith("cooldown:"):
        return CooldownOverlay(controller, wid)
    if wid == "status":
        return StatusOverlay(controller, wid)
    if wid == "macros":
        return MacrosOverlay(controller, wid)
    if wid == "party":
        return PartyOverlay(controller, wid)
    if wid == "builder":
        return BuilderOverlay(controller, wid)
    return None
