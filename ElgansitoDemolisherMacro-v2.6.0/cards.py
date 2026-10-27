"""Finds Deepwoken's talent / mantra cards on screen and reads each card's title.

Works for the row of cards you pick from on level up and for grids like "Choose a Talent to Exchange".
Each card has a light parchment panel (the description) and the title banner a fixed distance above
it, scaled to the card: with W = the panel's width, the title's centre is 0.82 W above the panel's
top. Only two or more cards side by side count, so a single card (the tooltip you get hovering a
talent in your inventory) never triggers anything.
"""
import cv2
import numpy as np

import servername

DEFAULT_AREA = [380, 300, 1160, 340]   # the old fixed level-up row area (1920x1080), kept for old settings
TITLE_UP = 0.82                         # title centre, above the panel top, in panel widths
TITLE_HALF = 0.14                       # half the title banner's height, in panel widths


def find_cards(img):
    """[{'panel': (x, y, w, h), 'title': (x, y, w, h), 'frame': (x, y, w, h)}] for each card, top to bottom,
    left to right. Empty unless at least two cards sit side by side."""
    H, W = img.shape[:2]
    small = cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA)  # half size is plenty to find them
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = ((hsv[..., 2] > 195) & (hsv[..., 1] < 45)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))  # fill in the description text
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    panels = []
    for x, y, w, h, _ in stats[1:]:
        x, y, w, h = x * 2, y * 2, w * 2, h * 2
        if 0.04 * W <= w <= 0.13 * W and 0.25 * w <= h <= 0.82 * w:  # icon squares are ~1:1, panels ~3:2
            panels.append([x, y, w, h])
    if not panels:
        return []
    # Rows: panels whose middles line up. Heavy description text can push a panel's top down,
    # so every panel in a row takes the row's highest typical top.
    panels.sort(key=lambda p: p[1] + p[3] / 2)
    rows, cur = [], [panels[0]]
    for p in panels[1:]:
        if abs((p[1] + p[3] / 2) - (cur[-1][1] + cur[-1][3] / 2)) < 0.5 * p[2]:
            cur.append(p)
        else:
            rows.append(cur)
            cur = [p]
    rows.append(cur)
    rows = [r for r in rows if len(r) >= 2]
    if not rows:
        return []
    # Every card on screen is the same size; rows of smaller blobs (the white icon boxes) aren't cards.
    card_w = max(float(np.median([p[2] for p in r])) for r in rows)
    cards = []
    for row in rows:
        row = [p for p in row if abs(p[2] - card_w) < 0.15 * card_w]
        if len(row) < 2:
            continue
        typical = [p[1] for p in row if 1.3 <= p[2] / max(p[3], 1) <= 1.65] or [p[1] for p in row]
        top = int(np.median(typical))
        for x, _, w, _ in sorted(row):
            cy = top - TITLE_UP * w
            title = (int(x - 0.1 * w), int(cy - TITLE_HALF * w), int(1.2 * w), int(2 * TITLE_HALF * w))
            if title[1] < 0:
                continue  # scrolled half off the top: the title isn't on screen
            frame = (int(x - 0.15 * w), int(top - 0.98 * w), int(1.3 * w), int(1.81 * w))
            cards.append({"panel": (x, top, w, int(0.68 * w)), "title": title, "frame": frame})
    return cards


def read_titles(img, cards):
    """[(title text, card)] for each card; dark text on a light banner, so no inverting."""
    out = []
    for card in cards:
        x, y, w, h = card["title"]
        crop = img[max(y, 0):y + h, max(x, 0):x + w]
        if crop.size == 0:
            continue
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if w < 260:
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        try:
            text = servername.run_ocr(gray).strip()
        except Exception:
            text = ""
        out.append((text, card))
    return out


def read_cards(img):
    """Cards on screen as [(title, card)], or [] when no row of cards is showing."""
    cards = find_cards(img)
    return read_titles(img, cards) if cards else []
