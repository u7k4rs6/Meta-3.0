"""
src/core/hotkey_manager.py
Observer-based hotkey registry using pynput.
Agents register combos as strings like "k+," or "m+n".
Config keys are wired at runtime so changing settings rewires hotkeys.
"""
from __future__ import annotations

import threading
from typing import Callable, Dict, Set, Optional
from pynput import keyboard
from pynput.keyboard import Key


# ── Combo parsing ─────────────────────────────────────────────────────────────

def _parse_combo(combo_str: str) -> frozenset:
    """
    Parse a hotkey combo string like "k+," or "m+n" into
    a frozenset of lowercase character strings.
    """
    parts = combo_str.lower().split("+")
    return frozenset(p.strip() for p in parts if p.strip())


def _get_char(key) -> Optional[str]:
    try:
        return key.char
    except AttributeError:
        return None


# ── Manager ───────────────────────────────────────────────────────────────────

class HotkeyManager:
    """
    Maintains a registry of {frozenset_of_keys: callback}.
    A single pynput listener tracks all currently-held keys and
    fires a callback when a registered combo is fully held.
    """

    def __init__(self):
        self._registry:      Dict[frozenset, Callable] = {}
        self._pressed_keys:  Set = set()
        self._listener:      Optional[keyboard.Listener] = None
        self._lock           = threading.Lock()

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, combo: str, callback: Callable) -> None:
        """Register a hotkey combo string → callback."""
        key_set = _parse_combo(combo)
        with self._lock:
            self._registry[key_set] = callback

    def unregister(self, combo: str) -> None:
        key_set = _parse_combo(combo)
        with self._lock:
            self._registry.pop(key_set, None)

    def clear(self) -> None:
        with self._lock:
            self._registry.clear()

    # ── Listener lifecycle ────────────────────────────────────────────────────

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        print("logs: HotkeyManager started.", flush=True)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def join(self) -> None:
        """Block until the listener is stopped (for terminal mode)."""
        if self._listener:
            self._listener.join()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _on_press(self, key) -> None:
        self._pressed_keys.add(key)
        # Build set of lowercase chars currently held
        chars = set()
        for k in self._pressed_keys:
            c = _get_char(k)
            if c:
                chars.add(c.lower())

        with self._lock:
            for combo, callback in list(self._registry.items()):
                if combo.issubset(chars):
                    self._pressed_keys.clear()   # prevent repeat-fire
                    threading.Thread(target=callback, daemon=True).start()
                    break

    def _on_release(self, key) -> None:
        self._pressed_keys.discard(key)
