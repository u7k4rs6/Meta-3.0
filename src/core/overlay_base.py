"""
src/core/overlay_base.py
Base Tkinter floating window: always-on-top, capture exclusion,
drag, configurable alpha/colors. All overlays inherit from this.
"""
from __future__ import annotations

import ctypes
import threading
from typing import Optional

import tkinter as tk

WDA_EXCLUDEFROMCAPTURE   = 0x00000011
DWMWA_WINDOW_CORNER_PREF = 33
DWMWCP_ROUND             = 2


class BaseOverlay:
    """
    Minimal floating window base class.
    Subclasses call super().__init__() then override _build_content().
    """

    def __init__(self, title: str = "overlay", alpha: float = 0.92,
                 bg: str = "#0e0e1a", width: int = 580, height: int = 560,
                 pos_x: int = -1, pos_y: int = 24):
        self.title   = title
        self.alpha   = alpha
        self.bg      = bg
        self.width   = width
        self.height  = height
        self.pos_x   = pos_x
        self.pos_y   = pos_y

        self.root:    Optional[tk.Tk] = None
        self._hwnd:   int = 0
        self._ready   = threading.Event()
        self.visible: bool = False
        self._drag_x  = 0
        self._drag_y  = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the Tk main loop in a background daemon thread."""
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        self._ready.wait()

    def _run(self) -> None:
        self.root = tk.Tk()
        self._configure_window()
        self._apply_win32()
        self._build_content()
        self._ready.set()
        self.root.mainloop()

    # ── Win32 helpers ─────────────────────────────────────────────────────────

    def _configure_window(self) -> None:
        self.root.title(self.title)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.alpha)
        self.root.configure(bg=self.bg)
        self.root.withdraw()

        sw = self.root.winfo_screenwidth()
        x  = (sw - self.width - 30) if self.pos_x < 0 else self.pos_x
        self.root.geometry(f"{self.width}x{self.height}+{x}+{self.pos_y}")

    def _apply_win32(self) -> None:
        self.root.update()
        self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        self._apply_capture_exclusion()
        try:
            val = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                self._hwnd, DWMWA_WINDOW_CORNER_PREF,
                ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            pass

    def _apply_capture_exclusion(self) -> None:
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(
                self._hwnd, WDA_EXCLUDEFROMCAPTURE
            )
        except Exception as e:
            print(f"logs: Capture exclusion error: {e}", flush=True)

    # ── To be overridden ─────────────────────────────────────────────────────

    def _build_content(self) -> None:
        """Subclasses build their widgets here."""
        pass

    # ── Drag support ─────────────────────────────────────────────────────────

    def _bind_drag(self, widget: tk.Widget) -> None:
        widget.bind("<Button-1>",  self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)

    def _drag_start(self, event) -> None:
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event) -> None:
        self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    # ── Public visibility API ─────────────────────────────────────────────────

    def show(self) -> None:
        if not self.root:
            return
        def _u():
            self.root.deiconify()
            self.root.lift()
            self.root.update()
            self._apply_capture_exclusion()
            self.visible = True
        self.root.after(0, _u)

    def hide(self) -> None:
        if not self.root:
            return
        def _u():
            self.root.withdraw()
            self.visible = False
        self.root.after(0, _u)

    def toggle(self) -> None:
        if self.visible:
            self.hide()
        else:
            self.show()

    def schedule(self, fn, *args) -> None:
        """Thread-safe way to schedule a UI update."""
        if self.root:
            self.root.after(0, lambda: fn(*args))
