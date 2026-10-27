"""Read and write Roblox FastFlags (ClientAppSettings.json).

Bootstrappers like Froststrap, Bloxstrap and Fishstrap keep their flags in
Modifications/ClientSettings/ClientAppSettings.json and copy them into Roblox
every launch, so that is the file to edit when one of them is installed. With
the plain Roblox launcher the file lives in the version folder.
"""
import glob
import json
import os
import sys

LOCAL = os.environ.get("LOCALAPPDATA", "")
BOOTSTRAPPERS = ["Froststrap", "Fishstrap", "Bloxstrap", "Voidstrap"]

# Well-known flags. Roblox only honours flags on its allowlist, so some may do nothing.
PRESETS = {
    "FPS cap": ("DFIntTaskSchedulerTargetFps", "240"),
    "Prefer Direct3D 11": ("FFlagDebugGraphicsPreferD3D11", "True"),
    "Anti-aliasing samples (0-8)": ("FIntDebugForceMSAASamples", "0"),
    "Disable post-processing": ("FFlagDisablePostFx", "True"),
    "Grass distance (0 = no grass)": ("FIntFRMMinGrassDistance", "0"),
}


# Your own FastFlag lists, shipped in assets/fastflags/*.json (one-click presets on the Roblox page).
def preset_sets():
    import config
    folder = config.resolve(os.path.join("assets", "fastflags"))
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        try:
            with open(path, encoding="utf-8-sig") as f:
                out[os.path.splitext(os.path.basename(path))[0]] = {str(k): str(v) for k, v in json.load(f).items()}
        except (OSError, ValueError):
            continue
    return out


# Official download pages (opened in your browser; nothing is downloaded by this app).
DOWNLOADS = {
    "Froststrap v1.5.0": "https://github.com/Froststrap/Froststrap/releases/tag/v1.5.0",
    "Bloxstrap (latest)": "https://github.com/bloxstraplabs/bloxstrap/releases/latest",
}


def merge_into(path, flags):
    """Add / overwrite these flags in a bootstrapper's file, keeping any other flags already there."""
    current = load(path)
    current.update(flags)
    save(path, current)
    return len(flags)


def targets():
    """[(label, path)] of every place flags can be written, best first."""
    out = []
    for name in BOOTSTRAPPERS:
        base = os.path.join(LOCAL, name)
        if os.path.isdir(base):
            out.append((f"{name} (applied when {name} starts Roblox)",
                        os.path.join(base, "Modifications", "ClientSettings", "ClientAppSettings.json")))
    for exe in sorted(glob.glob(os.path.join(LOCAL, "Roblox", "Versions", "*", "RobloxPlayerBeta.exe")),
                      key=os.path.getmtime, reverse=True):
        folder = os.path.dirname(exe)
        out.append((f"Roblox {os.path.basename(folder)} (plain Roblox)",
                    os.path.join(folder, "ClientSettings", "ClientAppSettings.json")))
    return out


def launchers():
    """[(name, exe)] of installed bootstrappers, Froststrap first."""
    out = []
    for name in BOOTSTRAPPERS:
        exe = os.path.join(LOCAL, name, f"{name}.exe")
        if os.path.exists(exe):
            out.append((name, exe))
    return out


def launch(exe, place_id=None):
    """Start Roblox through a bootstrapper, the same way it does for links on the website."""
    import subprocess
    args = [exe, "-player"]
    if place_id:
        args.append(f"roblox://experiences/start?placeId={place_id}")
    subprocess.Popen(args, cwd=os.path.dirname(exe))


def open_menu(exe):
    import subprocess
    subprocess.Popen([exe, "-menu"], cwd=os.path.dirname(exe))


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    return {str(k): v if isinstance(v, str) else json.dumps(v) for k, v in data.items()}


def save(path, flags):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(flags, f, indent=2)
    os.replace(tmp, path)


def parse_json(text):
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("paste a JSON object like {\"FlagName\": \"value\"}")
    return {str(k): v if isinstance(v, str) else json.dumps(v) for k, v in data.items()}


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pythonw}" "{os.path.abspath(sys.argv[0])}"'


def set_start_with_windows(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        for old in ("ScreenMacro", "ElgansitoDemolisherMacro"):
            try:
                winreg.DeleteValue(key, old)
            except FileNotFoundError:
                pass
        if on:
            winreg.SetValueEx(key, "ElgansitoDemolisherMacro", 0, winreg.REG_SZ, launch_command())
