"""
src/ui/mcq_overlay.py
Subprocess wrapper for the MCQ overlay.
Runs the transparent Tkinter GUI in an isolated process to prevent mainloop crashes.
"""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
import sys

class MCQOverlay:
    def __init__(self):
        self._proc = None

    def start(self) -> None:
        """Launches the overlay process."""
        script_path = Path(__file__).parent / "mcq_overlay_proc.py"
        self._proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )

    def _send(self, msg: str) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write(msg + "\n")
                self._proc.stdin.flush()
            except Exception:
                pass

    def set_thinking(self) -> None:
        # No automatic SHOW per user request
        self._send("THINK:")

    def set_answer(self, answer: str) -> None:
        # No automatic SHOW per user request
        self._send(f"ANS:{answer}")

    def set_error(self) -> None:
        # No automatic SHOW per user request
        self._send("ERR:")

    def toggle(self) -> None:
        self._send("TOGGLE")

    def hide(self) -> None:
        self._send("HIDE")

    def stop(self) -> None:
        self._send("EXIT")
        if self._proc:
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
