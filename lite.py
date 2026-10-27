"""Elgansito Lite: the same app with only the key features, for the lowest CPU and memory use.

Keeps: cooldown bars (with the game's cooldown bubbles), macros, profiles, overlays, the Roblox page
and FastFlags. Leaves out: Party HP, key prompts, Builder 101, screen rules, music, and the
background screen reading those need. Settings and profiles are shared with the full app.
"""
import os

os.environ["ELGANSITO_LITE"] = "1"

import app  # noqa: E402  (must come after the flag above)

if __name__ == "__main__":
    app.run()
