"""
src/ui/chat_overlay.py
Unified chat overlay for Full Control agent.

Features:
  - Rounded window corners (DWM) + rounded input field feel
  - Manual mode: typed chat + screenshot button + hold-mic
  - Auto mode toggle: 🔊 speaker icon — lights up when active
  - Memory-aware follow-ups (handled by agent layer)
  - Markdown-rendered AI responses
  - Debounce "Auto" badge in header when auto-mode is on
"""
from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable, Optional

from src.core.overlay_base import BaseOverlay
from src.ui.markdown_renderer import MarkdownRenderer

# ── Colour palette ─────────────────────────────────────────────────────────────
BG        = "#0e0e1a"
BG2       = "#13132a"
BG3       = "#1a1a30"
BORDER    = "#2a2260"
FG        = "#c8c8d0"
FG_DIM    = "#44446a"
FG_PH     = "#333360"       # placeholder
ACC       = "#7c6af7"       # purple accent
ACC2      = "#9b8fff"
GREEN     = "#3a9f6e"
AMBER     = "#e0a050"
RED_C     = "#ff5555"
AUTO_ON   = "#e0a050"       # speaker icon active colour
AUTO_OFF  = "#44446a"       # speaker icon inactive colour


class ChatOverlay(BaseOverlay):

    def __init__(self, cfg=None):
        alpha  = cfg.alpha        if cfg else 0.92
        bg     = cfg.bg_color     if cfg else BG
        width  = cfg.width        if cfg else 600
        height = cfg.height       if cfg else 580
        pos_x  = cfg.pos_x       if cfg else -1
        pos_y  = cfg.pos_y       if cfg else 24
        accent = cfg.accent_color if cfg else ACC

        super().__init__(
            title="ai-overlay",
            alpha=alpha,
            bg=bg,
            width=width,
            height=height,
            pos_x=pos_x,
            pos_y=pos_y,
        )

        self._accent          = accent
        self.renderer:        Optional[MarkdownRenderer] = None
        self.is_thinking:     bool = False
        self.mic_active:      bool = False
        self.auto_active:     bool = False

        # ── Callbacks (set by agent before .start()) ──────────────────────────
        self.on_send:          Optional[Callable[[str], None]]   = None
        self.on_clear:         Optional[Callable[[], None]]      = None
        self.on_mic_start:     Optional[Callable[[], None]]      = None
        self.on_mic_stop:      Optional[Callable[[], None]]      = None
        self.on_auto_toggle:   Optional[Callable[[bool], None]]  = None   # NEW
        self.on_screenshot:    Optional[Callable[[], None]]      = None   # NEW

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_content(self) -> None:
        bg     = BG
        accent = self._accent

        # ── Outer border (1px purple glow) ────────────────────────────────────
        outer = tk.Frame(self.root, bg=BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=bg, padx=14, pady=12)
        inner.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(inner, bg=bg)
        header.pack(fill="x", pady=(0, 4))

        self._title_lbl = tk.Label(
            header, text="✦  Full Control",
            bg=bg, fg=accent, font=("Segoe UI", 10, "bold")
        )
        self._title_lbl.pack(side="left")

        # Auto badge (hidden by default)
        self._auto_badge = tk.Label(
            header, text=" AUTO ",
            bg=AMBER, fg="#1a0e00", font=("Segoe UI", 7, "bold"),
            padx=4
        )
        # Not packed yet — shown when auto is on

        # Header buttons (right-aligned, pack RTL)
        def _hbtn(txt, color=FG_DIM):
            b = tk.Label(header, text=txt, bg=bg, fg=color,
                         font=("Segoe UI", 11), cursor="hand2", padx=2)
            b.pack(side="right", padx=2)
            return b

        close_btn = _hbtn(" ✕ ")
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>",    lambda e: close_btn.config(fg=RED_C))
        close_btn.bind("<Leave>",    lambda e: close_btn.config(fg=FG_DIM))

        clear_btn = _hbtn(" ⟳ ")
        clear_btn.bind("<Button-1>", lambda e: self._clear_chat())
        clear_btn.bind("<Enter>",    lambda e: clear_btn.config(fg=AMBER))
        clear_btn.bind("<Leave>",    lambda e: clear_btn.config(fg=FG_DIM))

        # 🔊 Auto-toggle button (speaker)
        self._auto_btn = _hbtn(" 🔊 ", color=AUTO_OFF)
        self._auto_btn.bind("<Button-1>", lambda e: self._toggle_auto())
        self._auto_btn.bind("<Enter>",    lambda e: self._auto_btn.config(fg=AMBER)
                            if not self.auto_active else None)
        self._auto_btn.bind("<Leave>",    lambda e: self._auto_btn.config(
                            fg=AUTO_ON if self.auto_active else AUTO_OFF))

        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", pady=(4, 0))

        # ── Input area (bottom-packed first so it anchors correctly) ──────────
        input_container = tk.Frame(inner, bg=bg)
        input_container.pack(side="bottom", fill="x")

        # Hint bar
        self._hint_lbl = tk.Label(
            input_container,
            text="m+n hide  •  k+, queue shot  •  k+. send  •  k+c clear",
            bg=bg, fg="#1e1e40", font=("Segoe UI", 7)
        )
        self._hint_lbl.pack(side="bottom", pady=(3, 0))

        input_row = tk.Frame(input_container, bg=bg)
        input_row.pack(side="bottom", fill="x", pady=(0, 2))

        tk.Frame(input_container, bg=BG3, height=1).pack(side="bottom", fill="x", pady=(6, 3))

        # ── 🎤 Mic button ──────────────────────────────────────────────────────
        self.mic_btn = tk.Label(
            input_row, text=" 🎤 ", bg=BG2, fg=FG_DIM,
            font=("Segoe UI", 13), cursor="hand2", padx=8, pady=6
        )
        self.mic_btn.pack(side="left", padx=(0, 6))
        self.mic_btn.bind("<Button-1>", self._toggle_mic)

        # ── 📸 Screenshot button ───────────────────────────────────────────────
        self.shot_btn = tk.Label(
            input_row, text=" 📸 ", bg=BG2, fg=FG_DIM,
            font=("Segoe UI", 13), cursor="hand2", padx=8, pady=6
        )
        self.shot_btn.pack(side="left", padx=(0, 6))
        self.shot_btn.bind("<Button-1>", self._on_screenshot)
        self.shot_btn.bind("<Enter>",    lambda e: self.shot_btn.config(fg=ACC2))
        self.shot_btn.bind("<Leave>",    lambda e: self.shot_btn.config(fg=FG_DIM))

        # ── SEND button ────────────────────────────────────────────────────────
        self.send_btn = tk.Label(
            input_row, text=" SEND ", bg=accent, fg="#ffffff",
            font=("Segoe UI", 9, "bold"), cursor="hand2", pady=6, padx=14
        )
        self.send_btn.pack(side="right")
        self.send_btn.bind("<Button-1>", self._on_send)
        self.send_btn.bind("<Enter>",    lambda e: self.send_btn.config(bg=ACC2))
        self.send_btn.bind("<Leave>",    lambda e: self.send_btn.config(bg=accent))

        # ── Text input (rounded feel via padded canvas frame) ─────────────────
        #   Outer frame gives the coloured "border" look
        input_border = tk.Frame(input_row, bg=BORDER, padx=1, pady=1)
        input_border.pack(side="left", fill="x", expand=True, padx=(0, 6))

        input_bg_frame = tk.Frame(input_border, bg=BG2)
        input_bg_frame.pack(fill="both", expand=True)

        self.input_var   = tk.StringVar()
        self.input_field = tk.Entry(
            input_bg_frame,
            textvariable=self.input_var,
            bg=BG2, fg=FG,
            font=("Segoe UI", 11),
            relief="flat", bd=0,
            insertbackground=accent,
        )
        self.input_field.pack(fill="x", ipady=10, padx=10)
        self.input_field.bind("<Return>",   self._on_send)
        self.input_field.bind("<FocusIn>",  lambda e: self._placeholder(False))
        self.input_field.bind("<FocusOut>", lambda e: self._placeholder(True))
        self._placeholder(True)

        # ── Chat area ─────────────────────────────────────────────────────────
        chat_frame = tk.Frame(inner, bg=bg)
        chat_frame.pack(side="top", fill="both", expand=True, pady=(6, 0))

        scrollbar = tk.Scrollbar(
            chat_frame, bg=BG3, troughcolor=bg,
            activebackground=accent, relief="flat", bd=0, width=3
        )
        scrollbar.pack(side="right", fill="y")

        self.text_area = tk.Text(
            chat_frame, bg=bg, fg=FG,
            font=("Segoe UI", 11), wrap=tk.WORD,
            relief="flat", bd=0, cursor="arrow", state="disabled",
            width=40, height=8,
            yscrollcommand=scrollbar.set,
            padx=10, pady=8,
            selectbackground="#2a2a4a",
        )
        self.text_area.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.text_area.yview)

        self.renderer = MarkdownRenderer(self.text_area, accent=accent)

        self._bind_drag(header)

    # ── Placeholder ───────────────────────────────────────────────────────────

    def _placeholder(self, show: bool) -> None:
        ph  = "Ask a follow-up…"
        cur = self.input_var.get()
        if show and (cur == "" or cur == ph):
            self.input_var.set(ph)
            self.input_field.config(fg=FG_PH)
        elif not show and cur == ph:
            self.input_var.set("")
            self.input_field.config(fg=FG)

    # ── Mic (hold-to-talk) ────────────────────────────────────────────────────

    def _toggle_mic(self, _=None) -> None:
        if not self.mic_active:
            self.mic_active = True
            self.mic_btn.config(fg=RED_C)
            if self.on_mic_start:
                threading.Thread(target=self.on_mic_start, daemon=True).start()
        else:
            self.mic_active = False
            self.mic_btn.config(fg=FG_DIM)
            if self.on_mic_stop:
                threading.Thread(target=self.on_mic_stop, daemon=True).start()

    # ── Screenshot ────────────────────────────────────────────────────────────

    def _on_screenshot(self, _=None) -> None:
        if self.on_screenshot:
            threading.Thread(target=self.on_screenshot, daemon=True).start()

    # ── Auto mode toggle (🔊) ──────────────────────────────────────────────────

    def _toggle_auto(self) -> None:
        self.auto_active = not self.auto_active
        if self.auto_active:
            self._auto_btn.config(fg=AUTO_ON)
            # Show "AUTO" badge next to title
            self._auto_badge.pack(side="left", padx=(6, 0))
        else:
            self._auto_btn.config(fg=AUTO_OFF)
            self._auto_badge.pack_forget()
        if self.on_auto_toggle:
            threading.Thread(
                target=self.on_auto_toggle, args=(self.auto_active,), daemon=True
            ).start()

    # ── Send from input box ───────────────────────────────────────────────────

    def _on_send(self, _=None) -> None:
        text = self.input_var.get().strip()
        ph   = "Ask a follow-up…"
        if not text or text == ph or self.is_thinking:
            return
        self.input_var.set("")
        self._placeholder(True)
        if self.on_send:
            threading.Thread(target=self.on_send, args=(text,), daemon=True).start()

    # ── Clear chat ────────────────────────────────────────────────────────────

    def _clear_chat(self) -> None:
        self.renderer.clear()
        if self.on_clear:
            threading.Thread(target=self.on_clear, daemon=True).start()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_user_message(self, text: str) -> None:
        if self.root:
            self.root.after(0, lambda: self.renderer.append_user(text))

    def add_ai_message(self, md: str) -> None:
        if not self.root:
            return
        def _u():
            self.renderer.hide_thinking()
            self.renderer.append_ai(md)
            self.is_thinking = False
            self.send_btn.config(bg=self._accent, text=" SEND ")
        self.root.after(0, _u)

    def add_system_audio_transcript(self, text: str) -> None:
        if self.root:
            self.root.after(0, lambda: self.renderer.append_system_audio(text))

    def set_thinking(self, state: bool) -> None:
        if not self.root:
            return
        def _u():
            self.is_thinking = state
            if state:
                self.renderer.show_thinking()
                self.send_btn.config(bg=BG3, text=" ●●● ")
            else:
                self.send_btn.config(bg=self._accent, text=" SEND ")
        self.root.after(0, _u)

    def set_mic_transcribing(self, state: bool) -> None:
        if not self.root:
            return
        def _u():
            if state:
                self.mic_btn.config(fg=AMBER)
                self.input_var.set("Transcribing…")
                self.input_field.config(fg=FG_DIM)
            else:
                self.mic_btn.config(fg=FG_DIM)
                self.input_var.set("")
                self._placeholder(True)
        self.root.after(0, _u)

    def set_input_text(self, text: str) -> None:
        if not self.root:
            return
        def _u():
            self.input_var.set(text)
            self.input_field.config(fg=FG)
            self.input_field.focus_set()
        self.root.after(0, _u)

    def clear_chat(self) -> None:
        if self.root:
            self.root.after(0, self.renderer.clear)
