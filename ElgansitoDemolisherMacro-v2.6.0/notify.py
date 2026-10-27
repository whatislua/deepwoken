"""Toast notifications in the top-right corner of the screen, with your own sound and picture."""
import math
import os
import struct
import tempfile
import wave

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

import audio

ACCENT = {"builder": "#c084fc", "party": "#2de2e6", "macro": "#f3e600", "warn": "#ff3c5f", "info": "#2de2e6",
          "chat": "#f3e600"}


def default_chime():
    """A short two-note chime, made on the fly (used when you haven't picked a sound file)."""
    path = os.path.join(tempfile.gettempdir(), "elgansito_chime.wav")
    if os.path.exists(path):
        return path
    rate = 44100
    frames = bytearray()
    for freq, ms in ((880, 90), (1320, 160)):
        n = rate * ms // 1000
        for i in range(n):
            t = i / rate
            v = 0.35 * 32767 * math.exp(-t * 14) * math.sin(2 * math.pi * freq * t)
            frames += struct.pack("<h", int(v))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


class Toast(QWidget):
    W, H = 340, 74

    def __init__(self, title, text, kind, image, seconds, on_done):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.title, self.text = title, text
        self.accent = QColor(ACCENT.get(kind, ACCENT["info"]))
        self.pix = QPixmap(image) if image and os.path.exists(image) else QPixmap()
        if not self.pix.isNull():
            self.pix = self.pix.scaled(54, 54, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.setFixedSize(self.W, self.H)
        self.on_done = on_done
        self.life = 0
        self.total = int(seconds * 1000)
        self.setWindowOpacity(0.0)
        self.timer = QTimer(self, interval=30, timeout=self.step)
        self.timer.start()

    def step(self):
        self.life += 30
        fade = 220
        if self.life < fade:
            self.setWindowOpacity(self.life / fade)
        elif self.life > self.total - fade:
            self.setWindowOpacity(max(0.0, (self.total - self.life) / fade))
        else:
            self.setWindowOpacity(1.0)
        if self.life >= self.total:
            self.timer.stop()
            self.close()
            self.on_done(self)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.moveTo(r.left(), r.top())
        path.lineTo(r.right() - 14, r.top())
        path.lineTo(r.right(), r.top() + 14)
        path.lineTo(r.right(), r.bottom())
        path.lineTo(r.left(), r.bottom())
        path.closeSubpath()
        p.fillPath(path, QColor(9, 13, 18, 238))
        p.setPen(QPen(self.accent, 1.2))
        p.drawPath(path)
        p.fillRect(QRectF(0, 0, 3, self.height()), self.accent)
        x = 14
        if not self.pix.isNull():
            p.drawPixmap(x, 10, self.pix, 0, 0, 54, 54)
            x += 64
        p.setPen(self.accent)
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(QRectF(x, 9, self.width() - x - 18, 16), Qt.AlignVCenter, self.title.upper())
        p.setPen(QColor(236, 240, 245))
        p.setFont(QFont("Bahnschrift", 11, QFont.DemiBold))
        body = QFontMetrics(p.font()).elidedText(self.text, Qt.ElideRight, (self.width() - x - 14) * 2 - 20)
        p.drawText(QRectF(x, 26, self.width() - x - 14, 42), Qt.TextWordWrap | Qt.AlignTop, body)


class Notifier:
    def __init__(self, controller):
        self.c = controller
        self.toasts = []

    def show(self, title, text, kind="info"):
        cfg = self.c.cfg.get("notify", {})
        if not cfg.get("enabled", True):
            return
        t = Toast(title, text, kind, cfg.get("image", ""), float(cfg.get("seconds", 4)), self._gone)
        self.toasts.append(t)
        self._place()
        t.show()
        if cfg.get("sound_on", True):
            path = cfg.get("sound", "") or default_chime()
            if not audio.play_effect(path, int(cfg.get("volume", 70))):
                audio.play_effect(default_chime(), int(cfg.get("volume", 70)))

    def _gone(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
            toast.deleteLater()
        self._place()

    def _place(self):
        screen = QApplication.primaryScreen().availableGeometry()
        y = screen.top() + 16
        for t in self.toasts[-5:]:
            t.move(screen.right() - t.width() - 16, y)
            y += t.height() + 8
