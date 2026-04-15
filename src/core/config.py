"""
src/core/config.py
Single source of truth for all application settings.
Persists to settings.json. Merges defaults so missing keys never crash.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict

# ── Path Resolution ───────────────────────────────────────────────────────────

def get_root_dir() -> Path:
    """Get the directory where settings.json and .env should live."""
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle (.exe)
        return Path(sys.executable).parent
    else:
        # Running as a normal script
        # src/core/config.py -> parent(core) -> parent(src) -> parent(root)
        return Path(__file__).parent.parent.parent

_ROOT = get_root_dir()
SETTINGS_PATH = _ROOT / "settings.json"
ENV_PATH      = _ROOT / ".env"


# ── Sub-configs ───────────────────────────────────────────────────────────────

@dataclass
class OverlayConfig:
    alpha: float       = 0.92
    bg_color: str      = "#0e0e1a"
    fg_color: str      = "#c8c8d0"
    accent_color: str  = "#7c6af7"
    width: int         = 580
    height: int        = 560
    pos_x: int         = -1   # -1 = auto (right edge)
    pos_y: int         = 24


@dataclass
class TypingConfig:
    delay_min: float    = 0.05
    delay_max: float    = 0.12
    startup_delay: float = 2.0
    multifile_mode: bool = False


@dataclass
class AudioConfig:
    interval: float    = 10.0   # seconds between transcription flushes
    threshold: float   = 150.0  # RMS volume threshold


@dataclass
class HotkeyConfig:
    # Common
    add_screenshot:  str = "k+,"
    send:            str = "k+."
    clear_queue:     str = "k+/"
    toggle_overlay:  str = "m+n"
    clear_memory:    str = "k+c"
    # AutoType / Multifile
    stop_typing:     str = "k+x"
    pause_typing:    str = "a+s"
    next_file:       str = "k+n"
    retype:          str = "k+r"
    # Transcript
    send_transcript: str = "k+."
    send_with_shot:  str = "k+,"


@dataclass
class Config:
    api_key:      str          = ""
    models:       List[str]    = field(default_factory=lambda: [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
    ])
    active_agent: str          = "full_control"
    overlay:      OverlayConfig  = field(default_factory=OverlayConfig)
    typing:       TypingConfig   = field(default_factory=TypingConfig)
    audio:        AudioConfig    = field(default_factory=AudioConfig)
    hotkeys:      HotkeyConfig   = field(default_factory=HotkeyConfig)


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_env_key() -> str:
    """Read GEMINI_API_KEY from .env if it exists."""
    if ENV_PATH.exists():
        try:
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY"):
                    _, _, val = line.partition("=")
                    return val.strip().strip('"').strip("'")
        except Exception:
            pass
    return os.environ.get("GEMINI_API_KEY", "")


def _save_env_key(key: str) -> None:
    """Write GEMINI_API_KEY to .env file."""
    lines = []
    found = False
    if ENV_PATH.exists():
        try:
            for line in ENV_PATH.read_text().splitlines():
                if line.strip().startswith("GEMINI_API_KEY"):
                    lines.append(f"GEMINI_API_KEY={key}")
                    found = True
                else:
                    lines.append(line)
        except Exception:
            pass
    
    if not found:
        lines.append(f"GEMINI_API_KEY={key}")
    
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")


def _deep_merge(defaults: dict, saved: dict) -> dict:
    """Recursively merge saved dict on top of defaults, so new keys are preserved."""
    result = dict(defaults)
    for k, v in saved.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> Config:
    """Load config from settings.json, falling back to defaults."""
    default_dict = asdict(Config())

    if SETTINGS_PATH.exists():
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            merged = _deep_merge(default_dict, saved)
        except Exception:
            merged = default_dict
    else:
        merged = default_dict

    # Always pull API key from .env (security)
    merged["api_key"] = _load_env_key()

    cfg = Config(
        api_key=merged["api_key"],
        models=merged["models"],
        active_agent=merged["active_agent"],
        overlay=OverlayConfig(**merged["overlay"]),
        typing=TypingConfig(**merged["typing"]),
        audio=AudioConfig(**merged["audio"]),
        hotkeys=HotkeyConfig(**merged["hotkeys"]),
    )
    return cfg


def save_config(cfg: Config) -> None:
    """Persist config to settings.json and API key to .env."""
    # Save API key to .env
    if cfg.api_key:
        _save_env_key(cfg.api_key)

    # Save other settings to settings.json
    d = asdict(cfg)
    d.pop("api_key", None)   # never write key to json
    try:
        SETTINGS_PATH.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error saving settings: {e}")
