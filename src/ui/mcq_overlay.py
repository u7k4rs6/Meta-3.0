"""
src/ui/mcq_overlay.py
Unified MCQ overlay running in the same process via BaseOverlay.
Extremely minimal floating text overlay with a fully transparent background.
"""
from __future__ import annotations

import tkinter as tk
from src.core.overlay_base import BaseOverlay

# Using #000001 as the exact transparent key from legacy
BG      = "#000001"

class MCQOverlay(BaseOverlay):
    def __init__(self):
        super().__init__(
            title="mcq",
            alpha=1.0,
            bg=BG,
            width=80,
            height=40,
            pos_x=-1,
            pos_y=-1 # Handled in configure_window or build_content
        )
        self._lbl = None

    def _configure_window(self) -> None:
        super()._configure_window()
        try:
            self.root.attributes("-transparentcolor", BG)
        except Exception:
            pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"80x40+{sw - 110}+{sh - 110}")

    def _build_content(self) -> None:
        self._lbl = tk.Label(
            self.root, 
            text="—", 
            bg=BG, 
            fg="#00ff88", 
            font=("Segoe UI", 14, "bold"), 
            justify="center"
        )
        self._lbl.pack(fill="both", expand=True)
        
        self._bind_drag(self._lbl)

    def set_thinking(self) -> None:
        self.schedule(self._update_main, "...", "#555577")

    def set_answer(self, answer: str) -> None:
        self.schedule(self._update_main, answer, "#00ff88")

    def set_error(self, err_msg: str = "") -> None:
        self.schedule(self._update_main, "✕", "#ff5555")
        
    def set_log(self, log_msg: str) -> None:
        pass

    def _update_main(self, text: str, color: str) -> None:
        if self._lbl:
            self._lbl.config(text=text, fg=color)

    def stop(self) -> None:
        if self.root:
            self.schedule(self.root.destroy)
        self.visible = False




