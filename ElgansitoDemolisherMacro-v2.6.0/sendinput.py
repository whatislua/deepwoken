"""Keyboard and mouse input through Windows SendInput.

Keys are sent as hardware scan codes, which games like Roblox pick up more
reliably than the virtual-key events most Python libraries send.
"""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.VkKeyScanW.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x1
KEYEVENTF_KEYUP = 0x2
KEYEVENTF_SCANCODE = 0x8
MAPVK_VK_TO_VSC = 0

# button -> (down flag, up flag, mouseData)
MOUSE_FLAGS = {"left": (0x2, 0x4, 0), "right": (0x8, 0x10, 0), "middle": (0x20, 0x40, 0),
               "x1": (0x80, 0x100, 1), "x2": (0x80, 0x100, 2)}

VK = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "space": 0x20, "enter": 0x0D,
    "tab": 0x09, "esc": 0x1B, "backspace": 0x08, "caps_lock": 0x14,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23, "page_up": 0x21, "page_down": 0x22,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
}
EXTENDED = {"up", "down", "left", "right", "insert", "delete", "home", "end", "page_up", "page_down"}

# Every key name the app understands, for dropdowns.
KEY_NAMES = [chr(c) for c in range(ord("a"), ord("z") + 1)] + [str(d) for d in range(10)] + list(VK)
MOUSE_BUTTONS = list(MOUSE_FLAGS)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send(inp):
    if not user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)):
        raise OSError(f"SendInput failed ({ctypes.get_last_error()})")


def vk_for(name):
    name = name.lower()
    if len(name) == 1:
        code = user32.VkKeyScanW(ord(name))
        if code == -1:
            raise ValueError(f"no key for '{name}'")
        return code & 0xFF
    if name not in VK:
        raise ValueError(f"unknown key '{name}'")
    return VK[name]


def _key(name, flags):
    vk = vk_for(name)
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags |= KEYEVENTF_SCANCODE
    if name.lower() in EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    _send(INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags))))


def key_down(name):
    _key(name, 0)


def key_up(name):
    _key(name, KEYEVENTF_KEYUP)


def tap(name, hold_ms=25):
    key_down(name)
    time.sleep(hold_ms / 1000)
    key_up(name)


def _mouse(button, index):
    flags = MOUSE_FLAGS[button]
    _send(INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(mouseData=flags[2], dwFlags=flags[index]))))


def mouse_down(button="left"):
    _mouse(button, 0)


def mouse_up(button="left"):
    _mouse(button, 1)


def move_to(x, y):
    user32.SetCursorPos(int(x), int(y))


def cursor_pos():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def click(button="left", hold_ms=25):
    mouse_down(button)
    time.sleep(hold_ms / 1000)
    mouse_up(button)
