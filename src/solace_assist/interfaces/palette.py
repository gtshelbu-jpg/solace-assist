"""Optional, read-only Solace palette bridge; no desktop/runtime dependencies."""

import os
from pathlib import Path
import re
import tomllib


DEFAULT_PALETTE = {
    "primary": "#94b8ad", "secondary": "#94b8ad", "accent": "#94b8ad",
    "background": "#101514", "foreground": "#d5dedb",
    "surface": "#19231f", "panel": "#19231f",
    "success": "#8bbf9c", "warning": "#d2b77b", "error": "#d88796", "dark": True,
}


def system_palette_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "solace/current/theme/colors.toml"


def load_palette(path):
    """Return validated Textual theme fields, or None for unavailable/invalid data."""
    try:
        path = Path(path)
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            return None
        colors = tomllib.loads(raw.decode("utf-8"))

        def color(key, fallback=None):
            value = colors.get(key, fallback)
            if not isinstance(value, str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", value):
                raise ValueError("Invalid palette color")
            return value.lower()

        background = color("background")
        foreground = color("foreground")
        accent = color("accent")
        mode = colors.get("mode")
        if mode not in (None, "light", "dark"):
            return None
        # Older/minimal palettes may not declare a mode.
        rgb = [int(background[i:i+2], 16) for i in (1, 3, 5)]
        dark = mode == "dark" if mode else sum(c * w for c, w in zip(rgb, (0.2126, 0.7152, 0.0722))) < 128
        surface = color("lighter_bg", background)
        return {
            "primary": accent, "secondary": accent, "accent": accent,
            "background": background, "foreground": foreground,
            "surface": surface, "panel": surface,
            "success": color("green", colors.get("color2", "#458d59")),
            "warning": color("yellow", colors.get("color3", "#b59435")),
            "error": color("red", colors.get("color1", "#d04c5b")),
            "dark": dark,
        }
    except (OSError, ValueError, UnicodeError, TypeError):
        return None
