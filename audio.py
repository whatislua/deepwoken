"""Plays audio files with Windows' built-in media player (MCI): mp3, wav, m4a, wma, and the sound
of mp4 videos. No extra libraries, nothing downloaded, nothing streamed."""
import ctypes
import os

_winmm = ctypes.windll.winmm
_winmm.mciSendStringW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)

AUDIO_TYPES = "Audio and video (*.mp3 *.wav *.m4a *.wma *.aac *.mp4 *.mkv *.webm *.ogg *.flac)"


def _cmd(command):
    buf = ctypes.create_unicode_buffer(256)
    err = _winmm.mciSendStringW(command, buf, 255, None)
    if err:
        msg = ctypes.create_unicode_buffer(256)
        _winmm.mciGetErrorStringW(err, msg, 255)
        raise RuntimeError(msg.value or f"MCI error {err}")
    return buf.value


class Track:
    """One open audio file under an alias. MCI aliases are per-process, so each player uses its own."""

    def __init__(self, alias):
        self.alias = alias
        self.path = None

    def open(self, path):
        self.close()
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        _cmd(f'open "{path}" type mpegvideo alias {self.alias}')
        self.path = path

    def play(self, volume=80, start_ms=0):
        if not self.path:
            return
        self.set_volume(volume)
        _cmd(f"play {self.alias} from {int(start_ms)}")

    def pause(self):
        if self.path:
            _cmd(f"pause {self.alias}")

    def resume(self):
        if self.path:
            _cmd(f"resume {self.alias}")

    def set_volume(self, volume):
        if self.path:
            try:
                _cmd(f"setaudio {self.alias} volume to {int(max(0, min(volume, 100)) * 10)}")
            except RuntimeError:
                pass  # some formats can't change volume; play anyway

    def mode(self):
        """'playing', 'paused', 'stopped' or '' when nothing is open."""
        if not self.path:
            return ""
        try:
            return _cmd(f"status {self.alias} mode")
        except RuntimeError:
            return ""

    def position(self):
        try:
            return int(_cmd(f"status {self.alias} position") or 0)
        except (RuntimeError, ValueError):
            return 0

    def length(self):
        try:
            return int(_cmd(f"status {self.alias} length") or 0)
        except (RuntimeError, ValueError):
            return 0

    def close(self):
        if self.path:
            try:
                _cmd(f"close {self.alias}")
            except RuntimeError:
                pass
        self.path = None


_effect = Track("elgansito_effect")


def play_effect(path, volume=80):
    """Fire-and-forget sound (notifications). Returns False if the file can't be played."""
    try:
        _effect.open(path)
        _effect.play(volume)
        return True
    except Exception:
        return False
