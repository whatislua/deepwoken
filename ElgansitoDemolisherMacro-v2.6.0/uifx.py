"""Interface touches: click sound, button press animation, page fade, and the pictures
(app picture in the sidebar, Deepwoken banner on the Roblox page)."""
import io
import math
import os
import struct
import tempfile
import wave
import winsound

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QObject, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QAbstractButton, QGraphicsOpacityEffect, QWidget

import config


def asset(name):
    return config.resolve(os.path.join("assets", name))


# ---- click sound ---------------------------------------------------------------

def click_wav(volume):
    """A short soft "tick": a quick high tone that dies away in ~30 ms."""
    rate, ms = 44100, 32
    n = rate * ms // 1000
    amp = 32767 * max(0.0, min(volume, 100)) / 100 * 0.55
    frames = bytearray()
    for i in range(n):
        t = i / rate
        env = math.exp(-t * 180)
        v = amp * env * (0.7 * math.sin(2 * math.pi * 2100 * t) + 0.3 * math.sin(2 * math.pi * 3400 * t))
        frames += struct.pack("<h", int(v))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class ClickSound:
    def __init__(self):
        self.path = os.path.join(tempfile.gettempdir(), "elgansito_click.wav")
        self.volume = None

    def play(self, volume):
        if volume != self.volume:
            with open(self.path, "wb") as f:
                f.write(click_wav(volume))
            self.volume = volume
        # Async, so a click never waits on the sound.
        winsound.PlaySound(self.path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


class ClickFx(QObject):
    """App-wide: every button press plays the click sound and gets a quick fade-back animation."""

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.sound = ClickSound()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.MouseButtonPress and isinstance(obj, QAbstractButton) and obj.isEnabled():
            ui = self.c.cfg.get("ui", {})
            if ui.get("click_sound", True):
                try:
                    self.sound.play(int(ui.get("volume", 60)))
                except Exception:
                    pass
            if ui.get("animations", True):
                pulse(obj)
        return False


def _fade(widget, start, end, ms):
    if widget.graphicsEffect() is not None:
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QAbstractAnimation.DeleteWhenStopped)


def pulse(button):
    _fade(button, 0.45, 1.0, 260)


def fade_in(page):
    _fade(page, 0.0, 1.0, 220)


# ---- pictures --------------------------------------------------------------------

def rounded(pixmap, w, h, radius):
    """`pixmap` scaled to cover w x h, cropped to the middle, with rounded corners."""
    out = QPixmap(w, h)
    out.fill(Qt.transparent)
    if pixmap.isNull():
        return out
    scaled = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x, y = (scaled.width() - w) // 2, (scaled.height() - h) // 2
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, scaled, x, y, w, h)
    p.end()
    return out


class Banner(QWidget):
    """The Deepwoken artwork across the top of the Roblox page, cropped to fit its width."""

    def __init__(self, height=210):
        super().__init__()
        self.art = QPixmap(asset("banner.png"))
        self.setFixedHeight(height if not self.art.isNull() else 0)

    def paintEvent(self, e):
        if self.art.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(0, 0, rounded(self.art, self.width(), self.height(), 12))
        # Darken the bottom so the title reads on any part of the art.
        shade = QLinearGradient(0, self.height() * 0.45, 0, self.height())
        shade.setColorAt(0, QColor(10, 12, 18, 0))
        shade.setColorAt(1, QColor(10, 12, 18, 210))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)
        p.fillPath(path, shade)
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", 20, QFont.Bold))
        p.drawText(QRectF(20, self.height() - 58, self.width() - 40, 34), Qt.AlignLeft | Qt.AlignVCenter, "DEEPWOKEN")
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(205, 210, 225))
        p.drawText(QRectF(20, self.height() - 28, self.width() - 40, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   "Launch it below - macros switch on by themselves once you're in.")
