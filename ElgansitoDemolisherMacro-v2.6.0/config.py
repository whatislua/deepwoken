"""Loading and saving config.json, with defaults for anything missing."""
import copy
import json
import os
import re
import sys

# The app's own files (exe, shipped pictures) live in HERE. Your settings and recordings live in
# %APPDATA%\ElgansitoDemolisher so they survive new downloads, re-unzipping, deleting the app
# folder, or opening the exe straight from inside the zip (Windows runs that from a temp folder).
HERE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
DATA_DIR = os.path.join(os.environ.get("APPDATA") or HERE, "ElgansitoDemolisher")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
TEMPLATE_DIR = os.path.join(DATA_DIR, "templates")   # your captured pictures and recordings
APP_TEMPLATES = os.path.join(HERE, "templates")      # pictures that ship with the app (prompts)
OLD_CONFIG = os.path.join(HERE, "config.json")       # where versions before 1.1 kept settings

DEEPWOKEN_UNIVERSE = 1359573625
DEEPWOKEN_PLACE = 4111023553

DEFAULT_DETECT = {
    "type": "color_area",
    "region": [760, 480, 360, 360],
    "color": [255, 255, 255],
    "tolerance": 30,
    "min_fraction": 0.04,
    "point": [960, 540],
    "template": "",
    "threshold": 0.8,
}

# Tuned on a 1920x1080 recording: a landed parry's yellow spark fills ~13-16% of this
# area around the character (less when the camera is zoomed out), blocked hits only ~1.5%.
PARRY_SPARK = dict(DEFAULT_DETECT, color=[237, 209, 81], tolerance=45, min_fraction=0.025)


def new_reset(name="New reset", key="f", enabled=False, detect=None, window_ms=450):
    """Something that puts a cooldown back to ready when it's seen on screen
    shortly after pressing `key` (a parry landing, an M1 hitting...)."""
    return {"name": name, "enabled": enabled, "key": key, "toggle_key": "", "window_ms": window_ms,
            "detect": copy.deepcopy(detect or DEFAULT_DETECT)}


DEFAULTS = {
    "game_window": "Roblox",
    "toggle_key": "f6",
    "pick_key": "f7",
    "hide_key": "f8",                # hides / shows the app window and overlays
    # Auto wisp: types the letters in Deepwoken's ritual box (C / X / V / Z) for you, while macros are on.
    "wisp": {"enabled": False, "delay_ms": 0, "hold_ms": 40, "retry_ms": 350, "confirm": True, "area": None},
    # Mouse buttons that press a key instead (in game, while macros are on), e.g. side button -> 9.
    "remaps": [{"button": "mouse_x1", "key": "9", "enabled": False},
               {"button": "mouse_x2", "key": "0", "enabled": False}],
    "chat_key": "enter",             # opens the party message box in game
    "performance": "balanced",        # light / balanced / max: how hard the background loops work
    "notify": {"enabled": True, "sound_on": True, "sound": "", "image": "", "volume": 70, "seconds": 4,
               "party_low": True},
    "builder": {"url": "", "name": "", "talents": [], "obtained": [], "watch": False,
                "highlight": True, "mark_out": True, "list_on_cards": True, "max_rows": 12, "all": []},
    "music": {"tracks": [], "volume": 60, "loop": True, "shuffle": False},
    "start_active": False,
    "monitor": 1,
    "scan_interval_ms": 50,
    # bar_style "flat" = plain thick parry/dodge bars (flat_width x flat_height px), "card" = with name + time
    "ui": {"click_sound": True, "volume": 60, "animations": True, "display_name": "ELGANSITO",
           "tagline": "EDGERUNNER // LV.20", "pfp": "", "background": "", "background_dim": 70},
    "overlay": {"locked": False, "opacity": 0.92, "bar_style": "flat", "flat_width": 178, "flat_height": 12, "flat_outline": 1,
                "party_width": 400, "party_bar": 12, "party_style": "cyber", "party_chat_lines": 3, "party_info_size": 10,
                "hide_unfocused": True},
    "widgets": {},
    # Deepwoken's cooldown bubbles under the health bar (1920x1080): bars sync to them.
    "cd_icons": {"enabled": True, "x": [933, 951, 969, 987], "y": [928, 962]},
    # Deepwoken's hotbar along the bottom (1920x1080): mantra bars follow how dark their slot is.
    "hotbar": {"x0": 564, "step": 72, "y": [1004, 1058], "half": 26},
    # Where the Deepwoken server name is (top left info block, 1920x1080).
    "server_name": {"region": [452, 8, 188, 26]},
    # Your own health, read off your health bar (1920x1080 defaults).
    "my_hp": {
        "region": [722, 880, 476, 50],
        # raw bar fill -> real %, measured: the fill reads 0.924 when the game says 91%
        "calibration": [[0.924, 0.91]],
    },
    # Share your HP with friends who run Elgansito Demolisher Macro with the same party code.
    "party": {
        "enabled": False,
        "username": "",
        "code": "",
        "friends": [],
        "broker": "broker.emqx.io",
        "port": 8883,
        "quick": ["need help!", "on my way", "low hp, backing off", "gg"],
        # Hotkeys that send a message straight away, without opening the box.
        "binds": [{"key": "", "text": "HELP!"}, {"key": "", "text": "on my way"},
                  {"key": "", "text": "low hp, backing off"}, {"key": "", "text": "ganked, come now"}],
    },
    # Answer party messages by voice: listens on this mic for a few seconds after a message arrives
    # (or while the voice key is held) and sends the phrase you said.
    "voice": {"enabled": False, "mic": "", "listen_s": 6, "key": "",
              "phrases": ["yes", "no", "on my way", "need help", "wait", "coming", "okay", "thanks", "run", "low hp"]},
    # Press Deepwoken's Z / X / C / V prompts when they show up (never the teal fakes).
    "prompts": {
        "enabled": False,
        "region": [480, 150, 960, 700],
        "threshold": 0.82,
        "delay_ms": 0,
    },
    "roblox": {
        "auto_enable": True,
        "games": [{"name": "Deepwoken", "universe_id": DEEPWOKEN_UNIVERSE}],
        "fastflags_file": "",
        "start_with_windows": False,
    },
    "cooldowns": [
        {
            "name": "Dodge",
            "key": "q",
            "cooldown_ms": 750,
            "color": "#69b9e8",
            "icon_slot": 0,   # the game's roll bubble stays dim far longer than you actually have to wait
            "cancel": {"enabled": True, "key": "mouse_right", "window_ms": 350, "cooldown_ms": 0, "max_refunds": 1},
            "resets": [new_reset("Blade Dancer (M1 hit)", "mouse_left", window_ms=350)],
        },
        {
            "name": "Parry",
            "key": "f",
            "cooldown_ms": 1200,
            "color": "#3bb967",
            "icon_slot": 2,
            "cancel": {"enabled": False, "key": "mouse_right", "window_ms": 350, "cooldown_ms": 0, "max_refunds": 1},
            "resets": [new_reset("Parry landed", "f", True, PARRY_SPARK)],
        },
    ],
    "macros": [
        {
            "name": "Roll uppercut",
            "enabled": True,
            "hotkey": "t",
            "block_key": False,
            "mode": "once",
            "interval_ms": 100,
            "steps": [
                {"action": "down", "key": "ctrl"},
                {"action": "wait", "ms": 80},
                {"action": "tap", "key": "q", "ms": 30},
                {"action": "wait", "ms": 30},
                {"action": "click", "button": "right", "ms": 25},
                {"action": "up", "key": "ctrl"},
            ],
        },
        {
            "name": "Spam F",
            "enabled": True,
            "hotkey": "mouse_x2",
            "block_key": False,
            "mode": "hold",
            "interval_ms": 30,
            "steps": [{"action": "tap", "key": "f", "ms": 15}],
        },
        {
            "name": "roll m1",
            "enabled": True,
            "hotkey": "c",
            "block_key": False,
            "mode": "once",
            "interval_ms": 100,
            "steps": [
                {"action": "tap", "key": "q", "ms": 125},
                {"action": "click", "button": "right", "ms": 75},
                {"action": "click", "button": "left", "ms": 25},
            ],
        },
    ],
    "rules": [],
}


def new_cooldown(name="New cooldown"):
    cd = copy.deepcopy(DEFAULTS["cooldowns"][1])
    cd.update(name=name, key="e", color="#a78bfa", resets=[], icon_slot=0, hotbar_slot=0)
    return cd


def new_macro(name="New macro"):
    return {"name": name, "enabled": True, "hotkey": "", "block_key": False, "mode": "once", "interval_ms": 100,
            "steps": [{"action": "tap", "key": "e", "ms": 25}]}


def new_member(name="Friend"):
    return {"name": name, "region": None}


def new_rule(name="New screen rule"):
    detect = copy.deepcopy(DEFAULT_DETECT)
    detect.update(type="image", region=[860, 440, 200, 200])
    return {"name": name, "enabled": True, "detect": detect, "trigger": "on_appear", "cooldown_ms": 500,
            "action": {"type": "none", "key": "space", "button": "left", "at": "match", "point": [960, 540],
                       "return_mouse": True, "ms": 30}}


def _fill(cfg, defaults):
    for key, value in defaults.items():
        if key not in cfg:
            cfg[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(cfg[key], dict):
            _fill(cfg[key], value)


def _migrate(cfg):
    # Older configs used "combos" and flat rules.
    if "combos" in cfg and "macros" not in cfg:
        cfg.pop("combos")
        cfg["macros"] = copy.deepcopy(DEFAULTS["macros"])
        cfg["rules"] = [r for r in cfg.get("rules", []) if "detect" in r]
        for cd in cfg.get("cooldowns", []):
            cd.setdefault("cancel", {}).setdefault("enabled", bool(cd["cancel"].get("key")))
    cfg.pop("capture_size", None)
    # One "reset_detect" per cooldown became a list of "resets"; use the tuned defaults.
    defaults = {cd["name"]: cd for cd in DEFAULTS["cooldowns"]}
    for cd in cfg.get("cooldowns", []):
        old = cd.pop("reset_detect", None)
        if "resets" in cd:
            continue
        if cd["name"] in defaults:
            cd["resets"] = copy.deepcopy(defaults[cd["name"]]["resets"])
        elif old and old.get("enabled"):
            detect = {k: v for k, v in old.items() if k not in ("enabled", "window_ms")}
            cd["resets"] = [new_reset(f"{cd['name']} lands", cd["key"], True, detect, old.get("window_ms", 450))]
    # Party HP used to come from a Matcha script's file; it's now shared between Elgansito Demolisher Macro users.
    party = cfg.get("party")
    if isinstance(party, dict) and ("names_file" in party or "members" in party):
        cfg["party"] = copy.deepcopy(DEFAULTS["party"])
    # Parry spark threshold lowered from 4% so zoomed-out landings still count.
    if not cfg.get("_parry_spark_v2"):
        cfg["_parry_spark_v2"] = True
        for cd in cfg.get("cooldowns", []):
            for r in cd.get("resets", []):
                d = r.get("detect", {})
                if d.get("color") == PARRY_SPARK["color"] and d.get("min_fraction") == 0.04:
                    d["min_fraction"] = PARRY_SPARK["min_fraction"]
    # Sync Dodge / Parry with the game's cooldown bubbles (roll = 1st, parry = 2nd).
    if not cfg.get("_icon_slots_v1"):
        cfg["_icon_slots_v1"] = True
        for cd in cfg.get("cooldowns", []):
            cd.setdefault("icon_slot", {"Dodge": 1, "Parry": 2}.get(cd.get("name"), 0))
    # v2.2: the roll bubble stays dim for 1.5-2.3 s while you can roll again after ~0.75 s, so the
    # Dodge bar runs on its own timer instead of following it.
    if not cfg.get("_dodge_v22"):
        cfg["_dodge_v22"] = True
        for cd in cfg.get("cooldowns", []):
            if cd.get("name") == "Dodge":
                cd["icon_slot"] = 0
                if cd.get("cooldown_ms") in (2000, 1750):
                    cd["cooldown_ms"] = 750
    # v2.5: cards are found anywhere on screen; an area picked for the old level-up-row reader would hide
    # the "Choose a Talent to Exchange" grid, so start from the whole screen again.
    if not cfg.get("_cards_v25"):
        cfg["_cards_v25"] = True
        if isinstance(cfg.get("builder"), dict):
            cfg["builder"].pop("cards", None)
    # v2.3: Enter opens the party message box (it was F4).
    if not cfg.get("_chat_enter_v23"):
        cfg["_chat_enter_v23"] = True
        if cfg.get("chat_key", "f4") == "f4":
            cfg["chat_key"] = "enter"
    # v2: Spam F macro (hold the side mouse button to spam parry).
    if not cfg.get("_macros_v2"):
        cfg["_macros_v2"] = True
        macros = cfg.setdefault("macros", [])
        if not any(m.get("name", "").lower() == "spam f" for m in macros):
            spam = copy.deepcopy(next(m for m in DEFAULTS["macros"] if m["name"] == "Spam F"))
            if any(m.get("hotkey") == spam["hotkey"] and m.get("enabled", True) for m in macros):
                spam["enabled"] = False
            macros.append(spam)
    # Flat bars: switch the old default colours to the light blue / green look.
    if not cfg.get("_flat_bars_v1"):
        cfg["_flat_bars_v1"] = True
        new = {"#4aa3ff": "#69b9e8", "#ffb347": "#3bb967"}
        for cd in cfg.get("cooldowns", []):
            cd["color"] = new.get(cd.get("color", "").lower(), cd.get("color"))
    # v1.1: Feint parry removed; Roll uppercut and roll m1 are the built-in macros.
    if not cfg.get("_macros_v11"):
        cfg["_macros_v11"] = True
        macros = [m for m in cfg.get("macros", []) if m.get("name") != "Feint parry"]
        names = {m.get("name", "").lower() for m in macros}
        hotkeys = {m.get("hotkey") for m in macros if m.get("enabled", True)}
        for m in DEFAULTS["macros"]:
            if m["name"].lower() not in names:
                m = copy.deepcopy(m)
                if m["hotkey"] in hotkeys:  # don't fight a macro you already put on that key
                    m["enabled"] = False
                macros.append(m)
        cfg["macros"] = macros


def normalise(cfg):
    _migrate(cfg)
    _fill(cfg, {k: v for k, v in DEFAULTS.items() if k not in ("cooldowns", "macros", "rules")})
    for cd in cfg.setdefault("cooldowns", []):
        _fill(cd, new_cooldown())
        for r in cd["resets"]:
            _fill(r, new_reset())
    for m in cfg.setdefault("macros", []):
        _fill(m, new_macro())
    for r in cfg.setdefault("rules", []):
        _fill(r, new_rule())
    return cfg


def find_old_config():
    """Settings from before 1.1 were kept next to the exe. On first start, carry over the newest
    one: next to this exe, or in an older download/unzip in Downloads or on the Desktop."""
    import glob
    home = os.path.expanduser("~")
    candidates = [OLD_CONFIG]
    for base in (os.path.join(home, "Downloads"), os.path.join(home, "Desktop")):
        for depth in ("*", os.path.join("*", "*"), os.path.join("*", "*", "*")):
            candidates += glob.glob(os.path.join(base, depth, "config.json"))
    found = []
    for path in set(candidates):
        try:
            with open(path, encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, dict) and "cooldowns" in data and "macros" in data:
                found.append((os.path.getmtime(path), path))
        except (OSError, ValueError):
            continue
    return max(found)[1] if found else None


def load():
    path = CONFIG_PATH
    if not os.path.exists(path):
        path = find_old_config() or path  # first start of 1.1: carry over your old settings
    if not os.path.exists(path):
        return normalise(copy.deepcopy(DEFAULTS))
    with open(path, encoding="utf-8-sig") as f:
        cfg = normalise(json.load(f))
    if path != CONFIG_PATH:
        save(cfg)
    return cfg


def _write(path, cfg):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)


def save(cfg):
    """Save the live settings, and keep the active profile in step with them."""
    _write(CONFIG_PATH, cfg)
    _write(profile_path(active_profile()), cfg)


# ---- profiles --------------------------------------------------------------------
# Named copies of the whole settings. The active one updates itself as you change things;
# switching loads another one into the live settings.

PROFILE_DIR = os.path.join(DATA_DIR, "profiles")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
DEFAULT_PROFILE = "Default"


def _clean_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(name)).strip().strip(".")
    return name[:40]


def profile_path(name):
    return os.path.join(PROFILE_DIR, _clean_name(name) + ".json")


def active_profile():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            name = json.load(f).get("profile")
        if name and os.path.exists(profile_path(name)):
            return name
    except (OSError, ValueError):
        pass
    return DEFAULT_PROFILE


def set_active_profile(name):
    _write(STATE_PATH, {"profile": _clean_name(name)})


def list_profiles():
    names = []
    if os.path.isdir(PROFILE_DIR):
        names = [os.path.splitext(f)[0] for f in os.listdir(PROFILE_DIR) if f.endswith(".json")]
    active = active_profile()
    if active not in names:
        names.append(active)
    return sorted(names, key=str.lower)


def load_profile(name):
    with open(profile_path(name), encoding="utf-8-sig") as f:
        return normalise(json.load(f))


def create_profile(name, cfg):
    """Save `cfg` as a new profile. Returns the name it was saved under, or raises ValueError."""
    name = _clean_name(name)
    if not name:
        raise ValueError("give the profile a name")
    if os.path.exists(profile_path(name)):
        raise ValueError(f"there's already a profile called {name}")
    _write(profile_path(name), cfg)
    return name


def rename_profile(old, new):
    new = _clean_name(new)
    if not new:
        raise ValueError("give the profile a name")
    if new.lower() != old.lower() and os.path.exists(profile_path(new)):
        raise ValueError(f"there's already a profile called {new}")
    was_active = active_profile() == old
    os.replace(profile_path(old), profile_path(new))
    if was_active:
        set_active_profile(new)
    return new


def delete_profile(name):
    if len(list_profiles()) <= 1:
        raise ValueError("you need at least one profile")
    if name == active_profile():
        raise ValueError("switch to another profile first")
    os.remove(profile_path(name))


def resolve(path):
    """A relative path: your data folder first (recordings, captures), then the app folder."""
    if os.path.isabs(path):
        return path
    for base in (DATA_DIR, HERE):
        full = os.path.join(base, path)
        if os.path.exists(full):
            return full
    return os.path.join(DATA_DIR, path)


def export(cfg, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def import_file(path):
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "cooldowns" not in data:
        raise ValueError("that file isn't an Elgansito Demolisher settings file")
    cfg = normalise(data)
    save(cfg)
    return cfg
