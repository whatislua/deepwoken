"""Everything that runs in the background: input hooks, cooldowns, macros,
screen rules and parry-landed detection. The GUI reads this state and edits
the config; nothing here touches the GUI."""
import copy
import ctypes
import glob
import os
import re
import threading
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
from pynput import keyboard, mouse

import combat
import config
import detect
import hotbar
import hp
import builder
import cards
import hud
import icons
import servername
import voice
import wisp
import party
import prompts
import sendinput

user32 = ctypes.windll.user32


def foreground_title():
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def foreground_pid():
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


def process_elevated(pid=None):
    """True if the process runs as administrator. No access to it counts as elevated."""
    kernel32, advapi32 = ctypes.windll.kernel32, ctypes.windll.advapi32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid) if pid else kernel32.GetCurrentProcess()
    if not handle:
        return True
    token = ctypes.c_void_p()
    try:
        if not advapi32.OpenProcessToken(ctypes.c_void_p(handle), 0x0008, ctypes.byref(token)):
            return True
        elevated, size = ctypes.c_ulong(), ctypes.c_ulong()
        advapi32.GetTokenInformation(token, 20, ctypes.byref(elevated), 4, ctypes.byref(size))
        return bool(elevated.value)
    finally:
        if token:
            kernel32.CloseHandle(token)
        if pid:
            kernel32.CloseHandle(ctypes.c_void_p(handle))


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong), ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong), ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_wchar * 260)]


def roblox_running():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snap = ctypes.c_void_p(kernel32.CreateToolhelp32Snapshot(0x2, 0))
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == "robloxplayerbeta.exe":
                return True
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return False


ROBLOX_LOGS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Roblox", "logs")
JOIN_RE = re.compile(r"game_join_loadtime: placeid:(\d+).*?universeid:(\d+)")
JOB_RE = re.compile(r"! Joining game '([0-9a-f-]{36})'")
MENU_PLACES = {4111023553}         # Deepwoken's start place: the main menu / character select
MENU_BOX = (140, 215, 380, 170)    # "Characters / Combat Training / Tutorial" list on the menu (1920x1080)
LEAVE_RE = re.compile(r"Time to disconnect replication data|DisconnectClientInitiated")

VK_NAMES = {v: k for k, v in sendinput.VK.items()}

LITE = os.environ.get("ELGANSITO_LITE") == "1"

# How hard the background loops work. "light" saves CPU, "max" reacts fastest.
PERF = {
    "light":    {"icons": 0.04, "hp": 0.40, "prompts": 0.08, "landing": 0.02, "server": 8.0, "combat": 1.5,
                 "builder": 2.5, "rules": 2.0, "overlay_ms": 66},
    "balanced": {"icons": 0.015, "hp": 0.15, "prompts": 0.03, "landing": 0.01, "server": 3.0, "combat": 0.5,
                 "builder": 1.5, "rules": 1.0, "overlay_ms": 16},
    "max":      {"icons": 0.008, "hp": 0.10, "prompts": 0.015, "landing": 0.005, "server": 2.0, "combat": 0.3,
                 "builder": 1.0, "rules": 0.5, "overlay_ms": 8},
}


def vk_name(vk):
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    return VK_NAMES.get(vk)


def nice(name):
    return (name or "?").upper() if len(name or "") == 1 else (name or "?").replace("_", " ")


def key_name(key):
    """Normalise a pynput key to the names used in config.json ('q', 'ctrl', 'f6')."""
    if key is None:
        return None
    if isinstance(key, keyboard.Key):
        name = key.name
        if name.endswith(("_l", "_r", "_gr")):
            name = name.rsplit("_", 1)[0]
        return {"cmd": "win"}.get(name, name)
    vk = getattr(key, "vk", None)
    # Use the virtual-key code for letters/digits: with ctrl held, .char is a control character.
    if vk is not None and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):
        return chr(vk).lower()
    return (key.char or "").lower() or None


class Log:
    def __init__(self, size=300):
        self.lines = deque(maxlen=size)
        self.seq = 0
        self.lock = threading.Lock()

    def __call__(self, msg):
        line = f"{datetime.now():%H:%M:%S}  {msg}"
        with self.lock:
            self.seq += 1
            self.lines.append((self.seq, line))

    def since(self, seq):
        with self.lock:
            return [(s, line) for s, line in self.lines if s > seq]


def menu_on_screen(img):
    """True when Deepwoken's main menu list (Characters / Combat Training / Tutorial) is on screen."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    text = servername.run_ocr(255 - gray).lower()  # light text on a dark scene; OCR wants dark on light
    hits = sum(w in text for w in ("characters", "combat training", "tutorial", "credits", "merch"))
    return hits >= 2


class Engine:
    def __init__(self):
        self.log = Log()
        self.cfg = config.load()
        self.active = self.cfg.get("start_active", False)
        self.running = True
        self.cooldowns, self.macros, self.rules = [], [], []
        self.held = set()           # every key/button currently down
        self.physical_held = set()  # only ones you are really holding
        self.capturing = False      # GUI is waiting for "press any key"
        self.captured_key = None
        self.snapshot_for = None    # cooldown name to record on its next use
        self.snapshot_path = None
        self.scans_per_sec = 0.0
        self._focus_cache = (0.0, False)
        self.toggled_resets = []   # (cooldown, reset, enabled) for the GUI to save
        self.blocked_down = set()  # hotkeys swallowed by a macro that replaces them
        self.universe_id = None    # Roblox game you're in, read from the Roblox log
        self.place_id = None
        self.auto_enabled = False
        self.elevation_warned = False
        self.my_hp = None          # your health %, read off your own bar
        self.my_hp_raw = None      # raw bar fill, for calibrating
        self.party = []            # [(name, health 0..1 or None, online, is_you)]
        self.party_link = party.PartyLink(self.log)
        self.party_link.on_chat = self._on_chat
        self.voice = voice.VoiceReplies(self.log, self._voice_reply)
        self.chat_requested = False  # the party message hotkey was pressed
        self._roblox_typing = False  # Roblox's own chat box is open (after /)
        self.remapped_down = {}      # mouse button -> key it's holding down
        self.job_id = None          # Roblox server you're in (from the Roblox log)
        self.server = servername.ServerName()
        self._server_read_at = 0.0
        self._combat_read_at = 0.0
        self.region = None          # e.g. "The Depths", read off the top of the screen
        self.in_menu = False        # on Deepwoken's main menu (character select)
        self.combat = (False, None) # (in PvP combat, how many players)
        self.prompt_seen = None    # last prompt found: (letter, score, fake)
        self.prompt_presses = 0
        self.notifications = []     # (title, text, kind) for the GUI to show as toasts
        self.hide_requested = False # the hide hotkey was pressed
        self.builder_seen = []      # build talents spotted on screen last scan
        self.builder_cards = []     # ('in' | 'out', talent, (x, y, w, h)) cards on screen, sorted against your build
        self.mask_rects = []        # where this app's own overlays are, so screen reads skip them
        self.builder_active = False # real talent cards are on screen right now
        self.wisp_state = "off"     # auto wisp status for the GUI
        self._party_low = set()
        self.apply(self.cfg)

    # ---- config -------------------------------------------------------------

    def apply(self, cfg):
        """Rebuild cooldowns, macros and rules from a config dict."""
        cfg = copy.deepcopy(cfg)
        old = {cd.name: cd for cd in self.cooldowns}
        for m in self.macros:
            m.stop()
        cooldowns, macros, rules = [], [], []
        for c in cfg.get("cooldowns", []):
            cd = combat.Cooldown(c)
            for r in cd.resets:
                if r.enabled and r.error:
                    self.log(f"{r.name}: off until set up ({r.error})")
            if cd.name in old:
                cd.carry_over(old[cd.name])
            cooldowns.append(cd)
        for m in cfg.get("macros", []):
            if not m.get("enabled", True):
                continue
            try:
                macros.append(combat.Macro(m))
            except Exception as e:
                self.log(f"macro '{m.get('name')}' off: {e}")
        for r in cfg.get("rules", []):
            if not r.get("enabled", True):
                continue
            try:
                rules.append(combat.Rule(r))
            except Exception as e:
                self.log(f"screen rule '{r.get('name')}' off: {e}")
        self.cfg = cfg
        self.cooldowns, self.macros, self.rules = cooldowns, macros, rules
        self.party_link.configure(cfg.get("party", {}))
        vcfg = dict(cfg.get("voice", {}))
        if LITE or not cfg.get("party", {}).get("enabled"):
            vcfg["enabled"] = False
        self.voice.configure(vcfg)

    def cooldown(self, name):
        return next((cd for cd in self.cooldowns if cd.name == name), None)

    def set_active(self, on, why=""):
        self.active = on
        if not on:
            for m in self.macros:
                m.stop()
        self.log(("macros ON" if on else "macros OFF") + (f" ({why})" if why else ""))

    def current_game(self):
        for g in self.cfg.get("roblox", {}).get("games", []):
            if g.get("universe_id") == self.universe_id:
                return g.get("name")
        return None

    def game_focused(self):
        title = self.cfg.get("game_window", "").strip().lower()
        if not title:
            return True
        t = time.perf_counter()
        cached_at, value = self._focus_cache
        if t - cached_at > 0.05:
            # Exact match: a browser tab like "Home - Roblox - Brave" must not count as the game.
            value = foreground_title().strip().lower() == title
            self._focus_cache = (t, value)
            if value and not self.elevation_warned:
                self.elevation_warned = True
                if process_elevated(foreground_pid()) and not process_elevated():
                    self.log("WARNING: the game runs as administrator, so Windows blocks this app's key presses "
                             "and hotkeys in it. Run Elgansito Demolisher Macro as administrator too.")
        return value

    # ---- input --------------------------------------------------------------

    def on_press(self, name, injected):
        if not name:
            return
        if self.capturing and not injected:
            self.captured_key = name
            self.capturing = False
            return
        if name in self.held:  # Windows key auto-repeat while held
            return
        self.held.add(name)
        if not injected:
            self.physical_held.add(name)
            if name == self.cfg.get("toggle_key"):
                self.set_active(not self.active)
                return
            if name == self.cfg.get("hide_key"):
                self.hide_requested = True
                return
            pcfg = self.cfg.get("party", {})
            if not LITE and pcfg.get("enabled") and self.game_focused():
                # While you're typing in Roblox's own chat (opened with /), keys belong to it: the Enter
                # that sends a Roblox message must not open the party box, and letters aren't hotkeys.
                if name == "/":
                    self._roblox_typing = True
                elif name in ("enter", "esc") and self._roblox_typing:
                    self._roblox_typing = False
                    return
                elif not self._roblox_typing:
                    if name == self.cfg.get("chat_key"):
                        self.chat_requested = True
                        return
                    text = next((b.get("text") for b in pcfg.get("binds", []) if b.get("key") == name), None)
                    if text:
                        err = self.party_link.send_chat(text)
                        self.log(f"party message hotkey: {text}" + (f" (not sent: {err})" if err else ""))
                        if err:
                            self.notify("PARTY", f"couldn't send '{text}': {err}", "warn")
            if name and name == self.cfg.get("voice", {}).get("key") and self.cfg.get("voice", {}).get("enabled"):
                self.voice.held = True
            if name == self.cfg.get("pick_key"):
                self.log_cursor()
                return
            for cd in self.cooldowns:
                for r in cd.resets:
                    if r.toggle_key and name == r.toggle_key:
                        r.enabled = not r.enabled
                        self.toggled_resets.append((cd.name, r.name, r.enabled))
                        self.log(f"{r.name} {'ON' if r.enabled else 'OFF'}")
        if not self.game_focused():
            return
        t = combat.now()
        for cd in self.cooldowns:
            for msg in cd.on_input(name, t):
                self.log(msg)
            snap = self.snapshot_for
            if snap and snap[0] == cd.name:
                reset = next((r for r in cd.resets if r.name == snap[1]), None)
                if reset and name == reset.key and (name != cd.key or cd.ready_at > t):
                    self.snapshot_for = None
                    threading.Thread(target=self._record_snapshot, args=(cd, reset), daemon=True).start()
        if injected:
            return
        for m in self.macros:
            if m.hotkey == name:
                if self.active:
                    m.trigger(self.is_held, self.macros_allowed, self.log)
                else:
                    self.log(f"{nice(name)} pressed, but macros are OFF "
                             f"({nice(self.cfg.get('toggle_key'))} turns them on)")

    def is_held(self, key):
        return key in self.physical_held

    def macros_allowed(self):
        return self.active and self.running

    def on_release(self, name, injected):
        if name:
            if name == self.cfg.get("voice", {}).get("key"):
                self.voice.held = False
            self.held.discard(name)
            if not injected:
                self.physical_held.discard(name)

    def blocking_macro(self, name):
        """The macro that replaces this key in game right now, if any."""
        if not (self.active and name):
            return None
        for m in self.macros:
            if m.block_key and m.hotkey == name:
                return m if self.game_focused() else None
        return None

    def kb_filter(self, msg, data):
        """Runs before Windows passes a key on. Swallows a hotkey whose macro replaces it
        (F -> feint then parry), so the game only sees what the macro sends."""
        if data.flags & 0x10:  # injected (by a macro or another program)
            return True
        name = vk_name(data.vkCode)
        if msg in (0x100, 0x104):
            if self.capturing:
                return True
            if name in self.blocked_down:  # auto-repeat while held
                self.kb_listener.suppress_event()
            macro = self.blocking_macro(name)
            if macro:
                # Only mark it physically held: `held` must stay free so the macro's own
                # copy of this key (e.g. its F) still counts for cooldowns like the parry bar.
                self.blocked_down.add(name)
                self.physical_held.add(name)
                macro.trigger(self.is_held, self.macros_allowed, self.log)
                self.kb_listener.suppress_event()
        elif name in self.blocked_down:
            self.blocked_down.discard(name)
            self.physical_held.discard(name)
            self.kb_listener.suppress_event()
        return True

    def remap_for(self, button):
        """The key a mouse button is remapped to right now (in game, macros on), or None."""
        if self.capturing or not self.active or not self.game_focused():
            return None
        return next((r.get("key") for r in self.cfg.get("remaps", [])
                     if r.get("enabled") and r.get("button") == button and r.get("key")), None)

    def mouse_filter(self, msg, data):
        """Mouse buttons remapped to keys (side button -> 9...): the key goes down and up with the
        button, and the click itself never reaches the game."""
        if data.flags & 0x1:  # injected by a macro or another program
            return True
        if msg in (0x20B, 0x20C):    # side buttons: which one is in the high word of mouseData
            button = "mouse_x1" if (data.mouseData >> 16) & 0xFFFF == 1 else "mouse_x2"
        elif msg in (0x207, 0x208):
            button = "mouse_middle"
        else:
            return True
        if msg in (0x20B, 0x207):
            key = self.remap_for(button)
            if not key:
                return True
            self.remapped_down[button] = key
            sendinput.key_down(key)
        else:
            key = self.remapped_down.pop(button, None)
            if not key:
                return True
            sendinput.key_up(key)
        self.mouse_listener.suppress_event()

    def start_listeners(self):
        def kb_press(key, injected=False):
            self.on_press(key_name(key), injected)

        def kb_release(key, injected=False):
            self.on_release(key_name(key), injected)

        def click(x, y, button, pressed, injected=False):
            name = f"mouse_{button.name}"
            (self.on_press if pressed else self.on_release)(name, injected)

        self.kb_listener = keyboard.Listener(on_press=kb_press, on_release=kb_release,
                                             win32_event_filter=self.kb_filter)
        self.mouse_listener = mouse.Listener(on_click=click, win32_event_filter=self.mouse_filter)
        self.listeners = [self.kb_listener, self.mouse_listener]
        for listener in self.listeners:
            listener.start()

    def log_cursor(self):
        x, y = sendinput.cursor_pos()
        with detect.MSS() as sct:
            r, g, b = sct.grab({"left": x, "top": y, "width": 1, "height": 1}).pixel(0, 0)
        self.log(f"cursor ({x}, {y})  colour [{r}, {g}, {b}]")

    # ---- background loops ---------------------------------------------------

    def perf(self, key):
        return PERF.get(self.cfg.get("performance", "balanced"), PERF["balanced"])[key]

    def notify(self, title, text, kind="info"):
        self.notifications.append((title, text, kind))

    def start(self):
        self.start_listeners()
        loops = [self._landing_loop, self._game_watch_loop, self._icons_loop, self._wisp_loop]
        if not LITE:  # Elgansito Lite skips the screen-reading extras
            loops += [self._rules_loop, self._hp_loop, self._prompts_loop, self._builder_loop]
        for loop in loops:
            threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self.running = False
        for m in self.macros:
            m.stop()
        for listener in getattr(self, "listeners", []):
            listener.stop()
        self.party_link.stop()
        self.voice.stop()

    def _rules_loop(self):
        with detect.MSS() as sct:
            while self.running:
                rules = self.rules
                if not rules:
                    self.scans_per_sec = 0.0
                    time.sleep(0.1)
                    continue
                start = time.perf_counter()
                box = detect.monitor_box(sct, self.cfg.get("monitor", 1))
                try:
                    frame = detect.grab(sct, box)
                except Exception as e:
                    self.log(f"screen capture failed: {e}")
                    time.sleep(1)
                    continue
                t = time.time()
                act = self.active and self.game_focused()
                for rule in list(rules):
                    was_found = rule.found
                    try:
                        rule.found, rule.score, rule.pos = rule.detector.measure(frame, (box["left"], box["top"]))
                    except Exception as e:
                        self.log(f"screen rule '{rule.name}' stopped: {e}")
                        rules.remove(rule)
                        continue
                    if act and rule.should_fire(was_found, t):
                        rule.last_fire = t
                        rule.fired += 1
                        try:
                            done = rule.run_action()
                            if done:
                                self.log(f"{rule.name}: {done}")
                        except Exception as e:
                            self.log(f"{rule.name}: action failed ({e})")
                elapsed = time.perf_counter() - start
                wait = max(self.cfg.get("scan_interval_ms", 50) / 1000 * self.perf("rules") - elapsed, 0)
                time.sleep(wait)
                self.scans_per_sec = 1 / max(elapsed + wait, 1e-6)

    def _landing_loop(self):
        """After a trigger key (F for parry, M1 for Blade Dancer), watch its area for
        the hit effect for a short window, and reset the cooldown if it shows up."""
        watching = {}
        with detect.MSS() as sct:
            while self.running:
                t = combat.now()
                pending = [(cd, r) for cd in self.cooldowns for r in cd.resets if r.armed and t <= r.detect_until]
                for cd, r in pending:
                    watching[id(r)] = (cd, r)
                    try:
                        box = r.detector.box(detect.monitor_box(sct, self.cfg.get("monitor", 1)))
                        found, score, _ = r.detector.measure(detect.grab(sct, box), (box["left"], box["top"]))
                    except Exception as e:
                        self.log(f"{r.name}: detection error ({e})")
                        r.detect_until = 0.0
                        continue
                    r.peak = max(r.peak, score)
                    if found:
                        was = cd.remaining(combat.now())
                        cd.land(r, combat.now())
                        self.log(f"{r.name}! {cd.name} ready" + (f" ({was:.1f}s early)" if was else ""))
                # Report misses once their window closes, to help tuning.
                live = {id(r) for _, r in pending}
                for key, (cd, r) in list(watching.items()):
                    if key not in live:
                        del watching[key]
                        if r.detect_until:
                            self.log(f"{r.name}: not seen, best {detect.describe_score(r.detector, r.peak)}")
                time.sleep(0.004 if pending else self.perf("landing"))

    def _hp_loop(self):
        """Read your own health (bar, or the "N% HEALTH" text under 14%), your server, region and
        PvP danger, share them with your party, and keep the party list (you first) for the overlay."""
        with detect.MSS() as sct:
            while self.running:
                cfg = self.cfg
                try:
                    focused = self.game_focused()
                    now = time.time()
                    if focused and self.universe_id and now - self._server_read_at > self.perf("server"):
                        self._server_read_at = now
                        self.in_menu = (self.place_id in MENU_PLACES
                                        or bool(self._read_box(sct, MENU_BOX, menu_on_screen)))
                        if self.in_menu:
                            self.region = None
                        else:
                            srv = self._read_box(sct, cfg.get("server_name", {}).get(
                                "region", servername.DEFAULT_REGION), servername.read)
                            reg = self._read_box(sct, hud.REGION_BOX, hud.read_region)
                            if not srv:  # other screen sizes: search the whole top line instead
                                srv, auto_reg = self._read_box(sct, hud.TOP_STRIP, hud.auto_server_region) or (None, None)
                                reg = auto_reg or reg
                            self.server.add(self.job_id, srv)
                            if reg:
                                self.region = reg
                    if not self.universe_id:
                        self.server.add(None, None)
                        self.in_menu = False
                        self.region = None
                        self.combat = (False, None)
                    if focused and now - self._combat_read_at > self.perf("combat"):
                        self._combat_read_at = now
                        x, y, w, h = hud.SKULL_BOX
                        box = {"left": x, "top": y, "width": w + 60, "height": h + 40}
                        self.combat = hud.read_combat(detect.grab(sct, box), hud.SKULL_BOX, (x, y))
                    if focused:
                        x, y, w, h = cfg.get("my_hp", {}).get("region", hp.DEFAULT_REGION)
                        frame = detect.grab(sct, {"left": x, "top": y, "width": w, "height": h})
                        tx, ty, tw, th = hp.TEXT_REGION
                        text_img = frame[max(ty - y, 0):ty - y + th, max(tx - x, 0):tx - x + tw]
                        self.my_hp, self.my_hp_raw = hp.read_combined(
                            frame, text_img, cfg.get("my_hp", {}).get("calibration", []))
                    pcfg = cfg.get("party", {})
                    if pcfg.get("enabled"):
                        in_combat, count = self.combat
                        where = "Main Menu" if self.in_menu else self.server.name
                        self.party_link.publish(self.my_hp, where, self.job_id,
                                                region=self.region, combat=in_combat, count=count)
                        my_job = party.job_hash(self.job_id)
                        rows = [{"name": pcfg.get("username") or "You", "you": True, "online": True,
                                 "hp": None if self.my_hp is None else self.my_hp / 100,
                                 "server": where, "same": False, "region": self.region,
                                 "combat": in_combat, "count": count}]
                        for m in self.party_link.snapshot(pcfg.get("friends", [])):
                            m["you"] = False
                            m["same"] = bool(m["online"] and m.get("job") and m["job"] == my_job)
                            m["hp"] = None if m["hp"] is None else m["hp"] / 100
                            rows.append(m)
                        self.party = rows
                        self._check_party_low(rows)
                    else:
                        self.party = []
                except Exception as e:
                    self.log(f"HP reader error: {e}")
                    time.sleep(1)
                time.sleep(self.perf("hp"))

    def _read_box(self, sct, box, reader):
        x, y, w, h = box
        try:
            return reader(detect.grab(sct, {"left": x, "top": y, "width": w, "height": h}))
        except Exception:
            return None

    def _icons_loop(self):
        """Read the game's cooldown bubbles ~60x a second and sync the bars to them."""
        reader = icons.IconReader()
        bar_reader = hotbar.HotbarReader()
        self.icon_states = []
        with detect.MSS() as sct:
            while self.running:
                icfg = self.cfg.get("cd_icons", icons.DEFAULT)
                synced = [cd for cd in self.cooldowns if cd.icon_slot] if icfg.get("enabled") else []
                mantras = [cd for cd in self.cooldowns if cd.hotbar_slot and not cd.icon_slot]
                if not ((synced or mantras) and self.game_focused()):
                    self.icon_states = []
                    time.sleep(0.1)
                    continue
                try:
                    states = reader.read(detect.grab(sct, icons.capture_box(icfg)), icfg) if synced else []
                    hcfg = self.cfg.get("hotbar", hotbar.DEFAULT)
                    slots = bar_reader.read(detect.grab(sct, hotbar.capture_box(hcfg)), hcfg,
                                            {cd.hotbar_slot for cd in mantras}) if mantras else {}
                except Exception as e:
                    self.log(f"cooldown bubbles / hotbar: {e}")
                    time.sleep(1)
                    continue
                self.icon_states = states
                t = combat.now()
                updates = [(cd, states[cd.icon_slot - 1]) for cd in synced if cd.icon_slot <= len(states)]
                updates += [(cd, slots.get(cd.hotbar_slot)) for cd in mantras]
                for cd, state in updates:
                    if state:
                        msg = cd.icon_update(state, t)
                        if msg:
                            self.log(msg)
                time.sleep(self.perf("icons"))

    def _prompts_loop(self):
        """Press Deepwoken's Z / X / C / V prompts when they appear. Decoys on a teal
        box are skipped, and each prompt is pressed once until it goes away."""
        finder, pressed_at = None, None
        with detect.MSS() as sct:
            while self.running:
                pcfg = self.cfg.get("prompts", {})
                if not (pcfg.get("enabled") and self.active and self.game_focused()):
                    pressed_at = None
                    time.sleep(0.1)
                    continue
                try:
                    if finder is None:
                        finder = prompts.PromptFinder()
                    x, y, w, h = pcfg.get("region") or [0, 0, 1920, 1080]
                    found = finder.find(detect.grab(sct, {"left": x, "top": y, "width": w, "height": h}))
                except Exception as e:
                    self.log(f"key prompts: {e}")
                    time.sleep(2)
                    continue
                hit = found and found[1] >= pcfg.get("threshold", 0.82)
                self.prompt_seen = (found[0], found[1], found[3]) if found else None
                if not hit:
                    pressed_at = None
                elif found[3]:
                    if pressed_at != ("fake", found[2]):
                        self.log(f"{found[0]} prompt is a fake - not pressing")
                        pressed_at = ("fake", found[2])
                elif pressed_at is None or pressed_at[0] != found[0] or \
                        abs(pressed_at[1][0] - found[2][0]) + abs(pressed_at[1][1] - found[2][1]) > 20:
                    delay = pcfg.get("delay_ms", 0) / 1000
                    if delay:
                        time.sleep(delay)
                    sendinput.tap(found[0].lower(), 25)
                    self.prompt_presses += 1
                    pressed_at = (found[0], found[2])
                    self.log(f"pressed {found[0]} prompt ({found[1]:.2f})")
                time.sleep(self.perf("prompts"))

    def _on_chat(self, name, text):
        """A friend's message: show it, and listen for a spoken reply for a few seconds."""
        vcfg = self.cfg.get("voice", {})
        listening = vcfg.get("enabled") and self.voice.status.startswith("ready")
        if listening:
            self.voice.listen_for(float(vcfg.get("listen_s", 6)))
        self.notify(f"PARTY // {name}", text + ("   [say yes / no to reply]" if listening else ""), "chat")

    def _voice_reply(self, phrase):
        err = self.party_link.send_chat(phrase)
        self.log(f"voice reply: {phrase}" + (f" (not sent: {err})" if err else ""))
        self.notify("VOICE REPLY", f"sent: {phrase}" if not err else f"heard '{phrase}' but {err}", "chat")

    def _check_party_low(self, rows):
        """Toast once when a friend drops under 30% HP."""
        if not self.cfg.get("notify", {}).get("party_low", True):
            return
        for r in rows:
            if r.get("you") or not r.get("online") or r.get("hp") is None:
                continue
            name = r["name"]
            if r["hp"] < 0.3 and name not in self._party_low:
                self._party_low.add(name)
                self.notify("Party", f"{name} is low: {r['hp']:.0%} HP", "party")
            elif r["hp"] >= 0.4:
                self._party_low.discard(name)

    def _builder_loop(self):
        """Builder 101: finds Deepwoken's talent cards on screen (the level-up row, or grids like "Choose a
        Talent to Exchange"), reads each title and sorts it: in your build (yellow frame, and a notification
        on level up) or not in your build (red frame). Single cards, like inventory tooltips, are ignored."""
        last = {}
        every = {}  # build link -> every talent name on its deepwoken.co page (to tell real talents from misreads)
        with detect.MSS() as sct:
            while self.running:
                b = self.cfg.get("builder", {})
                talents = b.get("talents", [])
                if not (b.get("watch") and talents and self.game_focused()):
                    self.builder_seen, self.builder_cards, self.builder_active = [], [], False
                    time.sleep(0.5)
                    continue
                url = b.get("url", "")
                if url and url not in every:
                    every[url] = b.get("all") or []
                    if not every[url]:
                        try:
                            every[url] = builder.fetch(url).get("all", [])
                        except Exception as e:
                            self.log(f"builder: couldn't fetch the talent list ({e})")
                if b.get("cards"):
                    x, y, w, h = b["cards"]
                    box = {"left": x, "top": y, "width": w, "height": h}
                else:
                    box = detect.monitor_box(sct, self.cfg.get("monitor", 1))
                try:
                    img = detect.grab(sct, box).copy()
                    # Blank out this app's own overlays, so their text is never read as a card.
                    for rx, ry, rw, rh in list(self.mask_rects):
                        x0, y0 = max(rx - box["left"], 0), max(ry - box["top"], 0)
                        x1, y1 = min(rx + rw - box["left"], box["width"]), min(ry + rh - box["top"], box["height"])
                        if x1 > x0 and y1 > y0:
                            img[y0:y1, x0:x1] = 0
                    found = cards.read_cards(img)
                except Exception as e:
                    self.log(f"builder: couldn't read the screen ({e})")
                    time.sleep(3)
                    continue
                have = set(b.get("obtained", []))
                seen, marks = [], []
                recognised = readable = 0
                for title, card in found:
                    readable += len(builder.canon(title)) >= 4
                    kind, name = builder.classify(title, talents, every.get(url, []))
                    if kind is None:
                        continue
                    recognised += 1
                    fx, fy, fw, fh = card["frame"]
                    marks.append((kind, name, (box["left"] + fx, box["top"] + fy, fw, fh)))
                    if kind == "in":
                        seen.append(name)
                # A real card screen has titles that read as talents. Other light panels (menus, scenery)
                # that happen to look like cards don't, so they show nothing.
                if not (recognised >= 2 or (recognised >= 1 and readable >= 3)):
                    seen, marks = [], []
                # Level up = one row of a few cards. A bigger grid ("Choose a Talent to Exchange") is your own
                # talents: there only the ones to get rid of are marked, and nothing is announced.
                level_up = len({c["panel"][1] for _, c in found}) == 1 and len(found) <= 6
                if not level_up:
                    marks = [m for m in marks if m[0] == "out"]
                self.builder_seen, self.builder_cards = seen, marks
                self.builder_active = bool(seen or marks)
                if level_up and seen:
                    now = time.time()
                    for t in seen:
                        if t not in have and now - last.get(t, 0) > 30:
                            last[t] = now
                            self.log(f"builder: {t} is in your build - take it")
                            self.notify("BUILDER 101", f"{t} is in your build - take it!", "builder")
                # No cards: a quick colour check, so look often. Cards up: OCR, so slow down.
                time.sleep(self.perf("builder") if found else 0.3)

    def _wisp_loop(self):
        """Auto wisp: when Deepwoken's ritual letter box is up, type its letters (see wisp.py)."""
        tracker = wisp.Tracker()
        with detect.MSS() as sct:
            while self.running:
                wc = self.cfg.get("wisp", {})
                if not (wc.get("enabled") and self.active and self.game_focused()):
                    tracker.reset()
                    self.wisp_state = "off" if not wc.get("enabled") else "waiting for macros ON + Roblox focused"
                    time.sleep(0.1)
                    continue
                x, y, w, h = wc.get("area") or wisp.DEFAULT_AREA
                try:
                    box, glyphs = wisp.read(detect.grab(sct, {"left": x, "top": y, "width": w, "height": h}))
                except Exception as e:
                    self.log(f"auto wisp: couldn't read the screen ({e})")
                    time.sleep(1)
                    continue
                key = tracker.step(glyphs if box else [], time.time(), float(wc.get("retry_ms", 350)) / 1000,
                                   bool(wc.get("confirm", True)))
                if key:
                    delay = float(wc.get("delay_ms", 0)) / 1000
                    if delay:
                        time.sleep(delay)
                    sendinput.tap(key, int(wc.get("hold_ms", 40)))
                    self.log(f"auto wisp: {key.upper()}")
                letters = "".join(g[2] for g in glyphs).upper()
                self.wisp_state = (f"box up: {letters or '...'}  -  {tracker.presses} letters typed" if box
                                   else f"watching  -  {tracker.presses} letters typed")
                time.sleep(0.004 if box else 0.04)

    def _game_watch_loop(self):
        """Follow the newest Roblox log to know which game you're in, and turn macros
        on/off automatically for the games in Settings > Roblox."""
        path, offset = None, 0
        while self.running:
            try:
                files = glob.glob(os.path.join(ROBLOX_LOGS, "*Player*.log"))
                newest = max(files, key=os.path.getmtime) if files else None
                if newest != path:
                    path, offset = newest, 0
                    self.universe_id = self.place_id = self.job_id = None
                if path:
                    with open(path, "rb") as f:
                        f.seek(offset)
                        chunk = f.read()
                        offset = f.tell()
                    for line in chunk.decode("utf-8", "replace").splitlines():
                        m = JOIN_RE.search(line)
                        if m:
                            self.place_id, self.universe_id = int(m.group(1)), int(m.group(2))
                        j = JOB_RE.search(line)
                        if j:
                            self.job_id = j.group(1)
                        elif LEAVE_RE.search(line):
                            self.universe_id = self.place_id = self.job_id = None
                if self.universe_id and not roblox_running():
                    self.universe_id = self.place_id = self.job_id = None
                self._auto_toggle()
            except Exception as e:
                self.log(f"Roblox log watch error: {e}")
            time.sleep(1.0)

    def _auto_toggle(self):
        if not self.cfg.get("roblox", {}).get("auto_enable", True):
            return
        game = self.current_game()
        if game and not self.auto_enabled:
            self.auto_enabled = True
            if not self.active:
                self.set_active(True, f"{game} detected")
                self.notify("Macros online", f"{game} detected - macros armed", "macro")
        elif not game and self.auto_enabled:
            self.auto_enabled = False
            if self.active:
                self.set_active(False, "left the game")

    def _record_snapshot(self, cd, reset):
        """Record the screen just after a parry and keep the frame that changed
        most, so the effect can be picked out in the GUI."""
        frames = []
        with detect.MSS() as sct:
            box = detect.monitor_box(sct, self.cfg.get("monitor", 1))
            end = time.perf_counter() + 0.6
            while time.perf_counter() < end:
                frames.append(detect.grab(sct, box))
                time.sleep(0.03)
        if len(frames) < 2:
            self.log("snapshot failed: no frames")
            return
        h, w = frames[0].shape[:2]
        centre = (slice(h // 4, 3 * h // 4), slice(w // 4, 3 * w // 4))
        base = frames[0][centre].astype(np.int16)
        best = max(frames[1:], key=lambda f: np.abs(f[centre].astype(np.int16) - base).mean())
        os.makedirs(config.TEMPLATE_DIR, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", f"{cd.name}_{reset.name}".lower()).strip("_")
        path = os.path.join(config.TEMPLATE_DIR, f"snapshot_{slug}.png")
        detect.write_image(path, best)
        self.snapshot_path = (f"{cd.name}/{reset.name}", path, (box["left"], box["top"]))
        self.log(f"{reset.name}: recording saved - pick the effect in the app")
