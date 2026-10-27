"""Cooldowns, macros and screen rules.

Cooldowns are timed from the moment you press the key, so the bars never
depend on reading the screen. A press made while still on cooldown is ignored
(the game ignores it too), the first roll cancel gives the roll back, and
resets (a parry landing, Blade Dancer M1 hits) seen on screen make it ready.
"""
import threading
import time

import detect
import sendinput

STEP_ACTIONS = {
    "tap": "Press key",
    "down": "Hold key down",
    "up": "Release key",
    "click": "Click mouse",
    "mouse_down": "Hold mouse button",
    "mouse_up": "Release mouse button",
    "wait": "Wait",
    "wait_release": "Wait until hotkey is released",
}
KEY_ACTIONS = {"tap", "down", "up"}
MOUSE_ACTIONS = {"click", "mouse_down", "mouse_up"}

MODES = {
    "once": "Run once per press",
    "hold": "Repeat while held",
    "toggle": "Press to start / stop a loop",
}


def now():
    return time.perf_counter()


class Reset:
    """Puts a cooldown back to ready when something shows up on screen shortly
    after pressing a key: a parry landing, or an M1 hitting with Blade Dancer."""

    def __init__(self, cfg):
        self.name = cfg["name"]
        self.key = cfg.get("key", "").lower()
        self.toggle_key = cfg.get("toggle_key", "").lower()
        self.enabled = cfg.get("enabled", False)
        self.window = cfg.get("window_ms", 450) / 1000
        self.error = None
        try:
            self.detector = detect.Detector(cfg["detect"])
        except Exception as e:
            self.detector, self.error = None, str(e)
        self.detect_until = 0.0
        self.peak = 0.0
        self.hits = 0

    @property
    def armed(self):
        return self.enabled and self.detector is not None


class Cooldown:
    def __init__(self, cfg):
        self.name = cfg["name"]
        self.key = cfg["key"].lower()
        self.duration = max(cfg["cooldown_ms"], 1) / 1000
        self.color = cfg.get("color", "#4aa3ff")
        self.label = cfg.get("label", "")  # text shown on the bar instead of the name, e.g. "AUTOPARRY METER"
        cancel = cfg.get("cancel") or {}
        on = cancel.get("enabled", False)
        self.cancel_key = cancel.get("key", "").lower() if on else None
        self.cancel_window = cancel.get("window_ms", 0) / 1000
        self.cancel_cooldown = cancel.get("cooldown_ms", 0) / 1000
        # Deepwoken gives one free extra roll when you cancel; cancelling that one too puts it on cooldown.
        self.max_refunds = cancel.get("max_refunds", 1)
        self.resets = [Reset(r) for r in cfg.get("resets", [])]
        self.ready_at = 0.0
        self.cancel_open_until = 0.0
        self.cancel_ready_at = 0.0
        self.refunds_left = self.max_refunds
        self.last_refund_at = -1e9
        self.uses = 0
        self.cancels = 0
        self.landed_at = -1e9
        # Sync with the game's own cooldown bubble (1-based slot under the health bar, 0 = off).
        self.icon_slot = int(cfg.get("icon_slot", 0) or 0)
        # Or follow a hotbar slot (1-10) going dark, for mantras.
        self.hotbar_slot = int(cfg.get("hotbar_slot", 0) or 0)
        self.icon_state = None
        self.icon_seen_at = -1e9
        self.press_at = -1e9
        self.unconfirmed = False   # started by a key press the game hasn't shown yet
        self.cool_started = None   # when the bubble went dim
        self.natural = []          # recent full cooldown lengths seen on the bubble
        self.ignored_streak = 0    # presses in a row the bubble never showed; 3 = we're misreading it
        self.lock = threading.Lock()

    def span(self):
        """Cooldown length: learned from the game's bubble once seen twice, else the setting."""
        if len(self.natural) >= 2:
            return float(sorted(self.natural)[len(self.natural) // 2])
        return self.duration

    def icon_live(self, t):
        return (self.icon_slot > 0 or self.hotbar_slot > 0) and t - self.icon_seen_at < 0.5 and self.ignored_streak < 3

    @property
    def landed(self):
        return sum(r.hits for r in self.resets)

    def carry_over(self, old):
        """Keep timers and counters when the config is edited mid-game."""
        self.ready_at = old.ready_at
        self.cancel_ready_at = old.cancel_ready_at
        self.refunds_left, self.last_refund_at = old.refunds_left, old.last_refund_at
        self.uses, self.cancels = old.uses, old.cancels
        self.natural = list(old.natural)
        hits = {r.name: r.hits for r in old.resets}
        for r in self.resets:
            r.hits = hits.get(r.name, 0)

    def on_input(self, key, t):
        """Update state for a fresh key press; returns log messages for anything that mattered."""
        msgs = []
        with self.lock:
            used = False
            if key == self.key:
                self.press_at = t
                # The bubble already went dim a moment ago (input lag the other way round): this press is it.
                if self.cool_started is not None and t - self.cool_started < 0.3 and self.ready_at - t < 0.1:
                    self.ready_at = self.cool_started + self.span()
                    self.uses += 1
                    used = True
                    msgs.append(f"{self.name} used ({self.span():.2f}s)")
            if used:
                pass
            elif key == self.key and t >= self.ready_at:
                if t - self.last_refund_at > self.duration:
                    self.refunds_left = self.max_refunds
                self.ready_at = t + self.span()
                self.cancel_open_until = t + self.cancel_window
                self.unconfirmed = self.icon_live(t)
                self.uses += 1
                used = True
                msgs.append(f"{self.name} used ({self.span():.2f}s)")
            elif (self.cancel_key and key == self.cancel_key
                    and self.cancel_ready_at <= t <= self.cancel_open_until):
                self.cancel_open_until = 0.0
                self.cancel_ready_at = t + self.cancel_cooldown
                self.cancels += 1
                if self.refunds_left > 0:
                    self.refunds_left -= 1
                    self.last_refund_at = t
                    self.ready_at = t
                    msgs.append(f"{self.name} cancelled - kept it")
                else:
                    msgs.append(f"{self.name} cancelled again - on cooldown")
            for r in self.resets:
                if r.armed and key == r.key and (used or key != self.key):
                    r.detect_until = t + r.window
                    r.peak = 0.0
        return msgs

    def land(self, reset, t):
        with self.lock:
            self.ready_at = t
            self.landed_at = t
            reset.detect_until = 0.0
            reset.hits += 1

    def icon_update(self, state, t):
        """Follow the game's bubble: a bar only counts down once the game shows the move happened,
        and is ready the moment the bubble lights up again (landed parry, cancel, Blade Dancer)."""
        msg = None
        if self.ignored_streak >= 3:
            return None  # bubble sync switched off for this bar: it kept disagreeing with real presses
        with self.lock:
            prev, self.icon_state, self.icon_seen_at = self.icon_state, state, t
            if prev is None:
                return None
            if state == "cooling":
                if prev == "ready":
                    self.cool_started = t
                    if self.unconfirmed:
                        self.unconfirmed = False
                        self.ignored_streak = 0
                    elif t - self.press_at < 0.5 and self.ready_at <= t:
                        self.ready_at = self.press_at + self.span()
                        self.uses += 1
                if self.cool_started is not None and self.ready_at <= t:
                    self.ready_at = t + 0.03  # the game says not yet: hold just short of ready
            elif state == "ready":
                if prev == "cooling" and self.cool_started is not None:
                    length = t - self.cool_started
                    # Mantra cooldowns vary a lot, so a hotbar slot may learn far from the starting guess.
                    lo, hi = (0.2, 5) if self.hotbar_slot else (0.6, 3)
                    if lo * self.duration < length < hi * self.duration:
                        self.natural = (self.natural + [round(length, 3)])[-5:]
                    if self.ready_at > t + 0.15:
                        msg = f"{self.name} ready ({self.ready_at - t:.1f}s early, from the game's icon)"
                        self.landed_at = t
                    self.ready_at = min(self.ready_at, t)
                    self.cool_started = None
                if self.unconfirmed and t - self.press_at > 0.4:
                    self.unconfirmed = False
                    self.ready_at = t
                    self.uses -= 1
                    self.ignored_streak += 1
                    msg = f"{self.name}: the game ignored that press"
                    if self.ignored_streak >= 3:
                        msg = (f"{self.name}: 3 presses in a row never showed on the game's bubble, so it's "
                               "probably misreading it - bubble sync off for this bar (Settings > Pick the bubbles)")
        return msg

    def remaining(self, t):
        return max(self.ready_at - t, 0.0)

    def cancel_remaining(self, t):
        return max(self.cancel_ready_at - t, 0.0)


class _Stopped(Exception):
    pass


class Macro:
    def __init__(self, cfg):
        self.name = cfg["name"]
        self.hotkey = cfg.get("hotkey", "").lower()
        if not self.hotkey:
            raise ValueError("no hotkey set")
        self.block_key = cfg.get("block_key", False)
        self.mode = cfg.get("mode", "once")
        self.interval = max(cfg.get("interval_ms", 100), 1) / 1000
        self.steps = cfg.get("steps", [])
        for step in self.steps:
            action = step.get("action")
            if action in KEY_ACTIONS:
                sendinput.vk_for(step.get("key", ""))
            elif action in MOUSE_ACTIONS:
                if step.get("button") not in sendinput.MOUSE_FLAGS:
                    raise ValueError(f"unknown mouse button '{step.get('button')}'")
            elif action not in ("wait", "wait_release"):
                raise ValueError(f"unknown step '{action}'")
        self.stop_flag = threading.Event()
        self.running = False
        self.runs = 0

    def trigger(self, is_held, allowed, log):
        if self.mode == "toggle" and self.running:
            self.stop_flag.set()
            return
        if self.running:
            return
        self.running = True
        self.stop_flag.clear()
        threading.Thread(target=self._loop, args=(is_held, allowed, log), daemon=True).start()

    def stop(self):
        self.stop_flag.set()

    def _sleep(self, seconds):
        # Event.wait is only accurate to ~15 ms on Windows; time.sleep is precise for short waits.
        if seconds < 0.02:
            time.sleep(seconds)
            if self.stop_flag.is_set():
                raise _Stopped
        elif self.stop_flag.wait(seconds):
            raise _Stopped

    def _loop(self, is_held, allowed, log):
        keys, buttons = [], []
        try:
            while True:
                self._run_steps(keys, buttons, is_held)
                self.runs += 1
                if self.mode == "once" or not allowed():
                    break
                if self.mode == "hold" and not is_held(self.hotkey):
                    break
                self._sleep(self.interval)
                if self.mode == "hold" and not is_held(self.hotkey):
                    break
        except _Stopped:
            pass
        except Exception as e:
            log(f"macro '{self.name}' failed: {e}")
        finally:
            # Never leave a key or button stuck down.
            for key in keys:
                sendinput.key_up(key)
            for button in buttons:
                sendinput.mouse_up(button)
            self.running = False

    def _run_steps(self, keys, buttons, is_held):
        for step in self.steps:
            if self.stop_flag.is_set():
                raise _Stopped
            action, ms = step["action"], step.get("ms", 25) / 1000
            key, button = step.get("key", ""), step.get("button", "left")
            if action == "tap":
                sendinput.key_down(key)
                keys.append(key)
                time.sleep(ms)
                sendinput.key_up(key)
                keys.remove(key)
            elif action == "down":
                sendinput.key_down(key)
                keys.append(key)
            elif action == "up":
                sendinput.key_up(key)
                if key in keys:
                    keys.remove(key)
            elif action == "click":
                sendinput.mouse_down(button)
                buttons.append(button)
                time.sleep(ms)
                sendinput.mouse_up(button)
                buttons.remove(button)
            elif action == "mouse_down":
                sendinput.mouse_down(button)
                buttons.append(button)
            elif action == "mouse_up":
                sendinput.mouse_up(button)
                if button in buttons:
                    buttons.remove(button)
            elif action == "wait":
                self._sleep(ms)
            elif action == "wait_release":
                while is_held(self.hotkey):
                    self._sleep(0.005)


class Rule:
    """Watch the screen for something and react when it shows up."""

    def __init__(self, cfg):
        self.name = cfg["name"]
        self.detector = detect.Detector(cfg["detect"])
        self.trigger = cfg.get("trigger", "on_appear")
        self.cooldown = cfg.get("cooldown_ms", 500) / 1000
        self.action = cfg.get("action", {"type": "none"})
        if self.action.get("type") == "key":
            sendinput.vk_for(self.action.get("key", ""))
        self.found = False
        self.score = 0.0
        self.pos = None
        self.fired = 0
        self.last_fire = 0.0

    def should_fire(self, was_found, t):
        if not self.found or t - self.last_fire < self.cooldown:
            return False
        return self.trigger == "while_visible" or not was_found

    def run_action(self):
        a = self.action
        kind = a.get("type", "none")
        if kind == "click":
            x, y = self.pos if a.get("at", "match") == "match" else a.get("point", self.pos)
            prev = sendinput.cursor_pos()
            sendinput.move_to(x, y)
            time.sleep(0.01)
            sendinput.click(a.get("button", "left"), a.get("ms", 25))
            if a.get("return_mouse", True):
                sendinput.move_to(*prev)
            return f"clicked {a.get('button', 'left')} at ({x}, {y})"
        if kind == "key":
            sendinput.tap(a["key"], a.get("ms", 30))
            return f"pressed {a['key']}"
        return None
