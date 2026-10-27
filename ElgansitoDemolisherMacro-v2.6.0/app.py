"""Elgansito Demolisher Macro control panel.

Run this file (or run.bat). Everything you change here saves to config.json
straight away and takes effect immediately.
"""
import copy
import ctypes
import json
import os
import re
import sys
import time

# Work in real screen pixels so Qt, screen capture and clicks all agree.
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import cv2
from PySide6.QtCore import QMimeData, QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QDrag, QFont, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QSizeGrip, QSlider, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

import combat
import config
import detect
import engine as engine_mod
import fastflags
import overlays
import party
import sendinput
import servername
import audio
import builder
import notify
import uifx
import voice

STYLE = """
* { font-family: "Bahnschrift", "Segoe UI"; font-size: 10pt; color: #c9d3dc; }
QMainWindow { background: #0a0e13; }
#Body { background: transparent; }
#TitleBar { background: #070a0e; border-bottom: 1px solid #16232b; }
#Sidebar { background: rgba(8, 12, 17, 235); border-right: 1px solid #16232b; }
#Brand { background: #f3e600; color: #0a0e13; font-weight: 700; font-size: 11pt; padding: 0 18px; }
#NetLink { color: #5f7380; font-family: "Consolas"; font-size: 9pt; padding-left: 14px; }
#AppTitle { font-size: 11pt; font-weight: 600; }
#PageKicker { color: #ff3c5f; font-family: "Consolas"; font-size: 9pt; }
#PageTitle { font-size: 22pt; font-weight: 700; color: #ffffff; }
#PageMeta { color: #5f7380; font-family: "Consolas"; font-size: 8pt; }
#Hint, .hint { color: #6b808c; }
QLabel { background: transparent; }
QPushButton { background: rgba(12, 18, 24, 220); border: 1px solid #1f3540; border-radius: 0; padding: 6px 12px; color: #c9d3dc; }
QPushButton:hover { border-color: #2de2e6; color: #ffffff; }
QPushButton:pressed { background: #0f1c24; }
QPushButton:disabled { color: #3d4c55; border-color: #16232b; }
QPushButton#Primary { background: #f3e600; border: none; color: #0a0e13; font-weight: 700; }
QPushButton#Primary:hover { background: #fff35c; }
QPushButton#Danger { background: transparent; border: 1px solid #5c1f2c; color: #ff3c5f; }
QPushButton#Danger:hover { border-color: #ff3c5f; }
QPushButton#Nav { text-align: left; padding: 8px 14px; border: none; border-left: 3px solid transparent;
                  background: transparent; color: #6b808c; font-weight: 600; font-family: "Consolas"; }
QPushButton#Nav:hover { color: #ffffff; border-left: 3px solid #2de2e6; background: rgba(45, 226, 230, 18); }
QPushButton#Nav:checked { color: #0a0e13; background: #f3e600; border-left: 3px solid #f3e600; }
QPushButton#Dashed { border: 1px dashed #2a434f; color: #6b808c; font-family: "Consolas"; font-size: 9pt; }
QPushButton#Dashed:hover { border-color: #2de2e6; color: #2de2e6; }
QPushButton#TitleBtn { background: transparent; border: none; padding: 4px 14px; font-size: 11pt; }
QPushButton#TitleBtn:hover { background: #16232b; }
QPushButton#CloseBtn { background: transparent; border: none; padding: 4px 14px; font-size: 11pt; }
QPushButton#CloseBtn:hover { background: #c42b1c; }
QPushButton#Toggle { font-size: 13pt; font-weight: 700; padding: 14px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit, QListWidget {
    background: rgba(9, 14, 19, 230); border: 1px solid #1b2a33; border-radius: 0; padding: 5px 7px; color: #c9d3dc; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #2de2e6; }
QComboBox#ProfileBox { border: 1px solid #2de2e6; color: #2de2e6; font-family: "Consolas"; font-weight: 700; padding: 7px 9px; }
QComboBox QAbstractItemView { background: #0c1218; selection-background-color: #163039; border: 1px solid #1f3540; }
QListWidget { padding: 4px; outline: 0; }
*:focus { outline: none; }
QPushButton:focus { outline: none; }
#SideTitle { font-size: 11pt; font-weight: 700; color: #ffffff; }
#SideTag { color: #2de2e6; font-family: "Consolas"; font-size: 8pt; }
#SideCaption { color: #5f7380; font-family: "Consolas"; font-size: 8pt; }
#AutoSave { color: #2de2e6; font-family: "Consolas"; font-size: 8pt; }
QListWidget::item { padding: 8px; }
QListWidget::item:selected { background: #163039; color: #ffffff; }
QGroupBox { border: 1px solid #1b2a33; border-radius: 0; margin-top: 16px; padding: 12px 10px 10px 10px;
            background: rgba(11, 16, 22, 215); font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #2de2e6; font-family: "Consolas"; }
QGroupBox::indicator, QCheckBox::indicator { width: 15px; height: 15px; }
QCheckBox::indicator { border: 1px solid #2a434f; background: #0a0f14; }
QCheckBox::indicator:checked, QGroupBox::indicator:checked { background: #f3e600; border: 1px solid #f3e600; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #1f3540; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #2de2e6; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QSlider::groove:horizontal { height: 3px; background: #1f3540; }
QSlider::handle:horizontal { background: #f3e600; width: 12px; margin: -6px 0; }
QTableWidget { gridline-color: #16232b; }
QHeaderView::section { background: #0c1218; border: none; padding: 6px; color: #2de2e6; font-family: "Consolas"; }
#Card { background: rgba(11, 16, 22, 220); border: 1px solid #1b2a33; }
#Card:hover { border-color: #2de2e6; }
#StepRow { background: rgba(11, 16, 22, 220); border: 1px solid #1b2a33; }
#StatusBanner { background: #f3e600; }
#StatusBanner[armed="false"] { background: rgba(11, 16, 22, 230); border: 1px solid #ff3c5f; }
#BannerKicker { color: #0a0e13; font-family: "Consolas"; font-size: 9pt; font-weight: 700; }
#BannerTitle { color: #0a0e13; font-size: 24pt; font-weight: 700; }
#BannerMeta { color: #0a0e13; font-family: "Consolas"; font-size: 8pt; }
#BannerKey { color: #0a0e13; border: 2px solid #0a0e13; font-family: "Consolas"; font-size: 12pt; font-weight: 700; padding: 8px 12px; }
#StatusBanner[armed="false"] #BannerKicker, #StatusBanner[armed="false"] #BannerTitle,
#StatusBanner[armed="false"] #BannerMeta { color: #ff3c5f; }
#StatusBanner[armed="false"] #BannerKey { color: #ff3c5f; border-color: #ff3c5f; }
#InfoCard { background: rgba(11, 16, 22, 225); border: 1px solid #1b2a33; border-left: 2px solid #1f3540; }
#InfoLabel { color: #5f7380; font-family: "Consolas"; font-size: 8pt; }
#InfoValue { color: #ffffff; font-size: 12pt; font-weight: 600; }
#LogPanel { background: rgba(9, 13, 18, 230); border: 1px solid #1b2a33; }
#LogTitle { color: #2de2e6; font-family: "Consolas"; font-weight: 700; }
#LogMeta { color: #5f7380; font-family: "Consolas"; font-size: 8pt; }
QTextEdit#Log { background: transparent; border: none; font-family: "Consolas"; font-size: 9pt; }
#Pfp { border: 1px solid #2de2e6; background: #0c1218; color: #5f7380; font-family: "Consolas"; font-size: 8pt; }
"""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "item"


def nice_key(name):
    if not name:
        return "not set"
    names = {"mouse_left": "Left mouse", "mouse_right": "Right mouse", "mouse_middle": "Middle mouse",
             "mouse_x1": "Mouse side 1", "mouse_x2": "Mouse side 2"}
    return names.get(name, name.upper() if len(name) == 1 else name.replace("_", " ").title())


def to_pixmap(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy())


def hint(text):
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label


def spin(value, lo, hi, on_change, suffix="", step=1):
    box = QSpinBox()
    box.setRange(lo, hi)
    box.setSingleStep(step)
    box.setValue(int(value))
    box.setSuffix(suffix)
    box.valueChanged.connect(on_change)
    return box


def combo(options, current, on_change, editable=False):
    """options: list of values, or dict value -> label."""
    box = QComboBox()
    box.setEditable(editable)
    items = options.items() if isinstance(options, dict) else [(o, o) for o in options]
    for value, label in items:
        box.addItem(label, value)
    idx = box.findData(current)
    if idx >= 0:
        box.setCurrentIndex(idx)
    elif editable:
        box.setEditText(str(current))
    if editable:
        box.currentTextChanged.connect(lambda text: on_change(text.strip().lower()))
    else:
        box.currentIndexChanged.connect(lambda _: on_change(box.currentData()))
    return box


def row(*widgets, stretch=True):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    for item in widgets:
        if isinstance(item, QLabel):
            item.setWordWrap(False)
        lay.addWidget(item)
    if stretch:
        lay.addStretch(1)
    return w


# ---- small reusable controls -----------------------------------------------

class KeyButton(QPushButton):
    """Click, then press any key or mouse button to set it."""

    def __init__(self, controller, value, on_change):
        super().__init__(nice_key(value))
        self.controller = controller
        self.value = value
        self.on_change = on_change
        self.setMinimumWidth(130)
        self.setToolTip("Click, then press a key or mouse button. Esc cancels, right-click clears.")
        self.clicked.connect(self.start)
        self.timer = QTimer(self, interval=30, timeout=self.poll)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton and not self.timer.isActive():
            self.value = ""
            self.on_change("")
            self.setText(nice_key(""))
            return
        super().mousePressEvent(e)

    def start(self):
        eng = self.controller.engine
        eng.captured_key = None
        eng.capturing = True
        self.setText("press a key...")
        self.timer.start()

    def poll(self):
        eng = self.controller.engine
        if eng.captured_key is None:
            return
        self.timer.stop()
        key, eng.captured_key = eng.captured_key, None
        if key != "esc":
            self.value = key
            self.on_change(key)
        self.setText(nice_key(self.value))


class ColorButton(QPushButton):
    def __init__(self, rgb, on_change):
        super().__init__()
        self.on_change = on_change
        self.setFixedWidth(90)
        self.clicked.connect(self.choose)
        self.set_rgb(rgb, notify=False)

    def set_rgb(self, rgb, notify=True):
        self.rgb = list(rgb)
        r, g, b = self.rgb
        text = "#000" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "#fff"
        self.setText(f"{r},{g},{b}")
        self.setStyleSheet(f"background: rgb({r},{g},{b}); color: {text}; border: 1px solid #2e3445;")
        if notify:
            self.on_change(self.rgb)

    def choose(self):
        c = QColorDialog.getColor(QColor(*self.rgb), self, "Pick colour")
        if c.isValid():
            self.set_rgb([c.red(), c.green(), c.blue()])


class HexColorButton(ColorButton):
    """Same as ColorButton but stores '#rrggbb'."""

    def __init__(self, hex_colour, on_change):
        c = QColor(hex_colour)
        super().__init__([c.red(), c.green(), c.blue()], lambda rgb: on_change(QColor(*rgb).name()))


# ---- screen picker -----------------------------------------------------------

class ScreenPicker(QWidget):
    """Full-screen frozen screenshot of one monitor: drag a box to pick an area, or click to pick a colour.

    The screenshot is in real screen pixels, but with two monitors or Windows scaling (2K at 125%,
    150%...) Qt's window may not be the same size in pixels. So the picture is drawn scaled to fill
    the window and every mouse position is converted back to screenshot pixels.
    """

    def __init__(self, image, origin, mode, callback, screen=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.image = image
        self.pixmap = to_pixmap(image)
        self.origin = origin
        self.mode = mode
        self.callback = callback
        self.start = self.end = None
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.mouse = QPoint(0, 0)
        if screen is not None:
            self.setGeometry(screen.geometry())
        else:
            self.setGeometry(origin[0], origin[1], self.pixmap.width(), self.pixmap.height())

    def show_on(self, screen):
        self.winId()  # create the native window so it can be moved to the right monitor
        if screen is not None and self.windowHandle():
            self.windowHandle().setScreen(screen)
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.activateWindow()
        self.setFocus()

    # widget <-> screenshot pixels
    def scale(self):
        return self.pixmap.width() / max(self.width(), 1), self.pixmap.height() / max(self.height(), 1)

    def to_image(self, p):
        sx, sy = self.scale()
        x = min(max(int(p.x() * sx), 0), self.image.shape[1] - 1)
        y = min(max(int(p.y() * sy), 0), self.image.shape[0] - 1)
        return x, y

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.finish(None)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.finish(None)
            return
        self.start = self.end = e.position().toPoint()

    def mouseMoveEvent(self, e):
        self.mouse = e.position().toPoint()
        if self.start is not None:
            self.end = self.mouse
        self.update()

    def mouseReleaseEvent(self, e):
        if self.start is None:
            return
        p = e.position().toPoint()
        ox, oy = self.origin
        if self.mode == "area":
            x0, y0 = self.to_image(QRect(self.start, p).normalized().topLeft())
            x1, y1 = self.to_image(QRect(self.start, p).normalized().bottomRight())
            if x1 - x0 >= 4 and y1 - y0 >= 4:
                self.finish({"region": [x0 + ox, y0 + oy, x1 - x0, y1 - y0]})
            else:
                self.start = None
        else:
            x, y = self.to_image(p)
            b, g, r = (int(v) for v in self.image[y, x])
            self.finish({"point": [x + ox, y + oy], "color": [r, g, b]})

    def finish(self, result):
        self.close()
        self.callback(result, self.image, self.origin)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(self.rect(), self.pixmap)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))
        if self.mode == "area" and self.start is not None:
            rect = QRect(self.start, self.end).normalized()
            sx, sy = self.scale()
            src = QRectF(rect.x() * sx, rect.y() * sy, rect.width() * sx, rect.height() * sy)
            p.drawPixmap(QRectF(rect), self.pixmap, src)
            p.setPen(QPen(QColor("#3b82f6"), 2))
            p.drawRect(rect)
            p.setPen(Qt.white)
            p.drawText(rect.bottomLeft() + QPoint(0, 16), f"{int(src.width())} x {int(src.height())} px")
        if self.mode == "point":
            self.draw_magnifier(p)
        text = ("Drag a box around the area.  Esc / right-click to cancel." if self.mode == "area"
                else "Click the colour you want.  Esc / right-click to cancel.")
        p.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
        box = QRectF(self.width() / 2 - 300, 24, 600, 40)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 17, 21, 230))
        p.drawRoundedRect(box, 10, 10)
        p.setPen(Qt.white)
        p.drawText(box, Qt.AlignCenter, text)

    def draw_magnifier(self, p):
        m = self.mouse
        x, y = self.to_image(m)
        src = QRect(x - 7, y - 7, 15, 15)
        dest = QRect(m.x() + 20, m.y() + 20, 150, 150)
        if dest.right() > self.width():
            dest.moveRight(m.x() - 20)
        if dest.bottom() > self.height():
            dest.moveBottom(m.y() - 20)
        p.drawPixmap(dest, self.pixmap, src)
        p.setPen(QPen(QColor("#3b82f6"), 2))
        p.drawRect(dest)
        cell = dest.width() / 15
        p.setPen(QPen(Qt.white, 1))
        p.drawRect(QRectF(dest.x() + 7 * cell, dest.y() + 7 * cell, cell, cell))
        b, g, r = (int(v) for v in self.image[y, x])
        p.fillRect(QRect(dest.x(), dest.bottom() + 4, dest.width(), 22), QColor(15, 17, 21, 230))
        p.drawText(QRect(dest.x(), dest.bottom() + 4, dest.width(), 22), Qt.AlignCenter, f"rgb {r}, {g}, {b}")


def game_monitor(sct, title, fallback_index):
    """The mss monitor the game window is on (else the one under the mouse, else the setting)."""
    monitors = sct.monitors[1:]
    point = None
    if title:
        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if hwnd and not ctypes.windll.user32.IsIconic(hwnd):
            from ctypes import wintypes
            r = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
            point = ((r.left + r.right) // 2, (r.top + r.bottom) // 2)
    if point is None:
        point = sendinput.cursor_pos()
    for m in monitors:
        if m["left"] <= point[0] < m["left"] + m["width"] and m["top"] <= point[1] < m["top"] + m["height"]:
            return {k: m[k] for k in ("left", "top", "width", "height")}
    return detect.monitor_box(sct, fallback_index)


def qt_screen_for(box):
    """The Qt screen showing that monitor (matched by position, allowing for Windows scaling)."""
    best, best_d = None, None
    for s in QApplication.screens():
        g, dpr = s.geometry(), s.devicePixelRatio()
        # Qt may report the screen's position in real pixels or in scaled ones; accept either.
        d = min(abs(g.x() * dpr - box["left"]) + abs(g.y() * dpr - box["top"]),
                abs(g.x() - box["left"]) + abs(g.y() - box["top"]))
        if best is None or d < best_d:
            best, best_d = s, d
    return best


# ---- detector editor (shared by cooldown landing + screen rules) -----------

class DetectorEditor(QWidget):
    def __init__(self, controller, spec, types, on_change, snapshot_name=None):
        super().__init__()
        self.c = controller
        self.spec = spec
        self.on_change = on_change
        self.snapshot_name = snapshot_name
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(Qt.AlignRight)

        self.type_box = combo({t: detect.TYPES[t] for t in types}, spec["type"], self.set_type)
        form.addRow("Look for", self.type_box)

        self.region_spins = []
        region = spec.get("region") or [0, 0, 100, 100]
        for i in range(4):
            self.region_spins.append(spin(region[i], 0 if i < 2 else 1, 20000, lambda v, i=i: self.set_region(i, v)))
            self.region_spins[i].setFixedWidth(84)
        self.pick_area_btn = QPushButton("Pick area")
        self.pick_area_btn.clicked.connect(lambda: self.pick("area"))
        self.region_row = row(*self.region_spins, self.pick_area_btn)
        form.addRow("Area (x, y, w, h)", self.region_row)

        self.color_btn = ColorButton(spec.get("color", [255, 255, 255]), lambda rgb: self.set("color", rgb))
        self.pick_color_btn = QPushButton("Pick colour")
        self.pick_color_btn.clicked.connect(lambda: self.pick("point"))
        self.tol = spin(spec.get("tolerance", 30), 0, 255, lambda v: self.set("tolerance", v))
        self.color_row = row(self.color_btn, self.pick_color_btn, QLabel("tolerance"), self.tol)
        form.addRow("Colour", self.color_row)

        self.frac = QDoubleSpinBox()
        self.frac.setRange(0.1, 100)
        self.frac.setDecimals(1)
        self.frac.setSingleStep(0.5)
        self.frac.setSuffix(" %")
        self.frac.setValue(spec.get("min_fraction", 0.04) * 100)
        self.frac.valueChanged.connect(lambda v: self.set("min_fraction", round(v / 100, 4)))
        self.frac_row = row(self.frac, hint("of the area must be that colour"))
        form.addRow("Needs", self.frac_row)

        self.point_lbl = QLabel()
        self.point_row = row(self.point_lbl, hint("set by Pick colour"))
        form.addRow("Pixel", self.point_row)

        self.tpl_lbl = QLabel()
        self.capture_btn = QPushButton("Capture picture")
        self.capture_btn.setToolTip("Drag a box around the thing to find. The search area is set a bit bigger.")
        self.capture_btn.clicked.connect(lambda: self.pick("area", capture=True))
        self.tpl_row = row(self.tpl_lbl, self.capture_btn)
        form.addRow("Picture", self.tpl_row)
        self.thr = QDoubleSpinBox()
        self.thr.setRange(0.3, 1.0)
        self.thr.setSingleStep(0.02)
        self.thr.setValue(spec.get("threshold", 0.8))
        self.thr.valueChanged.connect(lambda v: self.set("threshold", round(v, 3)))
        self.thr_row = row(self.thr, hint("match needed (0.8 is a good start)"))
        form.addRow("Match", self.thr_row)

        self.use_snapshot = QCheckBox("Pick from the recorded landing instead of the live screen")
        form.addRow("", self.use_snapshot)

        self.test_btn = QPushButton("Test on screen now")
        self.test_btn.clicked.connect(self.test)
        self.test_lbl = hint("")
        form.addRow("", row(self.test_btn, self.test_lbl))
        self.refresh()

    def set(self, key, value):
        self.spec[key] = value
        self.on_change()
        self.refresh()

    def set_type(self, t):
        self.set("type", t)

    def set_region(self, i, v):
        region = list(self.spec.get("region") or [0, 0, 100, 100])
        region[i] = v
        self.spec["region"] = region
        self.on_change()

    def refresh(self):
        t = self.spec["type"]
        self.region_row.setVisible(t != "pixel")
        self.color_row.setVisible(t != "image")
        self.frac_row.setVisible(t == "color_area")
        self.point_row.setVisible(t == "pixel")
        self.tpl_row.setVisible(t == "image")
        self.thr_row.setVisible(t == "image")
        self.form().labelForField(self.region_row).setVisible(t != "pixel")
        self.form().labelForField(self.color_row).setVisible(t != "image")
        self.form().labelForField(self.frac_row).setVisible(t == "color_area")
        self.form().labelForField(self.point_row).setVisible(t == "pixel")
        self.form().labelForField(self.tpl_row).setVisible(t == "image")
        self.form().labelForField(self.thr_row).setVisible(t == "image")
        self.point_lbl.setText("({}, {})".format(*self.spec.get("point", [0, 0])))
        self.tpl_lbl.setText(os.path.basename(self.spec.get("template") or "") or "none yet")
        region = self.spec.get("region") or [0, 0, 100, 100]
        for s, v in zip(self.region_spins, region):
            s.blockSignals(True)
            s.setValue(int(v))
            s.blockSignals(False)
        has_snap = bool(self.snapshot_name and self.snapshot_name in self.c.snapshots)
        self.use_snapshot.setVisible(has_snap)

    def form(self):
        return self.layout()

    def pick(self, mode, capture=False):
        source = None
        if self.use_snapshot.isVisible() and self.use_snapshot.isChecked():
            source = self.c.snapshots[self.snapshot_name]
        self.c.pick(mode, lambda res, img, origin: self.picked(res, img, origin, capture), source)

    def picked(self, result, image, origin, capture):
        if not result:
            return
        if "region" in result:
            x, y, w, h = result["region"]
            if capture or self.spec["type"] == "image":
                ox, oy = origin
                crop = image[y - oy:y - oy + h, x - ox:x - ox + w]
                os.makedirs(config.TEMPLATE_DIR, exist_ok=True)
                name = f"{slug(self.c.current_name())}_{int(time.time())}.png"
                detect.write_image(os.path.join(config.TEMPLATE_DIR, name), crop)
                self.spec["template"] = f"templates/{name}"
                m = 40
                self.spec["region"] = [max(x - m, 0), max(y - m, 0), w + 2 * m, h + 2 * m]
            else:
                self.spec["region"] = [x, y, w, h]
        else:
            self.spec["color"] = result["color"]
            self.color_btn.set_rgb(result["color"], notify=False)
            if self.spec["type"] == "pixel":
                self.spec["point"] = result["point"]
        self.on_change()
        self.refresh()

    def test(self):
        try:
            det = detect.Detector(self.spec)
            found, score, pos = det.check_now(self.c.cfg.get("monitor", 1))
            where = f" at {pos}" if pos else ""
            self.test_lbl.setText(("FOUND" if found else "not found") + f" - {detect.describe_score(det, score)}{where}")
        except Exception as e:
            self.test_lbl.setText(f"can't test: {e}")


# ---- pages ---------------------------------------------------------------------

class Page(QWidget):
    title = ""
    subtitle = ""
    code = "MODULE"

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 18, 26, 18)
        outer.setSpacing(2)
        top = QHBoxLayout()
        heads = QVBoxLayout()
        heads.setSpacing(0)
        self.kicker = QLabel(f"// {self.code}")
        self.kicker.setObjectName("PageKicker")
        heads.addWidget(self.kicker)
        t = QLabel(self.title.upper() + "<span style='color:#f3e600'>_</span>")
        t.setObjectName("PageTitle")
        t.setTextFormat(Qt.RichText)
        heads.addWidget(t)
        top.addLayout(heads)
        top.addStretch(1)
        self.meta = QLabel("")
        self.meta.setObjectName("PageMeta")
        self.meta.setAlignment(Qt.AlignRight | Qt.AlignTop)
        top.addWidget(self.meta)
        outer.addLayout(top)
        if self.subtitle:
            outer.addWidget(hint(self.subtitle))
        outer.addSpacing(10)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body, 1)

    def set_number(self, n):
        self.kicker.setText(f"{n:02d} // {self.code}")

    def shown(self):
        pass

    def tick(self):
        pass


LOG_TAGS = (
    ("macro", "MACRO", "#f3e600"), ("party", "PARTY", "#2de2e6"), ("profile", "PROFILE", "#ff3c5f"),
    ("parry", "COMBAT", "#3ee67a"), ("dodge", "COMBAT", "#3ee67a"), ("landed", "COMBAT", "#3ee67a"),
    ("builder", "BUILDER", "#c084fc"), ("talent", "BUILDER", "#c084fc"), ("music", "MUSIC", "#fb7185"),
    ("warning", "WARN", "#ff3c5f"), ("error", "WARN", "#ff3c5f"), ("failed", "WARN", "#ff3c5f"),
)


def log_html(line):
    """'12:00:01  macros ON' -> coloured '12:00:01  [MACRO]  macros on' like a terminal."""
    stamp, _, msg = line.partition("  ")
    low = msg.lower()
    tag, colour = "SYS", "#6b808c"
    for word, t, c in LOG_TAGS:
        if word in low:
            tag, colour = t, c
            break
    esc = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    pad = "&nbsp;" * (10 - len(tag))  # line the messages up after tags of different lengths
    return (f"<span style='color:#5f7380'>{stamp}</span>&nbsp;&nbsp;&nbsp;"
            f"<span style='color:{colour}'>[{tag}]</span>{pad}<span style='color:#c9d3dc'>{esc}</span>")


class InfoCard(QFrame):
    def __init__(self, label):
        super().__init__()
        self.setObjectName("InfoCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(2)
        lab = QLabel(label)
        lab.setObjectName("InfoLabel")
        self.value = QLabel("-")
        self.value.setObjectName("InfoValue")
        self.value.setTextFormat(Qt.RichText)
        lay.addWidget(lab)
        lay.addWidget(self.value)


class StatusBanner(QFrame):
    """The big yellow MACROS ONLINE panel; click it to arm or disarm."""

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.setObjectName("StatusBanner")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(110)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 14, 22, 14)
        left = QVBoxLayout()
        self.kicker = QLabel()
        self.kicker.setObjectName("BannerKicker")
        self.title = QLabel()
        self.title.setObjectName("BannerTitle")
        left.addWidget(self.kicker)
        left.addWidget(self.title)
        lay.addLayout(left)
        lay.addStretch(1)
        right = QVBoxLayout()
        keyrow = QHBoxLayout()
        press = QLabel("PRESS")
        press.setObjectName("BannerMeta")
        self.press = press
        self.key = QLabel()
        self.key.setObjectName("BannerKey")
        keyrow.addWidget(press)
        keyrow.addSpacing(10)
        keyrow.addWidget(self.key)
        right.addLayout(keyrow)
        self.meta = QLabel()
        self.meta.setObjectName("BannerMeta")
        self.meta.setAlignment(Qt.AlignRight)
        right.addWidget(self.meta)
        lay.addLayout(right)
        self.armed = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            eng = self.c.engine
            eng.set_active(not eng.active)
            uifx.pulse(self)
            self.c.click_sound()

    def refresh(self):
        on = self.c.engine.active
        key = nice_key(self.c.cfg.get("toggle_key")).upper()
        self.key.setText(key)
        self.meta.setText(f"SYS.ACTIVE // 0x{key}" if on else "SYS.IDLE // CLICK TO ARM")
        if on != self.armed:
            self.armed = on
            self.kicker.setText("■ STATUS: ARMED" if on else "■ STATUS: SAFE")
            self.title.setText("MACROS ONLINE" if on else "MACROS OFFLINE")
            self.setProperty("armed", "true" if on else "false")
            for w in (self, self.kicker, self.title, self.meta, self.key, self.press):
                w.style().unpolish(w)
                w.style().polish(w)


class HomePage(Page):
    title = "Home"
    code = "CONTROL"

    def __init__(self, controller):
        super().__init__(controller)
        self.started = time.time()
        self.banner = StatusBanner(controller)
        self.body.addWidget(self.banner)
        cards = QHBoxLayout()
        cards.setSpacing(0)
        self.game_card, self.target_card, self.party_card = (InfoCard("GAME_WINDOW"), InfoCard("TARGET_DETECTED"),
                                                             InfoCard("PARTY_LINK"))
        for card in (self.game_card, self.target_card, self.party_card):
            cards.addWidget(card)
        self.body.addLayout(cards)
        panel = QFrame()
        panel.setObjectName("LogPanel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 10, 14, 10)
        head = QHBoxLayout()
        title = QLabel("&gt; ACTIVITY_LOG")
        title.setObjectName("LogTitle")
        title.setTextFormat(Qt.RichText)
        head.addWidget(title)
        head.addStretch(1)
        self.count = QLabel("00 ENTRIES")
        self.count.setObjectName("LogMeta")
        head.addWidget(self.count)
        purge = QPushButton("[PURGE]")
        purge.setFlat(True)
        purge.setStyleSheet("border: none; color: #5f7380; font-family: Consolas; font-size: 8pt; padding: 2px 6px;")
        purge.clicked.connect(self.purge)
        head.addWidget(purge)
        pl.addLayout(head)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #16232b;")
        pl.addWidget(line)
        from PySide6.QtWidgets import QTextEdit
        self.log = QTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.document().setMaximumBlockCount(400)
        pl.addWidget(self.log, 1)
        self.cursor = QLabel("&gt; <span style='color:#2de2e6'>█</span>")
        self.cursor.setTextFormat(Qt.RichText)
        self.cursor.setStyleSheet("font-family: Consolas; color: #2de2e6;")
        pl.addWidget(self.cursor)
        self.body.addWidget(panel, 1)
        self.seq = 0
        self.lines = 0
        self.blink = 0

    def purge(self):
        self.log.clear()
        self.lines = 0

    def tick(self):
        eng = self.c.engine
        self.banner.refresh()
        up = int(time.time() - self.started)
        self.meta.setText(f"SESSION  <span style='color:#ffffff'>{up // 3600:02d}:{up // 60 % 60:02d}:{up % 60:02d}</span>"
                          "<br>ARM MACROS → JACK INTO GAME")
        self.meta.setTextFormat(Qt.RichText)
        game = (self.c.cfg.get("game_window") or "any window").upper()
        focused = eng.game_focused()
        tag = "<span style='color:#3ee67a; font-size:8pt'> [FOCUSED]</span>" if focused else \
            "<span style='color:#ff3c5f; font-size:8pt'> [NOT FOCUSED]</span>"
        self.game_card.value.setText(game + tag)
        playing = eng.current_game() or (f"PLACE {eng.place_id}" if eng.universe_id else "NONE")
        self.target_card.value.setText(playing.upper())
        if self.c.cfg.get("party", {}).get("enabled"):
            st = eng.party_link.status
            colour = "#2de2e6" if st == "connected" else "#f3e600"
            self.party_card.value.setText(f"<span style='color:{colour}'>■ {st.upper()}</span>")
        else:
            self.party_card.value.setText("<span style='color:#5f7380'>■ OFF</span>")
        for seq, line in eng.log.since(self.seq):
            self.seq = seq
            self.log.append(log_html(line))
            self.lines += 1
        self.count.setText(f"{min(self.lines, 400):02d} ENTRIES")
        self.blink = (self.blink + 1) % 10
        self.cursor.setText("&gt; " + ("<span style='color:#2de2e6'>█</span>" if self.blink < 5 else ""))


class WidgetCard(QFrame):
    def __init__(self, controller, wid, title, desc):
        super().__init__()
        self.c = controller
        self.wid = wid
        self.setObjectName("Card")
        self.setCursor(Qt.OpenHandCursor)
        self.setMinimumHeight(110)
        lay = QVBoxLayout(self)
        t = QLabel(title)
        t.setStyleSheet("font-weight: 600; font-size: 11pt;")
        lay.addWidget(t)
        lay.addWidget(hint(desc))
        lay.addStretch(1)
        self.btn = QPushButton()
        self.btn.clicked.connect(self.toggle)
        lay.addWidget(row(self.btn, hint("or drag this card out")))
        self.refresh()
        self.press = None

    def refresh(self):
        self.btn.setText("Hide" if self.c.overlay_visible(self.wid) else "Show")

    def toggle(self):
        if self.c.overlay_visible(self.wid):
            self.c.hide_overlay(self.wid)
        else:
            self.c.show_overlay(self.wid)
        self.refresh()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.press = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self.press is None or (e.position().toPoint() - self.press).manhattanLength() < 12:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.wid)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab().scaledToWidth(220, Qt.SmoothTransformation))
        drag.setHotSpot(QPoint(20, 20))
        drag.exec(Qt.MoveAction)
        self.press = None
        self.c.show_overlay(self.wid, QCursor.pos() - QPoint(20, 20))
        self.refresh()


class WidgetsPage(Page):
    title = "Overlays"
    code = "DISPLAY"
    subtitle = ("Drag a card out of this window and drop it anywhere on your screen. Drag an overlay to move it, "
                "right-click it to hide it.")

    def __init__(self, controller):
        super().__init__(controller)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        inner = QVBoxLayout(holder)
        inner.setContentsMargins(0, 0, 14, 0)
        inner.setSpacing(10)
        scroll.setWidget(holder)
        self.body.addWidget(scroll, 1)
        self.body = inner
        ov = self.c.cfg["overlay"]
        self.lock = QCheckBox("Lock overlays (clicks go straight through to the game)")
        self.lock.setChecked(ov.get("locked", False))
        self.lock.toggled.connect(self.set_lock)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(30, 100)
        self.opacity.setValue(int(ov.get("opacity", 0.92) * 100))
        self.opacity.setFixedWidth(200)
        self.opacity.valueChanged.connect(self.set_opacity)
        self.focus_hide = QCheckBox("Hide overlays when Roblox isn't the focused window")
        self.focus_hide.setChecked(ov.get("hide_unfocused", True))
        self.focus_hide.toggled.connect(lambda on: (self.c.cfg["overlay"].__setitem__("hide_unfocused", on),
                                                    self.c.changed(apply=False)))
        self.body.addWidget(self.lock)
        self.body.addWidget(self.focus_hide)
        self.body.addWidget(row(QLabel("Opacity"), self.opacity))

        def set_ov(key, value):
            self.c.cfg["overlay"][key] = value
            self.c.changed(apply=False)
        style = combo({"flat": "Flat bars", "neon": "Neon (angled, glowing)", "edge": "Edgerunner (like the Cyberpunk bar)", "image": "My own skin pictures",
                       "card": "Cards (name + time)"}, ov.get("bar_style", "flat"), lambda v: set_ov("bar_style", v))
        width = spin(ov.get("flat_width", 178), 40, 1600, lambda v: set_ov("flat_width", v), " px", 10)
        height = spin(ov.get("flat_height", 12), 2, 200, lambda v: set_ov("flat_height", v), " px")
        outline = spin(ov.get("flat_outline", 1), 0, 10, lambda v: set_ov("flat_outline", v), " px")
        box, form = form_group("Parry / Dodge bars")
        form.addRow("Style", style)
        form.addRow("Size", row(QLabel("length"), width, QLabel("thickness"), height, QLabel("outline"), outline))

        # text on the bars, off by default so plain bars cost nothing extra
        bt = ov.setdefault("bar_text", {"enabled": False, "template": "{NAME} {STATUS}", "color": "#ffffff",
                                        "size": 9, "position": "above"})

        def set_bt(key, value):
            bt[key] = value
            self.c.changed(apply=False)
        text_on = QCheckBox("Show text on the bars")
        text_on.setChecked(bt.get("enabled", False))
        text_on.toggled.connect(lambda on: set_bt("enabled", on))
        template = QLineEdit(bt.get("template", "{NAME} {STATUS}"))
        template.setToolTip("{NAME} = the bar's label, {STATUS} = READY / 1.2s / LANDED")
        template.editingFinished.connect(lambda: set_bt("template", template.text() or "{NAME} {STATUS}"))
        tcol = HexColorButton(bt.get("color", "#ffffff"), lambda h: set_bt("color", h))
        tsize = spin(bt.get("size", 9), 6, 40, lambda v: set_bt("size", v), " pt")
        tpos = combo({"above": "above the bar", "inside": "inside the bar"}, bt.get("position", "above"),
                     lambda v: set_bt("position", v))
        form.addRow("", text_on)
        form.addRow("Text", row(template, stretch=False))
        form.addRow("", row(tcol, tsize, tpos))
        form.addRow(hint("e.g. \"AUTOPARRY METER {STATUS}\". Set a label per bar in Cooldowns > Bar text; "
                         "without one the bar's name is used."))

        # skin pictures
        sk = ov.setdefault("skin", {"empty": "", "full": "", "fill_area": [4, 22, 96, 78]})

        def pick_skin(which):
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(self, f"Skin picture: bar {which}", "",
                                                  "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
            if path:
                sk[which] = self.c.keep_file(path, f"skin_{which}")
                self.c.changed(apply=False)
                for o in self.c.overlays.values():
                    getattr(o, "cache", {}).clear()
                self.skin_lbl.setText(self.skin_text())
        empty_btn = QPushButton("Import empty bar picture")
        empty_btn.clicked.connect(lambda: pick_skin("empty"))
        full_btn = QPushButton("Import full bar picture")
        full_btn.clicked.connect(lambda: pick_skin("full"))
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: (sk.update(empty="", full=""), self.c.changed(apply=False),
                                           self.skin_lbl.setText(self.skin_text())))
        form.addRow("Skin", row(empty_btn, full_btn, clear_btn))
        self.skin_lbl = hint(self.skin_text())
        form.addRow("", self.skin_lbl)
        area_spins = []
        for i, name in enumerate(("left", "top", "right", "bottom")):
            def setter(v, i=i):
                sk["fill_area"][i] = v
                self.c.changed(apply=False)
            area_spins.append(spin(sk.get("fill_area", [4, 22, 96, 78])[i], 0, 100, setter, "%"))
        form.addRow("Fill area", row(*[w for pair in zip([QLabel(n) for n in ("left", "top", "right", "bottom")],
                                                          area_spins) for w in pair]))
        form.addRow(hint("Style 'My own skin pictures': the empty picture is the bar at 0, the full picture is "
                         "revealed left to right inside the fill area as it recharges. With only an empty picture, "
                         "a colour fill is drawn inside the fill area and the picture sits on top like a frame."))

        # lining up
        snap = QCheckBox("Snap bars together when you drop them near each other")
        snap.setChecked(ov.get("snap", True))
        snap.toggled.connect(lambda on: set_ov("snap", on))
        gap = spin(ov.get("line_gap", 6), 0, 80, lambda v: set_ov("line_gap", v), " px gap")
        line_up = QPushButton("Line up bars")
        line_up.setObjectName("Primary")
        line_up.clicked.connect(lambda: self.c.engine.log(f"lined up {self.c.line_up_bars()} bars"))
        form.addRow("", snap)
        form.addRow("", row(line_up, gap))
        self.body.addWidget(box)
        pw = spin(ov.get("party_width", 400), 220, 1200, lambda v: set_ov("party_width", v), " px", 10)
        pb = spin(ov.get("party_bar", 12), 3, 60, lambda v: set_ov("party_bar", v), " px")
        pstyle = combo({"cyber": "Cyber", "classic": "Classic"}, ov.get("party_style", "cyber"),
                       lambda v: set_ov("party_style", v))
        plines = spin(ov.get("party_chat_lines", 3), 0, 8, lambda v: set_ov("party_chat_lines", v), " messages")
        psize = spin(ov.get("party_info_size", 10), 7, 20, lambda v: set_ov("party_info_size", v), " pt")
        self.body.addWidget(row(QLabel("Party HP  style"), pstyle, QLabel("width"), pw, QLabel("bar thickness"), pb,
                                QLabel("server text"), psize))
        if not engine_mod.LITE:
            self.body.addWidget(row(QLabel("Party messages shown on the overlay"), plines))
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 8, 0, 0)
        self.grid.setSpacing(12)
        self.body.addWidget(self.grid_host)
        self.body.addStretch(1)
        self.cards = []

    def skin_text(self):
        sk = self.c.cfg["overlay"].get("skin", {})
        names = [f"{k}: {os.path.basename(sk[k])}" for k in ("empty", "full") if sk.get(k)]
        return "  ·  ".join(names) or "no skin pictures yet"

    def set_lock(self, on):
        self.c.cfg["overlay"]["locked"] = on
        self.c.restyle_overlays()
        self.c.changed(apply=False)

    def set_opacity(self, v):
        self.c.cfg["overlay"]["opacity"] = v / 100
        self.c.restyle_overlays()
        self.c.changed(apply=False)

    def shown(self):
        for card in self.cards:
            card.setParent(None)
        self.cards = []
        for i, (wid, title, desc) in enumerate(overlays.widget_catalog(self.c.cfg)):
            card = WidgetCard(self.c, wid, title, desc)
            self.grid.addWidget(card, i // 3, i % 3)
            self.cards.append(card)

    def tick(self):
        for card in self.cards:
            card.refresh()


class ListPage(Page):
    """A list of items on the left and an editor for the selected one on the right."""
    list_key = ""
    add_label = "Add"

    def __init__(self, controller):
        super().__init__(controller)
        split = QHBoxLayout()
        split.setSpacing(16)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setFixedWidth(200)
        self.list.currentRowChanged.connect(self.select)
        left.addWidget(self.list, 1)
        add = QPushButton(self.add_label)
        add.setObjectName("Primary")
        add.clicked.connect(self.add)
        dup = QPushButton("Duplicate")
        dup.clicked.connect(self.duplicate)
        delete = QPushButton("Delete")
        delete.setObjectName("Danger")
        delete.clicked.connect(self.delete)
        left.addWidget(add)
        left.addWidget(row(dup, delete, stretch=False))
        self.left = left
        split.addLayout(left)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        split.addWidget(self.scroll, 1)
        self.body.addLayout(split, 1)
        self.editor = None

    @property
    def items(self):
        return self.c.cfg[self.list_key]

    def shown(self):
        current = max(self.list.currentRow(), 0)
        self.list.blockSignals(True)
        self.list.clear()
        for item in self.items:
            self.list.addItem(self.label_for(item))
        self.list.blockSignals(False)
        if self.items:
            self.list.setCurrentRow(min(current, len(self.items) - 1))
            self.select(self.list.currentRow())
        else:
            self.select(-1)

    def label_for(self, item):
        return item["name"]

    def update_label(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.items):
            self.list.item(i).setText(self.label_for(self.items[i]))

    def unique(self, name):
        names = {i["name"] for i in self.items}
        base, n = name, 2
        while name in names:
            name = f"{base} {n}"
            n += 1
        return name

    def select(self, i):
        self.c.selected_name = self.items[i]["name"] if 0 <= i < len(self.items) else ""
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 14, 0)
        if 0 <= i < len(self.items):
            self.build(lay, self.items[i])
        else:
            lay.addWidget(hint("Nothing here yet. Press the button on the left to add one."))
        lay.addStretch(1)
        self.scroll.setWidget(holder)

    def add(self):
        self.items.append(self.new_item(self.unique(self.new_name)))
        self.c.changed()
        self.shown()
        self.list.setCurrentRow(len(self.items) - 1)

    def duplicate(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.items):
            item = copy.deepcopy(self.items[i])
            item["name"] = self.unique(item["name"])
            self.items.insert(i + 1, item)
            self.c.changed()
            self.shown()
            self.list.setCurrentRow(i + 1)

    def delete(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.items):
            self.deleted(self.items.pop(i))
            self.c.changed()
            self.shown()

    def deleted(self, item):
        pass

    def name_field(self, item, form, on_rename=None):
        edit = QLineEdit(item["name"])

        def done():
            new = edit.text().strip() or item["name"]
            if new != item["name"]:
                others = {i["name"] for i in self.items if i is not item}
                if new in others:
                    edit.setText(item["name"])
                    return
                old, item["name"] = item["name"], new
                if on_rename:
                    on_rename(old, new)
                self.c.changed()
                self.update_label()
        edit.editingFinished.connect(done)
        form.addRow("Name", edit)


def form_group(title, checkable=False, checked=True, on_toggle=None):
    box = QGroupBox(title)
    if checkable:
        box.setCheckable(True)
        box.setChecked(checked)
        box.toggled.connect(on_toggle)
    form = QFormLayout(box)
    form.setLabelAlignment(Qt.AlignRight)
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(8)
    return box, form


class CooldownsPage(ListPage):
    title = "Cooldowns"
    code = "TIMERS"
    subtitle = "Bars that time your dodge, parry or any other key from the moment you press it."
    list_key = "cooldowns"
    add_label = "Add cooldown"
    new_name = "New cooldown"

    def __init__(self, controller):
        super().__init__(controller)
        mantra = QPushButton("+ Mantra bar")
        mantra.setToolTip("A bar for a mantra on your hotbar: it follows the slot going dark while on cooldown.")
        mantra.clicked.connect(self.add_mantra)
        self.left.insertWidget(2, mantra)

    def new_item(self, name):
        return config.new_cooldown(name)

    def add_mantra(self):
        used = {cd.get("hotbar_slot") for cd in self.items}
        slot = next((n for n in (4, 5, 6, 7, 8, 9, 10, 3, 2, 1) if n not in used), 4)
        cd = config.new_cooldown(self.unique(f"Mantra {slot % 10}"))
        cd.update(key=str(slot % 10), hotbar_slot=slot, cooldown_ms=8000, color="#c084fc")
        cd["cancel"]["enabled"] = False
        self.items.append(cd)
        self.c.changed()
        self.shown()
        self.list.setCurrentRow(len(self.items) - 1)

    def deleted(self, item):
        self.c.hide_overlay(f"cooldown:{item['name']}")

    def build(self, lay, cd):
        ch = self.c.changed
        box, form = form_group("General")
        self.name_field(cd, form, lambda old, new: self.c.rename_overlay(f"cooldown:{old}", f"cooldown:{new}"))
        form.addRow("Key", KeyButton(self.c, cd["key"], lambda k: (cd.__setitem__("key", k), ch())))
        form.addRow("Cooldown", spin(cd["cooldown_ms"], 50, 120000,
                                     lambda v: (cd.__setitem__("cooldown_ms", v), ch()), " ms", 50))
        form.addRow("Bar colour", HexColorButton(cd.get("color", "#4aa3ff"),
                                                 lambda h: (cd.__setitem__("color", h), ch())))
        label = QLineEdit(cd.get("label", ""))
        label.setPlaceholderText(f"text on the bar, e.g. AUTOPARRY METER (empty = {cd['name']})")
        label.editingFinished.connect(lambda: (cd.__setitem__("label", label.text().strip()), ch()))
        form.addRow("Bar text", label)
        form.addRow("Game bubble", row(combo({0: "none", 1: "1st (roll)", 2: "2nd (parry)", 3: "3rd", 4: "4th"},
                                             cd.get("icon_slot", 0),
                                             lambda v: (cd.__setitem__("icon_slot", v), ch())),
                                       hint("syncs this bar with the game's cooldown bubble under your health bar")))
        slots = {0: "none"}
        slots.update({n: f"slot {n % 10}" for n in range(1, 11)})
        form.addRow("Hotbar slot", row(combo(slots, cd.get("hotbar_slot", 0),
                                             lambda v: (cd.__setitem__("hotbar_slot", v), ch())),
                                       hint("for mantras: follows that hotbar slot going dark while on cooldown")))
        live = self.c.engine.cooldown(cd["name"])
        if live and live.natural:
            form.addRow("", hint(f"learned from the game: {live.span():.2f}s per use "
                                 f"(from {len(live.natural)} full cooldowns)"))
        show = QPushButton("Show bar on screen")
        show.clicked.connect(lambda: self.c.show_overlay(f"cooldown:{cd['name']}"))
        form.addRow("", show)
        lay.addWidget(box)

        cancel = cd["cancel"]
        box, form = form_group("Cancel gives it back (roll cancel)", True, cancel.get("enabled", False),
                               lambda on: (cancel.__setitem__("enabled", on), ch()))
        form.addRow(hint("If you press the cancel key soon enough after using this, the cooldown is refunded."))
        form.addRow("Cancel key", KeyButton(self.c, cancel.get("key", "mouse_right"),
                                            lambda k: (cancel.__setitem__("key", k), ch())))
        form.addRow("Within", spin(cancel.get("window_ms", 350), 10, 5000,
                                   lambda v: (cancel.__setitem__("window_ms", v), ch()), " ms", 10))
        form.addRow("Cancel cooldown", spin(cancel.get("cooldown_ms", 0), 0, 60000,
                                            lambda v: (cancel.__setitem__("cooldown_ms", v), ch()), " ms", 50))
        form.addRow("Free cancels", spin(cancel.get("max_refunds", 1), 0, 10,
                                         lambda v: (cancel.__setitem__("max_refunds", v), ch()), " in a row"))
        form.addRow(hint("Deepwoken: the first roll cancel gives the roll back, but cancelling that extra roll "
                         "too puts it on cooldown - so 1."))
        lay.addWidget(box)

        self.reset_widgets = {}
        for r in cd["resets"]:
            self.build_reset(lay, cd, r)
        add = QPushButton("+ Add reset trigger")
        add.setToolTip("Something seen on screen after a key press that makes this ready again")
        add.clicked.connect(lambda: self.add_reset(cd))
        lay.addWidget(row(add))

    def add_reset(self, cd):
        names = {r["name"] for r in cd["resets"]}
        name, n = "New reset", 2
        while name in names:
            name, n = f"New reset {n}", n + 1
        cd["resets"].append(config.new_reset(name, cd["key"]))
        self.c.changed()
        self.select(self.list.currentRow())

    def build_reset(self, lay, cd, r):
        ch = self.c.changed
        box, form = form_group(f"Reset: {r['name']}", True, r.get("enabled", False),
                               lambda on: (r.__setitem__("enabled", on), ch()))
        form.addRow(hint(f"Makes {cd['name']} ready again when the effect below shows up shortly after you press "
                         "the trigger key. Set it up: press Record, do it once in game, then come back and pick "
                         "the effect's area and colour from the recording."))
        name = QLineEdit(r["name"])

        def rename():
            new = name.text().strip()
            if new and new != r["name"] and new not in {x["name"] for x in cd["resets"]}:
                r["name"] = new
                box.setTitle(f"Reset: {new}")
                ch()
            else:
                name.setText(r["name"])
        name.editingFinished.connect(rename)
        form.addRow("Name", name)
        form.addRow("Trigger key", KeyButton(self.c, r.get("key", ""), lambda k: (r.__setitem__("key", k), ch())))
        toggle = KeyButton(self.c, r.get("toggle_key", ""), lambda k: (r.__setitem__("toggle_key", k), ch()))
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: (r.__setitem__("toggle_key", ""), toggle.setText(nice_key("")), ch()))
        form.addRow("On/off hotkey", row(toggle, clear))
        form.addRow("Watch for", spin(r.get("window_ms", 450), 50, 3000,
                                      lambda v: (r.__setitem__("window_ms", v), ch()), " ms after the key", 25))
        record = QPushButton("Record next one")
        label = hint("")
        record.clicked.connect(lambda: self.record(cd, r, label))
        form.addRow("", row(record, label))
        det = DetectorEditor(self.c, r["detect"], ["color_area", "image"], ch,
                             snapshot_name=f"{cd['name']}/{r['name']}")
        form.addRow(det)
        delete = QPushButton("Delete this reset")
        delete.setObjectName("Danger")
        delete.clicked.connect(lambda: (cd["resets"].remove(r), ch(), self.select(self.list.currentRow())))
        form.addRow("", row(delete))
        self.reset_widgets[f"{cd['name']}/{r['name']}"] = (label, det)
        lay.addWidget(box)

    def record(self, cd, r, label):
        self.c.engine.snapshot_for = (cd["name"], r["name"])
        self.c.engine.snapshot_path = None
        label.setText(f"waiting - go in game and press {nice_key(r['key'])} so it lands")
        self.c.waiting_snapshot = self

    def snapshot_ready(self, name):
        widgets = getattr(self, "reset_widgets", {}).get(name)
        if not widgets:
            return
        label, det = widgets
        try:
            label.setText("recorded - now use Pick area / Pick colour below")
            det.refresh()
            det.use_snapshot.setChecked(True)
        except RuntimeError:
            pass  # editor was rebuilt


class StepRow(QFrame):
    def __init__(self, page, steps, index, on_change):
        super().__init__()
        self.setObjectName("StepRow")
        step = steps[index]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        num = QLabel(f"{index + 1}.")
        num.setFixedWidth(22)
        lay.addWidget(num)

        def set_action(a):
            step["action"] = a
            if a in combat.KEY_ACTIONS:
                step.setdefault("key", "e")
            elif a in combat.MOUSE_ACTIONS:
                step.setdefault("button", "left")
            step.setdefault("ms", 25 if a != "wait" else 50)
            on_change(rebuild=True)
        lay.addWidget(combo(combat.STEP_ACTIONS, step["action"], set_action))
        a = step["action"]
        if a in combat.KEY_ACTIONS:
            lay.addWidget(combo(sendinput.KEY_NAMES, step.get("key", "e"),
                                lambda k: (step.__setitem__("key", k), on_change()), editable=True))
        elif a in combat.MOUSE_ACTIONS:
            lay.addWidget(combo({b: nice_key(f"mouse_{b}") for b in sendinput.MOUSE_BUTTONS},
                                step.get("button", "left"), lambda b: (step.__setitem__("button", b), on_change())))
        if a in ("tap", "click", "wait"):
            label = "for" if a == "wait" else "hold"
            lay.addWidget(QLabel(label))
            lay.addWidget(spin(step.get("ms", 25), 0, 60000, lambda v: (step.__setitem__("ms", v), on_change()),
                               " ms", 5))
        lay.addStretch(1)
        for text, tip, fn in (("↑", "Move up", lambda: page.move_step(steps, index, -1)),
                              ("↓", "Move down", lambda: page.move_step(steps, index, 1)),
                              ("✕", "Delete step", lambda: page.delete_step(steps, index))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedWidth(34)
            b.clicked.connect(fn)
            lay.addWidget(b)


def describe_steps(steps):
    out = []
    for s in steps:
        a = s.get("action")
        if a == "tap":
            out.append(f"press {nice_key(s.get('key'))}")
        elif a == "down":
            out.append(f"hold {nice_key(s.get('key'))}")
        elif a == "up":
            out.append(f"release {nice_key(s.get('key'))}")
        elif a == "click":
            out.append(f"click {nice_key('mouse_' + s.get('button', 'left'))}")
        elif a == "mouse_down":
            out.append(f"hold {nice_key('mouse_' + s.get('button', 'left'))}")
        elif a == "mouse_up":
            out.append(f"release {nice_key('mouse_' + s.get('button', 'left'))}")
        elif a == "wait":
            out.append(f"wait {s.get('ms', 0)}ms")
        elif a == "wait_release":
            out.append("wait until you let go")
    return " → ".join(out) or "no steps"


class MacrosPage(ListPage):
    title = "Macros"
    code = "INPUT"
    subtitle = "Press a hotkey to run a list of steps: hold keys, press keys, click, wait."
    list_key = "macros"
    add_label = "Add macro"
    new_name = "New macro"

    def new_item(self, name):
        return config.new_macro(name)

    def label_for(self, m):
        state = "" if m.get("enabled", True) else "  (off)"
        return f"{m['name']}  [{nice_key(m.get('hotkey'))}]{state}"

    def build(self, lay, m):
        ch = self.c.changed

        def changed():
            ch()
            self.update_label()
            self.summary.setText(describe_steps(m["steps"]))

        box, form = form_group("Macro")
        self.name_field(m, form)
        enabled = QCheckBox("Enabled")
        enabled.setChecked(m.get("enabled", True))
        enabled.toggled.connect(lambda on: (m.__setitem__("enabled", on), changed()))
        form.addRow("", enabled)
        form.addRow("Hotkey", KeyButton(self.c, m.get("hotkey", ""), lambda k: (m.__setitem__("hotkey", k), changed())))
        block = QCheckBox("Replace the key: the game only gets what this macro sends (keyboard keys)")
        block.setToolTip("Needed when the macro re-sends its own hotkey, like F -> right click -> F.")
        block.setChecked(m.get("block_key", False))
        block.toggled.connect(lambda on: (m.__setitem__("block_key", on), ch()))
        form.addRow("", block)
        interval = spin(m.get("interval_ms", 100), 1, 60000, lambda v: (m.__setitem__("interval_ms", v), ch()),
                        " ms between repeats", 10)

        def set_mode(mode):
            m["mode"] = mode
            interval.setEnabled(mode != "once")
            ch()
        form.addRow("When pressed", combo(combat.MODES, m.get("mode", "once"), set_mode))
        interval.setEnabled(m.get("mode", "once") != "once")
        form.addRow("Repeat delay", interval)
        lay.addWidget(box)

        box = QGroupBox("Steps")
        steps_lay = QVBoxLayout(box)
        self.summary = hint(describe_steps(m["steps"]))
        steps_lay.addWidget(self.summary)
        self.steps_holder = QVBoxLayout()
        self.steps_holder.setSpacing(6)
        steps_lay.addLayout(self.steps_holder)
        add = QPushButton("+ Add step")
        add.clicked.connect(lambda: (m["steps"].append({"action": "tap", "key": "e", "ms": 25}),
                                     self.rebuild_steps(m, changed), changed()))
        steps_lay.addWidget(row(add))
        lay.addWidget(box)
        lay.addWidget(hint("Keys a macro sends still count towards your cooldown bars. Any held keys are released "
                           "when a macro ends or macros are turned off."))
        self.rebuild_steps(m, changed)

    def rebuild_steps(self, m, changed):
        while self.steps_holder.count():
            w = self.steps_holder.takeAt(0).widget()
            if w:
                w.setParent(None)

        def on_change(rebuild=False):
            changed()
            if rebuild:
                QTimer.singleShot(0, lambda: self.rebuild_steps(m, changed))
        self._step_change = on_change
        self._macro = m
        for i in range(len(m["steps"])):
            self.steps_holder.addWidget(StepRow(self, m["steps"], i, on_change))

    def move_step(self, steps, i, d):
        j = i + d
        if 0 <= j < len(steps):
            steps[i], steps[j] = steps[j], steps[i]
            self._step_change(rebuild=True)

    def delete_step(self, steps, i):
        steps.pop(i)
        self._step_change(rebuild=True)


class RulesPage(ListPage):
    title = "Screen rules"
    code = "VISION"
    subtitle = "Watch the screen for a picture or colour, and react with a key press or click when it appears."
    list_key = "rules"
    add_label = "Add screen rule"
    new_name = "New screen rule"

    def new_item(self, name):
        return config.new_rule(name)

    def build(self, lay, r):
        ch = self.c.changed
        box, form = form_group("Rule")
        self.name_field(r, form)
        enabled = QCheckBox("Enabled")
        enabled.setChecked(r.get("enabled", True))
        enabled.toggled.connect(lambda on: (r.__setitem__("enabled", on), ch()))
        form.addRow("", enabled)
        self.live = hint("")
        form.addRow("Right now", self.live)
        lay.addWidget(box)

        box, form = form_group("What to look for")
        form.addRow(DetectorEditor(self.c, r["detect"], list(detect.TYPES), ch))
        lay.addWidget(box)

        a = r["action"]
        box, form = form_group("What to do")
        form.addRow("Fire", combo({"on_appear": "Once each time it appears",
                                   "while_visible": "Repeatedly while it's visible"},
                                  r.get("trigger", "on_appear"), lambda v: (r.__setitem__("trigger", v), ch())))
        form.addRow("At most every", spin(r.get("cooldown_ms", 500), 0, 600000,
                                          lambda v: (r.__setitem__("cooldown_ms", v), ch()), " ms", 50))
        key_box = combo(sendinput.KEY_NAMES, a.get("key", "space"),
                        lambda k: (a.__setitem__("key", k), ch()), editable=True)
        button_box = combo({b: nice_key(f"mouse_{b}") for b in sendinput.MOUSE_BUTTONS}, a.get("button", "left"),
                           lambda b: (a.__setitem__("button", b), ch()))
        at_box = combo({"match": "where it was found", "point": "a fixed spot"}, a.get("at", "match"),
                       lambda v: (a.__setitem__("at", v), ch(), sync()))
        point_lbl = QLabel("({}, {})".format(*a.get("point", [960, 540])))
        pick_point = QPushButton("Pick spot")

        def picked(res, img, origin):
            if res:
                a["point"] = res["point"]
                point_lbl.setText("({}, {})".format(*a["point"]))
                ch()
        pick_point.clicked.connect(lambda: self.c.pick("point", picked))
        ret = QCheckBox("Put the mouse back afterwards")
        ret.setChecked(a.get("return_mouse", True))
        ret.toggled.connect(lambda on: (a.__setitem__("return_mouse", on), ch()))
        rows = {"key": [("Key", key_box)],
                "click": [("Button", button_box), ("Click at", at_box), ("Spot", row(point_lbl, pick_point)),
                          ("", ret)]}

        def sync():
            kind = a.get("type", "none")
            for k, items in rows.items():
                for label, w in items:
                    visible = kind == k and not (label == "Spot" and a.get("at") != "point")
                    w.setVisible(visible)
                    lbl = form.labelForField(w)
                    if lbl:
                        lbl.setVisible(visible)
        form.addRow("Action", combo({"none": "Just show it", "key": "Press a key", "click": "Click"},
                                    a.get("type", "none"), lambda v: (a.__setitem__("type", v), ch(), sync())))
        for items in rows.values():
            for label, w in items:
                form.addRow(label, w)
        sync()
        lay.addWidget(box)

    def tick(self):
        if not hasattr(self, "live"):
            return
        try:
            rule = next((r for r in self.c.engine.rules if r.name == self.c.selected_name), None)
            if rule is None:
                self.live.setText("not running (disabled, or something needs fixing - see Home)")
            else:
                state = "FOUND" if rule.found else "not found"
                score = detect.describe_score(rule.detector, rule.score)
                where = f" at {rule.pos}" if rule.pos else ""
                self.live.setText(f"{state} - {score}{where} - fired {rule.fired}x")
        except RuntimeError:
            pass  # label was rebuilt


class PartyPage(Page):
    title = "Party HP"
    code = "SQUAD"
    subtitle = ("Your HP is read off your own health bar. Friends who run Elgansito Demolisher Macro with the same party code "
                "share theirs, and everyone sees each other's HP as bars.")

    def __init__(self, controller):
        super().__init__(controller)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 14, 0)
        scroll.setWidget(holder)
        self.body.addWidget(scroll, 1)
        ch = self.c.changed

        # -- your HP
        my = self.c.cfg["my_hp"]
        box, form = form_group("Your HP")
        self.hp_now = QLabel()
        form.addRow("Right now", self.hp_now)
        self.region_spins = []
        for i in range(4):
            s = spin(my["region"][i], 0 if i < 2 else 10, 20000, lambda v, i=i: self.set_region(i, v))
            s.setFixedWidth(84)
            self.region_spins.append(s)
        pick = QPushButton("Pick area")
        pick.setToolTip("Drag a box around your health bar, a little taller than the bar.")
        pick.clicked.connect(self.pick_region)
        form.addRow("Health bar area", row(*self.region_spins, pick))
        self.cal_value = QSpinBox()
        self.cal_value.setRange(1, 100)
        self.cal_value.setSuffix(" %")
        self.cal_value.setValue(100)
        add_cal = QPushButton("Calibrate")
        add_cal.setToolTip("Type the % the game shows on your health bar right now, then press this.")
        add_cal.clicked.connect(self.add_calibration)
        reset_cal = QPushButton("Reset calibration")
        reset_cal.clicked.connect(self.reset_calibration)
        form.addRow("The game shows", row(self.cal_value, add_cal, reset_cal))
        self.cal_label = hint("")
        form.addRow("", self.cal_label)
        form.addRow(hint("The bar's fill isn't perfectly in step with the % the game prints. Every time you "
                         "calibrate at a different HP, readings get closer to exact."))
        lay.addWidget(box)

        # -- party
        pcfg = self.c.cfg["party"]
        box, form = form_group("Share with friends", True, pcfg.get("enabled", False),
                               lambda on: (pcfg.__setitem__("enabled", on), ch()))
        self.link_status = QLabel()
        form.addRow("Status", self.link_status)
        user = QLineEdit(pcfg.get("username", ""))
        user.setPlaceholderText("your Roblox username - this is the name friends see")
        user.editingFinished.connect(lambda: (pcfg.__setitem__("username", user.text().strip()), ch()))
        form.addRow("Your username", user)
        self.code_edit = QLineEdit(pcfg.get("code", ""))
        self.code_edit.setPlaceholderText("everyone in the party uses the same code")
        self.code_edit.editingFinished.connect(lambda: (pcfg.__setitem__("code", self.code_edit.text().strip()), ch()))
        new = QPushButton("New code")
        new.clicked.connect(self.new_code)
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.code_edit.text()))
        form.addRow("Party code", row(self.code_edit, new, copy_btn, stretch=False))
        friends = QLineEdit(", ".join(pcfg.get("friends", [])))
        friends.setPlaceholderText("usernames to show, comma separated - empty shows everyone with the code")
        friends.editingFinished.connect(lambda: (pcfg.__setitem__(
            "friends", [f.strip() for f in friends.text().split(",") if f.strip()]), ch()))
        form.addRow("Friends", friends)
        show = QPushButton("Show Party HP on screen")
        show.setObjectName("Primary")
        show.clicked.connect(lambda: self.c.show_overlay("party"))
        form.addRow("", row(show))
        form.addRow(hint("Each friend needs Elgansito Demolisher Macro, their own username, and the same party code. Only your "
                         "username and HP % are sent, encrypted with the party code, through a free public relay "
                         f"({pcfg.get('broker', 'broker.emqx.io')})."))
        lay.addWidget(box)

        # -- messages
        box, form = form_group("Messages")
        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFixedHeight(150)
        form.addRow(self.chat_log)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("message your party - Enter to send")
        self.chat_input.setMaxLength(party.CHAT_MAX)
        self.chat_input.returnPressed.connect(self.send_chat)
        send = QPushButton("Send")
        send.setObjectName("Primary")
        send.clicked.connect(self.send_chat)
        form.addRow(row(self.chat_input, send, stretch=False))
        quick = []
        for text in pcfg.get("quick", []):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, t=text: self.send_chat(t))
            quick.append(b)
        if quick:
            form.addRow(row(*quick))
        self.chat_info = hint("")
        form.addRow(self.chat_info)
        binds = pcfg.setdefault("binds", [])
        while len(binds) < 6:
            binds.append({"key": "", "text": ""})
        form.addRow(QLabel("Message hotkeys - press the key in game and the message is sent right away"))
        for b in binds:
            text = QLineEdit(b.get("text", ""))
            text.setPlaceholderText("message")
            text.setMaxLength(party.CHAT_MAX)
            text.editingFinished.connect(lambda b=b, text=text: (b.__setitem__("text", text.text().strip()), ch()))
            key = KeyButton(self.c, b.get("key", ""), lambda k, b=b: (b.__setitem__("key", k), ch()))
            form.addRow(row(key, text, stretch=False))
        form.addRow(hint(f"In game, press {self.c.cfg.get('chat_key', 'enter').upper()} to open a message box over "
                         "Roblox (change the key in Settings > Hotkeys). Messages are encrypted with the party code "
                         "like your HP. Friends get a notification and see them on their Party HP overlay."))
        lay.addWidget(box)
        self._chat_key = None

        # -- voice replies
        vc = self.c.cfg["voice"]
        box, form = form_group("Voice replies", True, vc.get("enabled", False),
                               lambda on: (vc.__setitem__("enabled", on), ch()))
        form.addRow(hint("When a friend messages, say a reply (\"yes\", \"no\", \"on my way\"...) within a few "
                         "seconds and it's sent for you. Windows' offline speech recognizer listens only then, or "
                         "while you hold the voice key."))
        mics = voice.list_mics()
        mic = combo({m: m for m in (mics or ["(no microphone found)"])}, vc.get("mic") or (mics[0] if mics else ""),
                    lambda v: (vc.__setitem__("mic", v), ch()))
        form.addRow("Microphone", mic)
        form.addRow("Listen for", spin(vc.get("listen_s", 6), 2, 30, lambda v: (vc.__setitem__("listen_s", v), ch()),
                                       " s after a message"))
        form.addRow("Hold to talk", row(KeyButton(self.c, vc.get("key", ""), lambda k: (vc.__setitem__("key", k), ch())),
                                        hint("optional: hold it and say a phrase to send it any time")))
        phrases = QLineEdit(", ".join(vc.get("phrases", [])))
        phrases.editingFinished.connect(lambda: (vc.__setitem__(
            "phrases", [p.strip().lower() for p in phrases.text().split(",") if p.strip()] or list(voice.PHRASES)), ch()))
        form.addRow("Phrases", phrases)
        self.voice_status = QLabel()
        test = QPushButton("Listen now (6 s)")
        test.clicked.connect(lambda: self.c.engine.voice.listen_for(6))
        form.addRow("Status", row(self.voice_status, test))
        lay.addWidget(box)

        # -- key prompts
        pr = self.c.cfg["prompts"]
        box, form = form_group("Press Z / X / C / V prompts", True, pr.get("enabled", False),
                               lambda on: (pr.__setitem__("enabled", on), ch()))
        form.addRow(hint("When Deepwoken shows a Z, X, C or V prompt, it's pressed for you (while macros are ON "
                         "and the game is focused). Fake prompts on a teal box are never pressed."))
        self.prompt_now = QLabel()
        form.addRow("Right now", self.prompt_now)
        thr = QDoubleSpinBox()
        thr.setRange(0.5, 0.99)
        thr.setSingleStep(0.01)
        thr.setValue(pr.get("threshold", 0.82))
        thr.valueChanged.connect(lambda v: (pr.__setitem__("threshold", round(v, 2)), ch()))
        form.addRow("Match needed", row(thr, hint("raise it if it presses things that aren't prompts")))
        form.addRow("Delay before pressing", spin(pr.get("delay_ms", 0), 0, 2000,
                                                  lambda v: (pr.__setitem__("delay_ms", v), ch()), " ms", 10))
        self.prompt_spins = []
        for i in range(4):
            s = spin((pr.get("region") or [0, 0, 1920, 1080])[i], 0 if i < 2 else 10, 20000,
                     lambda v, i=i: self.set_prompt_region(i, v))
            s.setFixedWidth(84)
            self.prompt_spins.append(s)
        ppick = QPushButton("Pick area")
        ppick.setToolTip("Drag a box over where the prompts appear. Smaller is faster and avoids false matches.")
        ppick.clicked.connect(self.pick_prompt_region)
        form.addRow("Search area", row(*self.prompt_spins, ppick))
        lay.addWidget(box)
        lay.addStretch(1)
        self.refresh_calibration()

    # your HP
    def set_region(self, i, v):
        self.c.cfg["my_hp"]["region"][i] = v
        self.c.changed()

    def pick_region(self):
        def picked(res, img, origin):
            if res and "region" in res:
                self.c.cfg["my_hp"]["region"] = res["region"]
                for s, v in zip(self.region_spins, res["region"]):
                    s.blockSignals(True)
                    s.setValue(v)
                    s.blockSignals(False)
                self.c.changed()
        self.c.pick("area", picked)

    def add_calibration(self):
        raw = self.c.engine.my_hp_raw
        if raw is None:
            self.cal_label.setText("can't see your health bar right now - go in game first")
            return
        cal = self.c.cfg["my_hp"].setdefault("calibration", [])
        cal[:] = [pt for pt in cal if abs(pt[0] - raw) > 0.005]
        cal.append([round(raw, 4), self.cal_value.value() / 100])
        self.c.changed()
        self.refresh_calibration()

    def reset_calibration(self):
        self.c.cfg["my_hp"]["calibration"] = []
        self.c.changed()
        self.refresh_calibration()

    def refresh_calibration(self):
        pts = sorted(self.c.cfg["my_hp"].get("calibration", []))
        self.cal_label.setText("calibrated at: " + (", ".join(f"{b:.0%}" for _, b in pts) or "nothing yet (raw fill)"))

    # party
    def send_chat(self, text=None):
        typed = text is None or text is False
        err = self.c.engine.party_link.send_chat(self.chat_input.text() if typed else text)
        self.chat_info.setText(err or "")
        if not err and typed:
            self.chat_input.clear()

    def refresh_chat(self):
        import html
        chat = list(self.c.engine.party_link.chat)
        key = (len(chat), chat[-1][0] if chat else 0)
        if key == self._chat_key:
            return
        self._chat_key = key
        lines = []
        for t, name, text, mine in chat:
            colour = "#2de2e6" if mine else "#f3e600"
            lines.append(f"<span style='color:#5c6b7a'>{time.strftime('%H:%M', time.localtime(t))}</span> "
                         f"<b style='color:{colour}'>{html.escape('YOU' if mine else name)}&gt;</b> "
                         f"<span style='color:#e6e8ee'>{html.escape(text)}</span>")
        self.chat_log.setHtml("<br>".join(lines) or "<span style='color:#5c6b7a'>no messages yet</span>")
        bar = self.chat_log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def new_code(self):
        self.code_edit.setText(party.new_code())
        self.c.cfg["party"]["code"] = self.code_edit.text()
        self.c.changed()

    # prompts
    def set_prompt_region(self, i, v):
        region = self.c.cfg["prompts"].get("region") or [0, 0, 1920, 1080]
        region[i] = v
        self.c.cfg["prompts"]["region"] = region
        self.c.changed()

    def pick_prompt_region(self):
        def picked(res, img, origin):
            if res and "region" in res:
                self.c.cfg["prompts"]["region"] = res["region"]
                for s, v in zip(self.prompt_spins, res["region"]):
                    s.blockSignals(True)
                    s.setValue(v)
                    s.blockSignals(False)
                self.c.changed()
        self.c.pick("area", picked)

    def tick(self):
        eng = self.c.engine
        if eng.my_hp is None:
            self.hp_now.setText("can't see your health bar (go in game, or Pick area)")
        else:
            self.hp_now.setText(f"<b>{eng.my_hp}%</b>   (raw fill {eng.my_hp_raw:.3f})")
        self.link_status.setText(eng.party_link.status)
        self.refresh_chat()
        self.voice_status.setText(eng.voice.status + ("  -  LISTENING" if eng.voice.listening() else ""))
        seen = eng.prompt_seen
        if not self.c.cfg["prompts"].get("enabled"):
            self.prompt_now.setText("off")
        elif not (eng.active and eng.game_focused()):
            self.prompt_now.setText("waiting for macros ON + game focused")
        elif seen:
            self.prompt_now.setText(f"best match {seen[0]} {seen[1]:.2f}{' (fake)' if seen[2] else ''}"
                                    f"  -  pressed {eng.prompt_presses}")
        else:
            self.prompt_now.setText(f"watching  -  pressed {eng.prompt_presses}")


class BuilderPage(Page):
    title = "Builder"
    code = "BUILDER 101"
    subtitle = ("Paste your deepwoken.co build. Its talents show top-right on screen, and when a talent card you're "
                "offered is in your build you get a notification.")

    def __init__(self, controller):
        super().__init__(controller)
        b = self.c.cfg["builder"]
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        page = QVBoxLayout(holder)
        page.setContentsMargins(0, 0, 14, 0)
        scroll.setWidget(holder)
        self.body.addWidget(scroll, 1)
        box, form = form_group("Elgansito Builder")
        self.url = QLineEdit(b.get("url", ""))
        self.url.setPlaceholderText("https://deepwoken.co/builder?id=...")
        load = QPushButton("Load build")
        load.setObjectName("Primary")
        load.clicked.connect(self.load)
        site = QPushButton("Open deepwoken.co builder")
        site.clicked.connect(lambda: __import__("webbrowser").open(self.url.text().strip() or "https://deepwoken.co/builder"))
        form.addRow("Build link", row(self.url, load, site, stretch=False))
        self.status = hint("")
        form.addRow("", self.status)
        show = QPushButton("Show BUILDER 101 on screen")
        show.clicked.connect(lambda: self.c.show_overlay("builder"))
        rows = spin(b.get("max_rows", 12), 3, 40, lambda v: (b.__setitem__("max_rows", v), self.c.changed(apply=False)),
                    " talents shown")
        form.addRow("", row(show, rows))
        auto = QCheckBox("Only show the BUILDER 101 list while talent cards are on screen")
        auto.setChecked(b.get("list_on_cards", True))
        auto.toggled.connect(lambda on: (b.__setitem__("list_on_cards", on), self.c.changed(apply=False)))
        form.addRow("", auto)
        page.addWidget(box)

        box, form = form_group("Talent card alerts")
        watch = QCheckBox("Watch for level-up cards and notify me when one is in my build")
        watch.setChecked(b.get("watch", False))
        watch.toggled.connect(lambda on: (b.__setitem__("watch", on), self.c.changed()))
        form.addRow("", watch)
        glow = QCheckBox("Highlight cards on screen (yellow = in my build)")
        glow.setChecked(b.get("highlight", True))
        glow.toggled.connect(lambda on: (b.__setitem__("highlight", on), self.c.changed(apply=False)))
        form.addRow("", glow)
        red = QCheckBox("Mark talents that aren't in my build red (handy on \"Choose a Talent to Exchange\")")
        red.setChecked(b.get("mark_out", True))
        red.toggled.connect(lambda on: (b.__setitem__("mark_out", on), self.c.changed(apply=False)))
        form.addRow("", red)
        pick = QPushButton("Only look in an area...")
        pick.setToolTip("Optional: drag a box where cards show up. By default the whole game screen is checked.")
        pick.clicked.connect(self.pick_area)
        reset = QPushButton("Whole screen")
        reset.clicked.connect(lambda: (b.pop("cards", None), self.c.changed(), self.fill()))
        self.area = hint("")
        form.addRow("", row(pick, reset, self.area))
        self.seen = QLabel("")
        form.addRow("Right now", self.seen)
        form.addRow(hint("Finds talent cards anywhere on screen: the level-up row and grids like \"Choose a Talent "
                         "to Exchange\". Only 2+ cards side by side count, so inventory tooltips never set it off. "
                         "Each title is read with Windows OCR (offline) and matched to your build; a card is only "
                         "marked red when it clearly reads as a different talent. Notifications are for level up."))
        sync = QPushButton("Sync from my in-game talent list")
        sync.setToolTip("Ticks every talent of your build that's in your in-game talent list.")
        sync.clicked.connect(self.sync_owned)
        form.addRow("", row(sync))
        form.addRow(hint("Open your talent list in game first. This window minimises, and 3 seconds later the "
                         "screen is read once and the talents you already have are ticked, so they stop alerting."))
        page.addWidget(box)

        box = QGroupBox("Talents in the build")
        lay = QVBoxLayout(box)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("search...")
        self.filter.textChanged.connect(self.fill)
        lay.addWidget(self.filter)
        self.list = QListWidget()
        self.list.setMinimumHeight(320)
        self.list.itemChanged.connect(self.ticked)
        lay.addWidget(self.list, 1)
        page.addWidget(box)
        self.fill()

    def load(self):
        b = self.c.cfg["builder"]
        self.status.setText("loading...")
        QApplication.processEvents()
        try:
            build = builder.fetch(self.url.text())
        except Exception as e:
            self.status.setText(f"couldn't load: {e}")
            return
        b.update(url=self.url.text().strip(), name=build["name"], talents=build["talents"], all=build.get("all", []),
                 obtained=[t for t in b.get("obtained", []) if t in build["talents"]])
        self.c.changed()
        self.c.engine.log(f"builder: loaded '{build['name']}' ({len(build['talents'])} talents)")
        self.fill()

    def fill(self):
        b = self.c.cfg["builder"]
        talents, have = b.get("talents", []), set(b.get("obtained", []))
        q = self.filter.text().strip().lower()
        self.list.blockSignals(True)
        self.list.clear()
        from PySide6.QtWidgets import QListWidgetItem
        for t in talents:
            if q and q not in t.lower():
                continue
            item = QListWidgetItem(t)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if t in have else Qt.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if talents:
            self.status.setText(f"{b.get('name', 'Build')}: {len(have)} / {len(talents)} talents ticked as obtained")
        else:
            self.status.setText("no build loaded yet")
        r = b.get("cards")
        self.area.setText("area: {} x {} at ({}, {})".format(r[2], r[3], r[0], r[1]) if r else "whole game screen")

    def ticked(self, item):
        have = self.c.cfg["builder"].setdefault("obtained", [])
        t = item.text()
        if item.checkState() == Qt.Checked and t not in have:
            have.append(t)
        elif item.checkState() != Qt.Checked and t in have:
            have.remove(t)
        self.c.changed()
        self.fill()

    def pick_area(self):
        def picked(res, img, origin):
            if res and "region" in res:
                self.c.cfg["builder"]["cards"] = res["region"]
                self.c.changed()
                self.fill()
        self.c.pick("area", picked)

    def sync_owned(self):
        if not self.c.cfg["builder"].get("talents"):
            self.status.setText("load a build first")
            return
        self.status.setText("open your talent list in game - reading it in 3 seconds...")
        self.c.window.showMinimized()
        self.c.scanning = True  # hides this app's overlays and toasts so they aren't read
        self.c.sync_overlays()
        for t in self.c.notifier.toasts:
            t.hide()
        QTimer.singleShot(3000, self._sync_read)

    def _sync_read(self):
        b = self.c.cfg["builder"]
        try:
            with detect.MSS() as sct:
                box = game_monitor(sct, self.c.cfg.get("game_window", ""), self.c.cfg.get("monitor", 1))
                img = detect.grab(sct, box)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            found = builder.find_talents(servername.run_ocr(255 - gray), b.get("talents", []))
            error = None
        except Exception as e:
            found, error = [], e
        finally:
            self.c.scanning = False
            self.c.sync_overlays()
            self.c.show_main()
        if error:
            self.status.setText(f"couldn't read the screen: {error}")
            return
        have = b.setdefault("obtained", [])
        new = [t for t in found if t not in have]
        have.extend(new)
        self.c.changed()
        self.fill()
        self.status.setText(f"synced: {len(found)} of your build's talents are in your list, {len(new)} newly ticked"
                            if found else "didn't find any of your build's talents - was the talent list open?")

    def tick(self):
        seen = self.c.engine.builder_seen
        self.seen.setText(("on screen: " + ", ".join(seen)) if seen else
                          ("watching" if self.c.cfg["builder"].get("watch") else "off"))


class MusicPage(Page):
    title = "Music"
    code = "AUDIO"
    subtitle = ("Play your own songs (mp3, wav, m4a, or the sound of mp4 clips) while you play, or control Spotify. "
                "Everything plays from files on your PC - nothing is streamed or downloaded.")

    def __init__(self, controller):
        super().__init__(controller)
        m = self.c.cfg["music"]
        box, form = form_group("Now playing")
        self.now = QLabel("nothing")
        self.now.setStyleSheet("font-size: 13pt; font-weight: 700; color: #ffffff;")
        form.addRow(self.now)
        self.prog = QLabel("")
        self.prog.setObjectName("Hint")
        form.addRow(self.prog)
        prev_b, play_b, next_b, stop_b = (QPushButton("⏮"), QPushButton("⏯  PLAY / PAUSE"), QPushButton("⏭"),
                                          QPushButton("■ STOP"))
        play_b.setObjectName("Primary")
        prev_b.clicked.connect(lambda: self.c.music.skip(-1))
        play_b.clicked.connect(self.c.music.toggle)
        next_b.clicked.connect(lambda: self.c.music.skip(1))
        stop_b.clicked.connect(self.c.music.stop)
        vol = QSlider(Qt.Horizontal)
        vol.setRange(0, 100)
        vol.setValue(int(m.get("volume", 60)))
        vol.setFixedWidth(160)
        vol.valueChanged.connect(lambda v: (m.__setitem__("volume", v), self.c.music.set_volume(v),
                                            self.c.changed(apply=False)))
        form.addRow("", row(prev_b, play_b, next_b, stop_b, QLabel("volume"), vol))
        loop = QCheckBox("Loop the playlist")
        loop.setChecked(m.get("loop", True))
        loop.toggled.connect(lambda on: (m.__setitem__("loop", on), self.c.changed(apply=False)))
        shuffle = QCheckBox("Shuffle")
        shuffle.setChecked(m.get("shuffle", False))
        shuffle.toggled.connect(lambda on: (m.__setitem__("shuffle", on), self.c.changed(apply=False)))
        form.addRow("", row(loop, shuffle))
        self.body.addWidget(box)

        box = QGroupBox("Playlist")
        lay = QVBoxLayout(box)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda it: self.c.music.play_index(self.list.row(it)))
        lay.addWidget(self.list, 1)
        add = QPushButton("+ Add songs")
        add.clicked.connect(self.add)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self.remove)
        lay.addWidget(row(add, remove, hint("double-click a song to play it")))
        self.body.addWidget(box, 1)

        box, form = form_group("Spotify")
        self.spot = QLabel("")
        form.addRow("Spotify", self.spot)
        sp_prev, sp_play, sp_next = QPushButton("⏮"), QPushButton("⏯  PLAY / PAUSE"), QPushButton("⏭")
        sp_prev.clicked.connect(lambda: media_key(0xB1))
        sp_play.clicked.connect(lambda: media_key(0xB3))
        sp_next.clicked.connect(lambda: media_key(0xB0))
        form.addRow("", row(sp_prev, sp_play, sp_next))
        form.addRow(hint("Controls the Spotify app (or any player) with your keyboard's media keys, and shows what "
                         "Spotify is playing. Nothing logs in or connects to your account."))
        self.body.addWidget(box)
        self.fill()

    def fill(self):
        self.list.clear()
        for path in self.c.cfg["music"].get("tracks", []):
            self.list.addItem(os.path.splitext(os.path.basename(path))[0])

    def add(self):
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(self, "Add songs", "", audio.AUDIO_TYPES)
        if paths:
            self.c.cfg["music"].setdefault("tracks", []).extend(paths)
            self.c.changed(apply=False)
            self.fill()

    def remove(self):
        tracks = self.c.cfg["music"].get("tracks", [])
        for i in sorted({ix.row() for ix in self.list.selectedIndexes()}, reverse=True):
            if i < len(tracks):
                tracks.pop(i)
        self.c.changed(apply=False)
        self.fill()

    def tick(self):
        mp = self.c.music
        if mp.track.path:
            name = os.path.splitext(os.path.basename(mp.track.path))[0]
            state = mp.track.mode()
            self.now.setText(f"{'▶' if state == 'playing' else '❚❚'}  {name}")
            pos, length = mp.track.position() // 1000, max(mp.track.length() // 1000, 1)
            self.prog.setText(f"{pos // 60}:{pos % 60:02d} / {length // 60}:{length % 60:02d}")
        else:
            self.now.setText("nothing playing")
            self.prog.setText("")
        self.spot.setText(spotify_now_playing() or "not playing (open the Spotify app)")


def media_key(vk):
    """Press a keyboard media key (play/pause 0xB3, next 0xB0, previous 0xB1)."""
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0x1, 0)
    user32.keybd_event(vk, 0, 0x1 | 0x2, 0)


def spotify_now_playing():
    """'Artist - Song' from the Spotify window title (it shows just 'Spotify' when paused)."""
    titles = []
    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32 = ctypes.windll.user32

    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            titles.append((buf.value, pid.value))
        return True
    user32.EnumWindows(proto(cb), 0)
    spotify_pids = {pid for t, pid in titles if t.startswith("Spotify")}
    for t, pid in titles:
        if " - " in t and (pid in spotify_pids or _process_name(pid) == "spotify.exe"):
            return t
    return None


def _process_name(pid):
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = ctypes.c_ulong(260)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        k.CloseHandle(ctypes.c_void_p(h))


class MusicPlayer:
    """Playlist on top of audio.Track; advances to the next song when one ends."""

    def __init__(self, controller):
        self.c = controller
        self.track = audio.Track("elgansito_music")
        self.index = -1
        self.timer = QTimer(interval=1000, timeout=self.check)
        self.timer.start()

    def tracks(self):
        return self.c.cfg.get("music", {}).get("tracks", [])

    def volume(self):
        return int(self.c.cfg.get("music", {}).get("volume", 60))

    def play_index(self, i):
        tracks = self.tracks()
        if not tracks:
            return
        self.index = i % len(tracks)
        try:
            self.track.open(tracks[self.index])
            self.track.play(self.volume())
            self.c.engine.log(f"music: playing {os.path.basename(tracks[self.index])}")
        except Exception as e:
            self.c.engine.log(f"music: can't play {os.path.basename(tracks[self.index])} ({e})")

    def toggle(self):
        mode = self.track.mode()
        if mode == "playing":
            self.track.pause()
        elif mode == "paused":
            self.track.resume()
        else:
            self.play_index(max(self.index, 0))

    def skip(self, d):
        tracks = self.tracks()
        if not tracks:
            return
        if self.c.cfg["music"].get("shuffle") and d > 0:
            import random
            self.play_index(random.randrange(len(tracks)))
        else:
            self.play_index(self.index + d)

    def stop(self):
        self.track.close()

    def set_volume(self, v):
        self.track.set_volume(v)

    def check(self):
        if self.track.path and self.track.mode() == "stopped":
            last = self.index >= len(self.tracks()) - 1
            if last and not self.c.cfg["music"].get("loop", True):
                self.track.close()
            else:
                self.skip(1)


class SettingsPage(Page):
    title = "Settings"
    code = "SYSTEM"

    def __init__(self, controller):
        super().__init__(controller)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        inner = QVBoxLayout(holder)
        inner.setContentsMargins(0, 0, 14, 0)
        inner.setSpacing(10)
        scroll.setWidget(holder)
        self.body.addWidget(scroll, 1)
        self.body = inner  # the groups below go inside the scroll area
        cfg = self.c.cfg
        ch = self.c.changed
        box, form = form_group("Game")
        self.game = QLineEdit(cfg.get("game_window", ""))
        self.game.setPlaceholderText("leave empty to work in every window")
        self.game.editingFinished.connect(lambda: (cfg.__setitem__("game_window", self.game.text().strip()), ch()))
        grab = QPushButton("Use the next window I click")
        grab.clicked.connect(self.grab_window)
        self.grab_lbl = hint("")
        form.addRow("Window title", self.game)
        form.addRow("", row(grab, self.grab_lbl))
        form.addRow(hint("Cooldowns and macros only work while this window is focused, so typing in Discord "
                         "or your browser never triggers anything. Roblox's game window is called \"Roblox\"."))
        self.body.addWidget(box)

        box, form = form_group("Hotkeys")
        form.addRow("Macros on / off", KeyButton(self.c, cfg.get("toggle_key", "f6"),
                                                 lambda k: (cfg.__setitem__("toggle_key", k), ch())))
        form.addRow("Log cursor position + colour", KeyButton(self.c, cfg.get("pick_key", "f7"),
                                                              lambda k: (cfg.__setitem__("pick_key", k), ch())))
        form.addRow("Hide / show the app", KeyButton(self.c, cfg.get("hide_key", "f8"),
                                                     lambda k: (cfg.__setitem__("hide_key", k), ch())))
        if not engine_mod.LITE:
            form.addRow("Party message box", KeyButton(self.c, cfg.get("chat_key", "f4"),
                                                       lambda k: (cfg.__setitem__("chat_key", k), ch())))
        start = QCheckBox("Start with macros ON")
        start.setChecked(cfg.get("start_active", False))
        start.toggled.connect(lambda on: (cfg.__setitem__("start_active", on), ch()))
        form.addRow("", start)
        self.body.addWidget(box)

        wc = cfg.setdefault("wisp", {})
        box, form = form_group("Auto wisp (ritual letters)", True, wc.get("enabled", False),
                               lambda on: (wc.__setitem__("enabled", on), ch()))
        form.addRow(hint("When the ritual box of letters (C / X / V / Z) comes up while casting, the letters are "
                         "typed for you: the leftmost one, then the next as soon as the queue moves on. White and "
                         "purple letters are both pressed. Works while macros are ON and Roblox is focused."))
        form.addRow("Delay before each key", spin(wc.get("delay_ms", 0), 0, 1000,
                                                  lambda v: (wc.__setitem__("delay_ms", v), ch()), " ms", 5))
        form.addRow("Hold each key", spin(wc.get("hold_ms", 40), 10, 200,
                                          lambda v: (wc.__setitem__("hold_ms", v), ch()), " ms", 5))
        form.addRow("Press again if stuck after", spin(wc.get("retry_ms", 350), 100, 2000,
                                                       lambda v: (wc.__setitem__("retry_ms", v), ch()), " ms", 25))
        safe = QCheckBox("Read each letter twice before pressing (safer; turn off for the fastest typing)")
        safe.setChecked(wc.get("confirm", True))
        safe.toggled.connect(lambda on: (wc.__setitem__("confirm", on), ch()))
        form.addRow("", safe)
        self.wisp_now = QLabel()
        form.addRow("Right now", self.wisp_now)
        form.addRow(hint("Too slow? Lower the delay and the hold. Missing letters (lag)? Raise the hold a little. "
                         "Defaults are for a 1920x1080 screen."))
        self.body.addWidget(box)

        box, form = form_group("Mouse buttons -> keys")
        form.addRow(hint("Make a mouse button press a key in game, e.g. the side buttons as 9 and 0. The key is held "
                         "as long as the button is, and the game never sees the click. Works while macros are ON "
                         "and Roblox is focused. A remapped button no longer triggers macros set to it (like Spam F "
                         "on side button 2)."))
        buttons = {"mouse_x1": "Side button 1 (back)", "mouse_x2": "Side button 2 (forward)",
                   "mouse_middle": "Middle button"}
        remaps = cfg.setdefault("remaps", [])
        while len(remaps) < 3:
            remaps.append({"button": "mouse_middle", "key": "", "enabled": False})

        def set_key(r, k, btn):
            if k.startswith("mouse_"):
                btn.setText(nice_key(r.get("key", "")))  # a key, not another mouse button
                btn.value = r.get("key", "")
                return
            r["key"] = k
            ch()
        for r in remaps:
            on = QCheckBox()
            on.setChecked(r.get("enabled", False))
            on.toggled.connect(lambda v, r=r: (r.__setitem__("enabled", v), ch()))
            which = combo(buttons, r.get("button", "mouse_x1"), lambda v, r=r: (r.__setitem__("button", v), ch()))
            key = KeyButton(self.c, r.get("key", ""), None)
            key.on_change = lambda k, r=r, key=key: set_key(r, k, key)
            form.addRow(row(on, which, QLabel("presses"), key))
        self.body.addWidget(box)

        box, form = form_group("Screen")
        form.addRow("Monitor", spin(cfg.get("monitor", 1), 1, 8, lambda v: (cfg.__setitem__("monitor", v), ch())))
        form.addRow("Screen rule scan every", spin(cfg.get("scan_interval_ms", 50), 5, 2000,
                                                   lambda v: (cfg.__setitem__("scan_interval_ms", v), ch()), " ms", 5))
        folder = QPushButton("Open app folder")
        folder.clicked.connect(lambda: os.startfile(config.HERE))
        form.addRow("", folder)
        self.body.addWidget(box)

        box, form = form_group("Profiles")
        form.addRow(hint("Each profile is a whole set of settings: bars, macros, overlays, party. The one you're on "
                         "saves as you change things; switch with the box at the bottom of the sidebar."))
        self.profiles = QListWidget()
        self.profiles.setFixedHeight(120)
        form.addRow(self.profiles)
        new = QPushButton("New from current")
        new.clicked.connect(lambda: self.profile_action("new"))
        load = QPushButton("Switch to selected")
        load.setObjectName("Primary")
        load.clicked.connect(lambda: self.profile_action("switch"))
        rename = QPushButton("Rename")
        rename.clicked.connect(lambda: self.profile_action("rename"))
        delete = QPushButton("Delete")
        delete.setObjectName("Danger")
        delete.clicked.connect(lambda: self.profile_action("delete"))
        form.addRow("", row(load, new, rename, delete))
        self.body.addWidget(box)
        self.refresh_profiles()

        box, form = form_group("Your settings")
        form.addRow(hint(f"Everything saves automatically to {config.CONFIG_PATH}. That folder isn't touched by "
                         "updates, so a new download or re-unzipping keeps all your macros, bars and party "
                         "settings."))
        export = QPushButton("Export settings")
        export.clicked.connect(self.export_settings)
        imp = QPushButton("Import settings")
        imp.clicked.connect(self.import_settings)
        open_data = QPushButton("Open settings folder")
        open_data.clicked.connect(lambda: (os.makedirs(config.DATA_DIR, exist_ok=True), os.startfile(config.DATA_DIR)))
        self.settings_lbl = hint("")
        form.addRow("", row(export, imp, open_data, self.settings_lbl))
        self.body.addWidget(box)

        box, form = form_group("Performance")
        perf = combo({"light": "Light - least CPU, a bit slower to react",
                      "balanced": "Balanced (recommended)",
                      "max": "Max - fastest reactions, most CPU"}, cfg.get("performance", "balanced"),
                     lambda v: (cfg.__setitem__("performance", v), ch(apply=False)))
        form.addRow("Usage", perf)
        form.addRow(hint("How often the app reads the screen and redraws overlays. Text on bars, skins, Builder "
                         "alerts, Party HP and key prompts all have their own on/off switches too - anything "
                         "switched off costs nothing. For the lightest version, use Elgansito Lite."))
        self.body.addWidget(box)

        nt = cfg.setdefault("notify", {})
        box, form = form_group("Notifications", True, nt.get("enabled", True),
                               lambda on: (nt.__setitem__("enabled", on), ch(apply=False)))
        form.addRow(hint("Pop-ups in the top-right corner: Builder 101 talents, a friend under 30% HP, macros "
                         "arming when Deepwoken is detected."))
        snd_on = QCheckBox("Play a sound")
        snd_on.setChecked(nt.get("sound_on", True))
        snd_on.toggled.connect(lambda on: (nt.__setitem__("sound_on", on), ch(apply=False)))
        pick_snd = QPushButton("Choose sound file")
        pick_snd.clicked.connect(lambda: self.pick_notify_file("sound"))
        pick_img = QPushButton("Choose picture")
        pick_img.clicked.connect(lambda: self.pick_notify_file("image"))
        default = QPushButton("Defaults")
        default.clicked.connect(lambda: (nt.update(sound="", image=""), ch(apply=False), self.notify_lbl.setText(self.notify_text())))
        test = QPushButton("Test")
        test.setObjectName("Primary")
        test.clicked.connect(lambda: self.c.notifier.show("BUILDER 101", "Blade Dancer is in your build - take it!", "builder"))
        form.addRow("", row(snd_on, pick_snd, pick_img, default, test))
        nvol = spin(nt.get("volume", 70), 0, 100, lambda v: (nt.__setitem__("volume", v), ch(apply=False)), " % volume", 5)
        secs = spin(nt.get("seconds", 4), 1, 20, lambda v: (nt.__setitem__("seconds", v), ch(apply=False)), " s on screen")
        low = QCheckBox("Friend under 30% HP")
        low.setChecked(nt.get("party_low", True))
        low.toggled.connect(lambda on: (nt.__setitem__("party_low", on), ch(apply=False)))
        form.addRow("", row(nvol, secs, low))
        self.notify_lbl = hint(self.notify_text())
        form.addRow("", self.notify_lbl)
        self.body.addWidget(box)

        ui = cfg.setdefault("ui", {"click_sound": True, "volume": 60, "animations": True})
        box, form = form_group("Interface")
        snd = QCheckBox("Click sound")
        snd.setChecked(ui.get("click_sound", True))
        snd.toggled.connect(lambda on: (ui.__setitem__("click_sound", on), ch()))
        vol = spin(ui.get("volume", 60), 0, 100, lambda v: (ui.__setitem__("volume", v), ch()), " % volume", 5)
        anim = QCheckBox("Animations")
        anim.setChecked(ui.get("animations", True))
        anim.toggled.connect(lambda on: (ui.__setitem__("animations", on), ch()))
        form.addRow("", row(snd, vol, anim))
        name = QLineEdit(ui.get("display_name", "ELGANSITO"))
        name.editingFinished.connect(lambda: (ui.__setitem__("display_name", name.text().strip()), ch(apply=False)))
        tagline = QLineEdit(ui.get("tagline", "EDGERUNNER // LV.20"))
        tagline.editingFinished.connect(lambda: (ui.__setitem__("tagline", tagline.text().strip()), ch(apply=False)))
        form.addRow("Name / tagline", row(name, tagline, stretch=False))
        bg_pick = QPushButton("Choose background image")
        bg_pick.clicked.connect(self.pick_background)
        bg_clear = QPushButton("No background")
        bg_clear.clicked.connect(lambda: (ui.__setitem__("background", ""), ch(apply=False), self.c.rebuild_window()))
        dim = QSlider(Qt.Horizontal)
        dim.setRange(20, 95)
        dim.setValue(int(ui.get("background_dim", 70)))
        dim.setFixedWidth(160)
        dim.valueChanged.connect(lambda v: (ui.__setitem__("background_dim", v), ch(apply=False),
                                            self.window().centralWidget().update()))
        form.addRow("Background", row(bg_pick, bg_clear, QLabel("darken"), dim))
        form.addRow(hint("Name, tagline and picture show in the sidebar; click the picture there to change it. "
                         "Name and tagline update next time you open the app or switch profile."))
        self.body.addWidget(box)

        icfg = cfg.setdefault("cd_icons", {"enabled": True, "x": [933, 951, 969, 987], "y": [928, 962]})
        box, form = form_group("Deepwoken cooldown bubbles", True, icfg.get("enabled", True),
                               lambda on: (icfg.__setitem__("enabled", on), ch()))
        form.addRow(hint("The small round icons under your health bar go dim while a move is on cooldown. "
                         "Bars set to a bubble (Cooldowns > Game bubble) follow them: they only start when the "
                         "game really did the move, and refill the moment the game says it's ready again."))
        self.icon_now = QLabel()
        form.addRow("Right now", self.icon_now)
        pick = QPushButton("Pick the bubbles")
        pick.setToolTip("Drag a box tightly around the 4 bubbles (only needed if your screen isn't 1920x1080).")
        pick.clicked.connect(self.pick_icons)
        form.addRow("", pick)
        self.body.addWidget(box)
        self.body.addStretch(1)
        self.grab_timer = QTimer(self, interval=100, timeout=self.poll_window)

    def refresh_profiles(self):
        self.profiles.clear()
        active = config.active_profile()
        for name in config.list_profiles():
            self.profiles.addItem(f"{name}   (active)" if name == active else name)

    def selected_profile(self):
        item = self.profiles.currentItem()
        return item.text().replace("   (active)", "") if item else None

    def profile_action(self, action):
        from PySide6.QtWidgets import QMessageBox
        name = self.selected_profile()
        if action == "new":
            new, ok = QInputDialog.getText(self, "New profile", "Name for a copy of the current settings:")
            if ok and new.strip():
                self.c.new_profile(new.strip())
            return
        if not name:
            QMessageBox.information(self, "Profiles", "Pick a profile in the list first.")
            return
        try:
            if action == "switch":
                self.c.switch_profile(name)
            elif action == "rename":
                new, ok = QInputDialog.getText(self, "Rename profile", "New name:", text=name)
                if ok and new.strip():
                    config.rename_profile(name, new.strip())
                    self.c.rebuild_window()
            elif action == "delete":
                if QMessageBox.question(self, "Delete profile", f"Delete the profile '{name}'?") == QMessageBox.Yes:
                    config.delete_profile(name)
                    self.c.rebuild_window()
        except ValueError as e:
            QMessageBox.warning(self, "Profiles", str(e))

    def notify_text(self):
        nt = self.c.cfg.get("notify", {})
        return "sound: {}   picture: {}".format(os.path.basename(nt.get("sound", "")) or "built-in chime",
                                                os.path.basename(nt.get("image", "")) or "none")

    def pick_notify_file(self, which):
        from PySide6.QtWidgets import QFileDialog
        kinds = audio.AUDIO_TYPES if which == "sound" else "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
        path, _ = QFileDialog.getOpenFileName(self, f"Notification {which}", "", kinds)
        if path:
            self.c.cfg["notify"][which] = self.c.keep_file(path, f"notify_{which}")
            self.c.changed(apply=False)
            self.notify_lbl.setText(self.notify_text())

    def pick_background(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Choose a background image", "",
                                              "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.c.cfg["ui"]["background"] = self.c.keep_file(path, "background")
            self.c.changed(apply=False)
            self.c.rebuild_window()

    def export_settings(self):
        from PySide6.QtWidgets import QFileDialog
        self.c.flush()
        path, _ = QFileDialog.getSaveFileName(self, "Export settings", "elgansito-settings.json", "JSON (*.json)")
        if path:
            config.export(self.c.cfg, path)
            self.settings_lbl.setText(f"saved {os.path.basename(path)}")

    def import_settings(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(self, "Import settings", "", "JSON (*.json);;All files (*)")
        if not path:
            return
        try:
            config.import_file(path)
        except Exception as e:
            self.settings_lbl.setText(f"couldn't import: {e}")
            return
        QMessageBox.information(self, "Settings imported", "Settings imported. The app will restart to load them.")
        self.c.restart()

    def pick_icons(self):
        def picked(res, img, origin):
            if res and "region" in res:
                x, y, w, h = res["region"]
                self.c.cfg["cd_icons"]["x"] = [int(x + w * (2 * i + 1) / 8) for i in range(4)]
                self.c.cfg["cd_icons"]["y"] = [y - 6, y + h + 6]
                self.c.changed()
        self.c.pick("area", picked)

    def tick(self):
        if not hasattr(self, "icon_now"):
            return
        self.wisp_now.setText(self.c.engine.wisp_state)
        states = getattr(self.c.engine, "icon_states", [])
        if not self.c.cfg.get("cd_icons", {}).get("enabled", True):
            self.icon_now.setText("off")
        elif not states:
            self.icon_now.setText("waiting for the game window")
        else:
            names = {"ready": "ready", "cooling": "cooling", None: "?"}
            self.icon_now.setText("   ".join(f"{i + 1}: {names[s]}" for i, s in enumerate(states)))

    def grab_window(self):
        self.own = int(self.window().winId())
        self.grab_lbl.setText("click the game window...")
        self.grab_timer.start()

    def poll_window(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd and hwnd != self.own:
            self.grab_timer.stop()
            title = engine_mod.foreground_title().strip()
            self.game.setText(title)
            self.c.cfg["game_window"] = title
            self.c.changed()
            self.grab_lbl.setText(f"set to \"{title}\"")
            self.c.show_main()


class RobloxPage(Page):
    title = "Roblox"
    code = "LAUNCH"
    subtitle = ("Works with Froststrap, Bloxstrap and Fishstrap: knows which game you're in, turns macros on in "
                "Deepwoken, and edits your FastFlags.")

    def __init__(self, controller):
        super().__init__(controller)
        rb = self.c.cfg["roblox"]
        ch = self.c.changed
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 14, 0)
        scroll.setWidget(holder)
        self.body.addWidget(scroll, 1)
        lay.addWidget(uifx.Banner())

        box, form = form_group("Game detection")
        self.status = QLabel()
        form.addRow("Right now", self.status)
        auto = QCheckBox("Turn macros ON when I join one of these games, OFF when I leave")
        auto.setChecked(rb.get("auto_enable", True))
        auto.toggled.connect(lambda on: (rb.__setitem__("auto_enable", on), ch()))
        form.addRow("", auto)
        self.games = QListWidget()
        self.games.setFixedHeight(90)
        form.addRow("Games", self.games)
        add = QPushButton("Add the game I'm in now")
        add.clicked.connect(self.add_current)
        remove = QPushButton("Remove")
        remove.clicked.connect(self.remove_game)
        form.addRow("", row(add, remove))
        self.launcher = QComboBox()
        for name, exe in fastflags.launchers():
            self.launcher.addItem(name, exe)
        self.launcher.addItem("Windows default (roblox:// link)", "link")
        saved = rb.get("launcher", "")
        if saved and self.launcher.findData(saved) >= 0:
            self.launcher.setCurrentIndex(self.launcher.findData(saved))
        self.launcher.currentIndexChanged.connect(
            lambda _: (rb.__setitem__("launcher", self.launcher.currentData()), ch(apply=False)))
        launch = QPushButton("Launch Deepwoken")
        launch.setObjectName("Primary")
        launch.clicked.connect(lambda: self.launch(config.DEEPWOKEN_PLACE))
        roblox = QPushButton("Launch Roblox")
        roblox.clicked.connect(lambda: self.launch(None))
        self.menu_btn = QPushButton("Open settings")
        self.menu_btn.clicked.connect(lambda: fastflags.open_menu(self.launcher.currentData()))
        self.menu_btn.setEnabled(self.launcher.currentData() != "link")
        self.launcher.currentIndexChanged.connect(lambda _: self.menu_btn.setEnabled(self.launcher.currentData() != "link"))
        form.addRow("Launch with", row(self.launcher, launch, roblox, self.menu_btn))
        start = QCheckBox("Start Elgansito Demolisher Macro with Windows (so it's ready whenever you play)")
        start.setChecked(rb.get("start_with_windows", False))
        start.toggled.connect(self.set_start)
        form.addRow("", start)
        lay.addWidget(box)

        box, form = form_group("Get a bootstrapper")
        form.addRow(hint("Opens the official download page in your browser. Froststrap v1.5.0 is the version "
                         "these presets were made with."))
        buttons = []
        for name, url in fastflags.DOWNLOADS.items():
            b = QPushButton(f"Download {name}")
            b.clicked.connect(lambda _, u=url: __import__("webbrowser").open(u))
            buttons.append(b)
        form.addRow("", row(*buttons))
        lay.addWidget(box)

        box, form = form_group("FastFlags")
        form.addRow(hint("These go into the same file your bootstrapper uses, so they apply the next time Roblox "
                         "starts. Roblox ignores flags that aren't on its allowlist, so some may do nothing."))
        self.target = QComboBox()
        for label, path in fastflags.targets():
            self.target.addItem(label, path)
        saved = rb.get("fastflags_file")
        if saved and self.target.findData(saved) >= 0:
            self.target.setCurrentIndex(self.target.findData(saved))
        self.target.currentIndexChanged.connect(self.load_flags)
        form.addRow("Write to", self.target)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Flag", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(260)
        self.table.setStyleSheet("QTableWidget { background: #1b1f29; border: 1px solid #2e3445; border-radius: 7px; "
                                 "gridline-color: #262b38; } QHeaderView::section { background: #171a21; "
                                 "border: none; padding: 6px; color: #aab2c3; }")
        self.table.itemChanged.connect(lambda _: self.mark_dirty())
        form.addRow(self.table)
        add_flag = QPushButton("+ Add flag")
        add_flag.clicked.connect(lambda: self.add_flag("", ""))
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self.delete_flags)
        paste = QPushButton("Paste JSON")
        paste.clicked.connect(self.paste_json)
        self.preset = QComboBox()
        for name in fastflags.PRESETS:
            self.preset.addItem(name)
        add_preset = QPushButton("Add preset")
        add_preset.clicked.connect(lambda: self.add_flag(*fastflags.PRESETS[self.preset.currentText()]))
        form.addRow("", row(add_flag, delete, paste, self.preset, add_preset))
        rb = self.c.cfg["roblox"]
        self.flag_set = QComboBox()
        for name in fastflags.preset_sets():
            self.flag_set.addItem(name)
        load_set = QPushButton("Load into table")
        load_set.setToolTip("Replaces the table with this list; press Save flags to write it")
        load_set.clicked.connect(self.load_flag_set)
        form.addRow("Elgansito presets", row(self.flag_set, load_set))
        auto = QCheckBox("Add the chosen preset to my flags each time I launch Roblox from this app")
        auto.setChecked(bool(rb.get("auto_flags")))
        auto.toggled.connect(lambda on: (rb.__setitem__("auto_flags", self.flag_set.currentText() if on else ""),
                                         self.c.changed(apply=False)))
        form.addRow("", auto)
        copy_all = QPushButton("Copy all")
        copy_all.setToolTip("Copies your flags as JSON - send it to a friend, they press Paste JSON")
        copy_all.clicked.connect(lambda: self.copy_flags(selected_only=False))
        copy_sel = QPushButton("Copy selected")
        copy_sel.clicked.connect(lambda: self.copy_flags(selected_only=True))
        save_file = QPushButton("Save to file")
        save_file.clicked.connect(self.export_flags)
        load_file = QPushButton("Load from file")
        load_file.clicked.connect(self.import_flags)
        form.addRow("Share", row(copy_all, copy_sel, save_file, load_file))
        save = QPushButton("Save flags")
        save.setObjectName("Primary")
        save.clicked.connect(self.save_flags)
        reload = QPushButton("Reload")
        reload.clicked.connect(self.load_flags)
        self.flag_status = hint("")
        form.addRow("", row(save, reload, self.flag_status))
        lay.addWidget(box)
        lay.addStretch(1)
        self.refresh_games()
        self.load_flags()

    def refresh_games(self):
        self.games.clear()
        for g in self.c.cfg["roblox"]["games"]:
            self.games.addItem(f"{g['name']}   (universe {g['universe_id']})")

    def add_current(self):
        eng = self.c.engine
        if not eng.universe_id:
            self.status.setText("not in a game - join it in Roblox first")
            return
        games = self.c.cfg["roblox"]["games"]
        if any(g["universe_id"] == eng.universe_id for g in games):
            return
        name, ok = QInputDialog.getText(self, "Add game", "Name for this game:", text=f"Place {eng.place_id}")
        if ok and name.strip():
            games.append({"name": name.strip(), "universe_id": eng.universe_id})
            self.c.changed()
            self.refresh_games()

    def remove_game(self):
        i = self.games.currentRow()
        if 0 <= i < len(self.c.cfg["roblox"]["games"]):
            self.c.cfg["roblox"]["games"].pop(i)
            self.c.changed()
            self.refresh_games()

    def load_flag_set(self):
        flags = fastflags.preset_sets().get(self.flag_set.currentText(), {})
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for k, v in flags.items():
            self._row(k, v)
        self.table.blockSignals(False)
        self.flag_status.setText(f"loaded {len(flags)} flags from the preset - press Save flags to apply")

    def launch(self, place_id):
        exe = self.launcher.currentData()
        preset = self.c.cfg["roblox"].get("auto_flags")
        if preset and self.path():
            try:
                n = fastflags.merge_into(self.path(), fastflags.preset_sets().get(preset, {}))
                self.c.engine.log(f"added {n} flags from '{preset}' before launching")
            except Exception as e:
                self.c.engine.log(f"couldn't add flags before launching: {e}")
        try:
            if exe != "link":
                fastflags.launch(exe, place_id)
            else:
                os.startfile(f"roblox://experiences/start?placeId={place_id}" if place_id else "roblox://")
            self.c.engine.log(f"launching {'Deepwoken' if place_id else 'Roblox'} with {self.launcher.currentText()}")
        except Exception as e:
            self.status.setText(f"couldn't launch: {e}")

    def set_start(self, on):
        try:
            fastflags.set_start_with_windows(on)
            self.c.cfg["roblox"]["start_with_windows"] = on
            self.c.changed(apply=False)
        except Exception as e:
            self.status.setText(f"couldn't change startup: {e}")

    def tick(self):
        eng = self.c.engine
        if eng.universe_id:
            game = eng.current_game() or "a game not in the list"
            text = f"in <b>{game}</b> (place {eng.place_id}, universe {eng.universe_id})"
        else:
            text = "not in a Roblox game"
        self.status.setText(text + ("  -  macros ON" if eng.active else "  -  macros OFF"))

    # fast flags
    def path(self):
        return self.target.currentData()

    def load_flags(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        path = self.path()
        if not path:
            self.flag_status.setText("no Roblox install found")
            self.table.blockSignals(False)
            return
        try:
            for k, v in fastflags.load(path).items():
                self._row(k, v)
            self.flag_status.setText(f"{self.table.rowCount()} flags loaded")
        except Exception as e:
            self.flag_status.setText(f"couldn't read: {e}")
        self.table.blockSignals(False)
        self.c.cfg["roblox"]["fastflags_file"] = path
        self.c.changed(apply=False)

    def _row(self, k, v):
        i = self.table.rowCount()
        self.table.insertRow(i)
        self.table.setItem(i, 0, QTableWidgetItem(k))
        self.table.setItem(i, 1, QTableWidgetItem(v))
        return i

    def add_flag(self, k, v):
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).text() == k and k:
                self.table.item(i, 1).setText(v)
                self.table.selectRow(i)
                return
        i = self._row(k, v)
        self.table.scrollToItem(self.table.item(i, 0))
        if not k:
            self.table.editItem(self.table.item(i, 0))
        self.mark_dirty()

    def delete_flags(self):
        for i in sorted({ix.row() for ix in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(i)
        self.mark_dirty()

    def paste_json(self):
        text, ok = QInputDialog.getMultiLineText(self, "Paste FastFlags", "Paste a JSON object of flags:")
        if not ok or not text.strip():
            return
        try:
            for k, v in fastflags.parse_json(text).items():
                self.add_flag(k, v)
        except Exception as e:
            self.flag_status.setText(f"not valid JSON: {e}")

    def mark_dirty(self):
        self.flag_status.setText("unsaved changes")

    def table_flags(self, selected_only=False):
        rows = sorted({ix.row() for ix in self.table.selectedIndexes()}) if selected_only             else range(self.table.rowCount())
        flags = {}
        for i in rows:
            k = (self.table.item(i, 0).text() if self.table.item(i, 0) else "").strip()
            if k:
                flags[k] = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
        return flags

    def copy_flags(self, selected_only):
        flags = self.table_flags(selected_only)
        if not flags:
            self.flag_status.setText("select some flags first" if selected_only else "no flags to copy")
            return
        QApplication.clipboard().setText(json.dumps(flags, indent=2))
        self.flag_status.setText(f"copied {len(flags)} flags - your friend presses Paste JSON")

    def export_flags(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save FastFlags", "fastflags.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.table_flags(), f, indent=2)
            self.flag_status.setText(f"saved to {os.path.basename(path)}")

    def import_flags(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Load FastFlags", "", "JSON (*.json);;All files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as f:
                flags = fastflags.parse_json(f.read())
            for k, v in flags.items():
                self.add_flag(k, v)
            self.flag_status.setText(f"loaded {len(flags)} flags - press Save flags to apply")
        except Exception as e:
            self.flag_status.setText(f"couldn't load: {e}")

    def save_flags(self):
        flags = {}
        for i in range(self.table.rowCount()):
            k = (self.table.item(i, 0).text() if self.table.item(i, 0) else "").strip()
            if k:
                flags[k] = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
        try:
            fastflags.save(self.path(), flags)
            self.flag_status.setText(f"saved {len(flags)} flags - restart Roblox to apply")
        except Exception as e:
            self.flag_status.setText(f"couldn't save: {e}")


# ---- main window ----------------------------------------------------------------

class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WA_StyledBackground)
        self.win = window
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        brand = QLabel("ELGANSITO  //LITE" if engine_mod.LITE else "DEMOLISHER  //V2")
        brand.setObjectName("Brand")
        brand.setFixedHeight(36)
        lay.addWidget(brand)
        user = (window.c.cfg.get("ui", {}).get("display_name") or "ELGANSITO").upper()
        self.net = QLabel(f"NET_LINK::{user}  //  SYS_OK")
        self.net.setObjectName("NetLink")
        lay.addWidget(self.net)
        lay.addStretch(1)
        for text, name, fn in (("—", "TitleBtn", window.showMinimized), ("✕", "CloseBtn", window.close)):
            b = QPushButton(text)
            b.setObjectName(name)
            b.setFixedHeight(36)
            b.clicked.connect(fn)
            lay.addWidget(b)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.win.windowHandle().startSystemMove()


class Backdrop(QWidget):
    """The window body: dark, or your chosen background image dimmed behind everything."""

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.setObjectName("Body")
        self.image = QPixmap()
        path = controller.cfg.get("ui", {}).get("background", "")
        if path and os.path.exists(path):
            self.image = QPixmap(path)
        self.cache = None

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 14, 19))
        if not self.image.isNull():
            if self.cache is None or self.cache.size() != self.size():
                self.cache = uifx.rounded(self.image, self.width(), self.height(), 0)
            p.drawPixmap(0, 0, self.cache)
            dim = self.c.cfg.get("ui", {}).get("background_dim", 70) / 100
            p.fillRect(self.rect(), QColor(10, 14, 19, int(255 * dim)))
        # faint scanlines for the terminal look
        p.setPen(QColor(255, 255, 255, 6))
        for y in range(0, self.height(), 4):
            p.drawLine(0, y, self.width(), y)


class Pfp(QLabel):
    """Profile picture: click to pick an image from your files."""

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.setObjectName("Pfp")
        self.setFixedSize(64, 64)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to choose your picture")
        self.refresh()

    def refresh(self):
        path = self.c.cfg.get("ui", {}).get("pfp", "")
        pix = QPixmap(path) if path and os.path.exists(path) else QPixmap(uifx.asset("app.png"))
        if pix.isNull():
            self.setText("pfp\nor\nbrowse\nfiles")
        else:
            self.setPixmap(uifx.rounded(pix, 62, 62, 0))

    def mousePressEvent(self, e):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Choose your picture", "",
                                              "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if path:
            self.c.cfg["ui"]["pfp"] = self.c.keep_file(path, "pfp")
            self.c.changed(apply=False)
            self.refresh()


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.setWindowTitle("Elgansito Lite" if engine_mod.LITE else "Elgansito Demolisher Macro")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.resize(1200, 760)
        self.setMinimumSize(900, 580)
        body = Backdrop(controller)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self))
        main = QHBoxLayout()
        main.setSpacing(0)
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setAttribute(Qt.WA_StyledBackground)
        side.setFixedWidth(214)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(12, 12, 12, 12)
        side_lay.setSpacing(3)
        ui = controller.cfg.get("ui", {})
        who = QHBoxLayout()
        who.addWidget(Pfp(controller))
        names = QVBoxLayout()
        names.setSpacing(0)
        side_title = QLabel((ui.get("display_name") or "ELGANSITO").upper())
        side_title.setObjectName("SideTitle")
        tag = QLabel(ui.get("tagline") or "EDGERUNNER // LV.20")
        tag.setObjectName("SideTag")
        names.addStretch(1)
        names.addWidget(side_title)
        names.addWidget(tag)
        names.addStretch(1)
        who.addLayout(names, 1)
        side_lay.addLayout(who)
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: #16232b;")
        side_lay.addSpacing(8)
        side_lay.addWidget(rule)
        side_lay.addSpacing(8)
        self.stack = QStackedWidget()
        self.pages = [cls(controller) for cls in controller.page_classes()]
        group = QButtonGroup(self)
        self.nav = []
        for i, page in enumerate(self.pages):
            page.set_number(i + 1)
            b = QPushButton(f"{i + 1:02d}   {page.title.upper()}")
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _, i=i: self.go(i))
            group.addButton(b)
            self.nav.append(b)
            side_lay.addWidget(b)
            self.stack.addWidget(page)
            if i == 0:
                b.setChecked(True)
        side_lay.addStretch(1)
        side_lay.addWidget(ProfileSwitcher(controller))
        main.addWidget(side)
        main.addWidget(self.stack, 1)
        outer.addLayout(main, 1)
        grip = QSizeGrip(body)
        outer.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)
        self.setCentralWidget(body)
        self.go(0)

    def go(self, i):
        self.nav[i].setChecked(True)
        self.stack.setCurrentIndex(i)
        self.pages[i].shown()
        if self.c.cfg.get("ui", {}).get("animations", True):
            uifx.fade_in(self.pages[i])

    def page(self, cls):
        return next(p for p in self.pages if isinstance(p, cls))

    def closeEvent(self, e):
        if getattr(self, "closing_for_rebuild", False):
            e.accept()
            return
        self.c.quit()
        e.accept()


class ProfileSwitcher(QWidget):
    """Bottom of the sidebar: pick a saved profile to switch to, or save the current settings as a new one."""

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        head = QHBoxLayout()
        cap = QLabel("// PROFILE")
        cap.setObjectName("SideCaption")
        auto = QLabel("AUTOSAVE ●")
        auto.setObjectName("AutoSave")
        head.addWidget(cap)
        head.addStretch(1)
        head.addWidget(auto)
        lay.addLayout(head)
        self.box = QComboBox()
        self.box.setObjectName("ProfileBox")
        self.box.setToolTip("Switch to another saved set of settings")
        self.refresh()
        self.box.currentIndexChanged.connect(self.switch)
        lay.addWidget(self.box)
        save_as = QPushButton("+ SAVE NEW PROFILE")
        save_as.setObjectName("Dashed")
        save_as.clicked.connect(self.save_as)
        lay.addWidget(save_as)

    def refresh(self):
        self.box.blockSignals(True)
        self.box.clear()
        active = config.active_profile()
        for name in config.list_profiles():
            self.box.addItem(name)
        self.box.setCurrentText(active)
        self.box.blockSignals(False)

    def switch(self):
        name = self.box.currentText()
        if name and name != config.active_profile():
            QTimer.singleShot(0, lambda: self.c.switch_profile(name))

    def save_as(self):
        name, ok = QInputDialog.getText(self, "Save as new profile", "Name for these settings (e.g. PvP, Grinding):")
        if ok and name.strip():
            self.c.new_profile(name.strip())


def force_foreground(hwnd):
    """Bring a window to the front even while another app (the game) has focus."""
    user32 = ctypes.windll.user32
    fg = user32.GetForegroundWindow()
    me = ctypes.windll.kernel32.GetCurrentThreadId()
    other = user32.GetWindowThreadProcessId(fg, None)
    attach = bool(other) and other != me
    if attach:
        user32.AttachThreadInput(other, me, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if attach:
        user32.AttachThreadInput(other, me, False)


class QuickChat(QWidget):
    """The party message box the chat hotkey opens over the game: type, Enter sends, Esc closes.
    Focus goes back to the game afterwards."""

    def __init__(self, controller):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.c = controller
        self.return_to = 0
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(480)
        self.setStyleSheet(
            "QLabel#Head { color: #f3e600; font: bold 9pt Consolas; }"
            "QLabel#Info { color: #ff3c5f; font: 8pt Consolas; }"
            "QLineEdit { background: #0a0e13; color: #e6e8ee; border: 1px solid #2de2e6; padding: 6px 8px;"
            "  font: 10pt Bahnschrift; selection-background-color: #2de2e6; }"
            "QPushButton { background: rgba(45,226,230,0.08); color: #2de2e6; border: 1px solid rgba(45,226,230,0.5);"
            "  padding: 4px 8px; font: 8pt Consolas; }"
            "QPushButton:hover { background: #f3e600; color: #0a0e13; border-color: #f3e600; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 14)
        lay.setSpacing(8)
        head = QLabel("// PARTY.MSG &nbsp;&nbsp; <span style='color:#5c6b7a'>ENTER = send &nbsp;&nbsp; ESC = close</span>")
        head.setObjectName("Head")
        lay.addWidget(head)
        self.edit = QLineEdit()
        self.edit.setMaxLength(party.CHAT_MAX)
        self.edit.setPlaceholderText("type a message to your party_")
        self.edit.returnPressed.connect(lambda: self.send())
        lay.addWidget(self.edit)
        self.quick_row = QHBoxLayout()
        self.quick_row.setSpacing(6)
        lay.addLayout(self.quick_row)
        self.info = QLabel("")
        self.info.setObjectName("Info")
        lay.addWidget(self.info)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, c = self.width() - 1, self.height() - 1, 14
        poly = [QPoint(c, 0), QPoint(w, 0), QPoint(w, h - c), QPoint(w - c, h), QPoint(0, h), QPoint(0, c)]
        p.setBrush(QColor(8, 11, 16, 240))
        p.setPen(QPen(QColor(45, 226, 230, 140), 1))
        p.drawPolygon(poly)
        p.setPen(QPen(QColor("#f3e600"), 2))
        p.drawLine(1, c, c, 1)
        p.drawLine(c, 1, 90, 1)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_box()
        else:
            super().keyPressEvent(e)

    def open(self):
        self.return_to = ctypes.windll.user32.GetForegroundWindow()
        while self.quick_row.count():
            item = self.quick_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for text in self.c.cfg.get("party", {}).get("quick", [])[:6]:
            b = QPushButton(text)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, t=text: self.send(t))
            self.quick_row.addWidget(b)
        self.quick_row.addStretch(1)
        self.info.setText("")
        self.adjustSize()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        g = screen.geometry()
        self.move(g.center().x() - self.width() // 2, g.top() + int(g.height() * 0.62))
        self.show()
        self.raise_()
        force_foreground(int(self.winId()))
        self.activateWindow()
        self.edit.setFocus()

    def send(self, text=None):
        err = self.c.engine.party_link.send_chat(self.edit.text() if text is None else text)
        if err:
            self.info.setText(err)
            return
        self.edit.clear()
        self.close_box()

    def close_box(self):
        self.hide()
        if self.return_to:
            force_foreground(self.return_to)


class Controller:
    def __init__(self):
        self.engine = engine_mod.Engine()
        self.cfg = copy.deepcopy(self.engine.cfg)
        self.engine.start()
        self.overlays = {}
        self.snapshots = {}
        self.selected_name = ""
        self.waiting_snapshot = None
        self._needs_apply = False
        self.save_timer = QTimer(singleShot=True, interval=300, timeout=self.flush)
        self.music = MusicPlayer(self)
        self.notifier = notify.Notifier(self)
        self.hidden = False
        self._overlays_on = True   # False while hidden, or while Roblox isn't the focused window
        self.quick_chat = None
        self.highlights = {}       # talent -> CardHighlight around a level-up card
        self.scanning = False      # reading the whole screen: keep this app's windows out of the way
        self.window = MainWindow(self)
        self.frame_timer = QTimer(interval=self.engine.perf("overlay_ms"), timeout=self.frame)
        self.frame_timer.start()
        self.ui_timer = QTimer(interval=100, timeout=self.ui_tick)
        self.ui_timer.start()
        for wid, state in list(self.cfg["widgets"].items()):
            if state.get("visible"):
                self.show_overlay(wid, save=False)

    def current_name(self):
        return self.selected_name or "picture"

    # config
    def changed(self, apply=True):
        self._needs_apply |= apply
        self.save_timer.start()

    def flush(self):
        if self._needs_apply:
            self._needs_apply = False
            self.engine.apply(self.cfg)
        try:
            config.save(self.cfg)
        except Exception as e:
            self.engine.log(f"could not save config: {e}")

    # overlays
    def valid_ids(self):
        return {wid for wid, _, _ in overlays.widget_catalog(self.cfg)}

    def overlay_visible(self, wid):
        ov = self.overlays.get(wid)
        return bool(ov and ov.isVisible())

    def show_overlay(self, wid, pos=None, save=True):
        if wid not in self.valid_ids():
            self.cfg["widgets"].pop(wid, None)
            return
        ov = self.overlays.get(wid)
        if ov is None:
            ov = overlays.make_overlay(self, wid)
            self.overlays[wid] = ov
        state = self.cfg["widgets"].setdefault(wid, {})
        if pos is not None:
            ov.move(pos)
        elif "x" in state:
            ov.move(state["x"], state["y"])
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            ov.move(screen.center() - QPoint(ov.width() // 2, ov.height() // 2))
        state["visible"] = True
        if self._overlays_on:
            ov.show()
        if save:
            self.changed(apply=False)

    def hide_overlay(self, wid):
        ov = self.overlays.pop(wid, None)
        if ov:
            ov.close()
            ov.deleteLater()
        if wid in self.cfg["widgets"]:
            self.cfg["widgets"][wid]["visible"] = False
        self.changed(apply=False)

    def rename_overlay(self, old, new):
        state = self.cfg["widgets"].pop(old, None)
        was_visible = self.overlay_visible(old)
        ov = self.overlays.pop(old, None)
        if ov:
            ov.close()
            ov.deleteLater()
        if state:
            self.cfg["widgets"][new] = state
        if was_visible:
            QTimer.singleShot(400, lambda: self.show_overlay(new))

    def overlay_moved(self, wid, x, y):
        state = self.cfg["widgets"].setdefault(wid, {})
        state["x"], state["y"] = x, y
        self.changed(apply=False)

    def line_up_bars(self):
        """Stack every visible cooldown bar under the top one, left edges lined up."""
        bars = sorted((ov for wid, ov in self.overlays.items() if wid.startswith("cooldown:") and ov.isVisible()),
                      key=lambda o: o.y())
        if not bars:
            return 0
        gap = int(self.cfg["overlay"].get("line_gap", 6))
        x, y = bars[0].x(), bars[0].y()
        for ov in bars:
            ov._snapping = True
            ov.move(x, y)
            ov._snapping = False
            y += ov.height() + gap
        return len(bars)

    def restyle_overlays(self):
        for ov in self.overlays.values():
            ov.apply_style()

    def show_main(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    # screen picking
    def pick(self, mode, callback, source=None):
        def done(result, image, origin):
            self.window.showNormal()
            self.window.raise_()
            callback(result, image, origin)

        def open_picker():
            with detect.MSS() as sct:
                box = game_monitor(sct, self.cfg.get("game_window", ""), self.cfg.get("monitor", 1))
                if source:
                    image, origin = detect.read_image(source[0]), source[1]
                else:
                    image, origin = detect.grab(sct, box), (box["left"], box["top"])
            screen = qt_screen_for({"left": origin[0], "top": origin[1]})
            self.picker = ScreenPicker(image, origin, mode, done, screen)
            self.picker.show_on(screen)

        self.window.showMinimized()
        QTimer.singleShot(350, open_picker)

    # timers
    def frame(self):
        for ov in list(self.overlays.values()) + list(self.highlights.values()):
            if ov.isVisible():
                ov.update()

    def ui_tick(self):
        page = self.window.stack.currentWidget()
        page.tick()
        while self.engine.notifications:
            self.notifier.show(*self.engine.notifications.pop(0))
        if self.engine.hide_requested:
            self.engine.hide_requested = False
            self.toggle_hidden()
        if self.engine.chat_requested:
            self.engine.chat_requested = False
            self.open_quick_chat()
        self.sync_overlays()
        self.sync_highlights()
        # Where this app's windows are (in screen pixels), so screen reading can skip them.
        rects = [w.geometry() for w in list(self.overlays.values()) + list(self.notifier.toasts) if w.isVisible()]
        dpr = QApplication.primaryScreen().devicePixelRatio()
        self.engine.mask_rects = [(int(r.x() * dpr), int(r.y() * dpr), int(r.width() * dpr), int(r.height() * dpr))
                                  for r in rects]
        want = self.engine.perf("overlay_ms")
        if self.frame_timer.interval() != want:
            self.frame_timer.setInterval(want)
        while self.engine.toggled_resets:
            cd_name, r_name, on = self.engine.toggled_resets.pop(0)
            for cd in self.cfg["cooldowns"]:
                for r in cd["resets"]:
                    if cd["name"] == cd_name and r["name"] == r_name:
                        r["enabled"] = on
            self.changed(apply=False)
            if isinstance(page, CooldownsPage):
                page.shown()
        snap = self.engine.snapshot_path
        if snap:
            self.engine.snapshot_path = None
            name, path, origin = snap
            self.snapshots[name] = (path, origin)
            if self.waiting_snapshot:
                self.waiting_snapshot.snapshot_ready(name)

    def toggle_hidden(self):
        """The hide hotkey: tuck the whole app (window and overlays) away, or bring it back."""
        self.hidden = not self.hidden
        if self.hidden:
            self.window.hide()
        else:
            self.window.showNormal()
        self.sync_overlays()
        self.engine.log("app hidden (press the hide key again to bring it back)" if self.hidden else "app shown")

    def overlays_wanted(self):
        """Overlays show while the game (or this app) is the focused window, unless hidden with the hide key."""
        if self.hidden or self.scanning:
            return False
        if not self.cfg["overlay"].get("hide_unfocused", True):
            return True
        return self.engine.game_focused() or engine_mod.foreground_pid() == os.getpid()

    def sync_overlays(self):
        self._overlays_on = on = self.overlays_wanted()
        # BUILDER 101's list can wait for talent cards (it only clutters the screen otherwise).
        b = self.cfg.get("builder", {})
        builder_ok = not b.get("list_on_cards", True) or self.engine.builder_active or self.window.isActiveWindow()
        for wid, ov in self.overlays.items():
            want = on and self.cfg["widgets"].get(wid, {}).get("visible") and (wid != "builder" or builder_ok)
            if want and not ov.isVisible():
                ov.show()
            elif not want and ov.isVisible():
                ov.hide()

    def sync_highlights(self):
        """Glowing frames around talent cards: yellow = in your build, red = not in it."""
        b = self.cfg.get("builder", {})
        on = self._overlays_on and b.get("highlight", True)
        hits = {}
        for kind, name, rect in (self.engine.builder_cards if on else []):
            if kind == "out" and not b.get("mark_out", True):
                continue
            hits[(kind, name, rect[0] // 40, rect[1] // 40)] = rect
        for key in list(self.highlights):
            if key not in hits:
                hl = self.highlights.pop(key)
                hl.close()
                hl.deleteLater()
        dpr = QApplication.primaryScreen().devicePixelRatio()
        for key, (x, y, w, h) in hits.items():
            hl = self.highlights.get(key)
            if hl is None:
                hl = self.highlights[key] = overlays.CardHighlight(key[1], key[0])
            hl.place((int(x / dpr), int(y / dpr), int(w / dpr), int(h / dpr)))
            if not hl.isVisible():
                hl.show()

    def open_quick_chat(self):
        if self.quick_chat is None:
            self.quick_chat = QuickChat(self)
        self.quick_chat.open()

    def page_classes(self):
        if engine_mod.LITE:
            return [HomePage, WidgetsPage, CooldownsPage, MacrosPage, RobloxPage, SettingsPage]
        return [HomePage, WidgetsPage, CooldownsPage, MacrosPage, PartyPage, BuilderPage, MusicPage, RulesPage,
                RobloxPage, SettingsPage]

    def keep_file(self, path, kind):
        """Copy a picked file (picture, sound, skin) into your settings folder so it survives updates."""
        import shutil
        folder = os.path.join(config.DATA_DIR, "files")
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, f"{kind}{os.path.splitext(path)[1].lower()}")
        if os.path.abspath(path) != os.path.abspath(dest):
            shutil.copyfile(path, dest)
        return dest

    def click_sound(self):
        fx = getattr(self, "fx", None)
        ui = self.cfg.get("ui", {})
        if fx and ui.get("click_sound", True):
            try:
                fx.sound.play(int(ui.get("volume", 60)))
            except Exception:
                pass

    # profiles
    def new_profile(self, name, switch=True):
        """Save the current settings as a new profile (and switch to it)."""
        from PySide6.QtWidgets import QMessageBox
        self.flush()
        try:
            name = config.create_profile(name, self.cfg)
        except ValueError as e:
            QMessageBox.warning(self.window, "Profile", str(e))
            return None
        if switch:
            config.set_active_profile(name)
            self.engine.log(f"saved settings as profile '{name}'")
            self.rebuild_window()
        return name

    def switch_profile(self, name):
        """Load another profile's settings live: bars, macros, overlays and every page."""
        from PySide6.QtWidgets import QMessageBox
        self.flush()  # the profile you're leaving keeps its latest changes
        try:
            cfg = config.load_profile(name)
        except Exception as e:
            QMessageBox.warning(self.window, "Profile", f"Couldn't load '{name}': {e}")
            self.rebuild_window()
            return
        config.set_active_profile(name)
        self.cfg = cfg
        config.save(cfg)
        self.engine.apply(cfg)
        for ov in list(self.overlays.values()):
            ov.close()
            ov.deleteLater()
        self.overlays = {}
        for wid, state in list(self.cfg["widgets"].items()):
            if state.get("visible"):
                self.show_overlay(wid, save=False)
        self.engine.log(f"switched to profile '{name}'")
        self.rebuild_window()

    def rebuild_window(self):
        """Recreate the control panel so every page shows the current profile."""
        old = self.window
        geometry, page = old.geometry(), old.stack.currentIndex()
        self.window = MainWindow(self)
        self.window.setGeometry(geometry)
        self.window.show()
        self.window.go(page)
        old.closing_for_rebuild = True
        old.hide()
        old.deleteLater()

    def restart(self):
        from PySide6.QtCore import QProcess
        self.save_timer.stop()       # the imported file is already saved; don't overwrite it
        self._needs_apply = False
        self.engine.stop()
        args = [] if getattr(sys, "frozen", False) else [os.path.abspath(sys.argv[0])]
        QProcess.startDetached(sys.executable, args)
        for ov in list(self.overlays.values()):
            ov.close()
        QApplication.quit()

    def quit(self):
        self.music.stop()
        self.flush()
        self.engine.stop()
        for ov in list(self.overlays.values()):
            ov.close()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    icon = os.path.join(config.HERE, "icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    controller = Controller()
    fx = uifx.ClickFx(controller)
    controller.fx = fx
    app.installEventFilter(fx)
    controller.window.show()
    sys.exit(app.exec())


def run():
    """Entry point that writes crash.log next to the app, since the exe has no console."""
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(os.path.join(config.DATA_DIR, "crash.log"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise


if __name__ == "__main__":
    run()
