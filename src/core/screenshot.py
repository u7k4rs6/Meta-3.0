"""
src/core/screenshot.py
Screen capture helpers. Single implementation for all agents.
"""
from __future__ import annotations

import io
from PIL import Image
import mss


def take_screenshot(monitor: int = 0) -> Image.Image:
    """Capture the full screen (monitor 0 = all monitors combined)."""
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[monitor])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    """Convert a PIL Image to raw bytes."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()
