"""
src/ui/settings_panel.py
Tabbed settings panel embedded inside the Launcher window.
Reads from and writes to the Config object, then saves to settings.json.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from src.core.config import Config, save_config

BG    = "#0a0a14"
BG2   = "#12121e"
FG    = "#c8c8d0"
ACC   = "#7c6af7"
ENTRY_BG = "#1a1a2e"
ENTRY_FG = "#e0e0f0"


def _label(parent, text, **kw):
    kw.setdefault("bg", BG2)
    kw.setdefault("fg", FG)
    kw.setdefault("font", ("Segoe UI", 10))
    return tk.Label(parent, text=text, **kw)


def _entry(parent, var, width=28):
    e = tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=ENTRY_FG,
                 font=("Segoe UI", 10), relief="flat", bd=0,
                 insertbackground=ACC, width=width)
    e.pack(pady=2, ipady=5, padx=6, fill="x")
    return e


def _section(parent, title):
    tk.Label(parent, text=title, bg=BG2, fg=ACC,
             font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 2))
    tk.Frame(parent, bg=ACC, height=1).pack(fill="x", pady=(0, 6))


class SettingsPanel:
    """
    Adds a 'Settings' frame inside `parent_frame`.
    Provides tabs: Hotkeys | Overlay | Typing | Audio | Models.
    """

    def __init__(self, parent_frame: tk.Frame, cfg: Config,
                 on_save: Callable[[Config], None]):
        self._cfg     = cfg
        self._on_save = on_save
        self._vars:   dict = {}
        self._build(parent_frame)

    def _build(self, parent: tk.Frame) -> None:
        # Main container
        self.container = tk.Frame(parent, bg=BG2)
        self.container.pack(fill="both", expand=True, padx=16, pady=12)

        # Title
        tk.Label(self.container, text="⚙  Settings", bg=BG2, fg=ACC,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 8))

        # Footer for Save Button - Packed first at bottom to ensure visibility
        footer = tk.Frame(self.container, bg=BG2)
        footer.pack(side="bottom", fill="x", pady=(12, 0))

        save_btn = tk.Label(footer, text="  💾  Save Settings  ", bg=ACC, fg="#fff",
                            font=("Segoe UI", 10, "bold"), cursor="hand2", pady=8, padx=20)
        save_btn.pack(pady=5)
        save_btn.bind("<Button-1>", lambda e: self._save())
        save_btn.bind("<Enter>",    lambda e: save_btn.config(bg="#9b8fff"))
        save_btn.bind("<Leave>",    lambda e: save_btn.config(bg=ACC))

        # Horizontal line above footer
        tk.Frame(footer, bg="#1a1a30", height=1).pack(side="top", fill="x", pady=(0, 10))

        # Tabs
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",        background=BG2, borderwidth=0)
        style.configure("TNotebook.Tab",    background=BG, foreground=FG,
                        padding=[10, 4], font=("Segoe UI", 9))
        style.map("TNotebook.Tab",          background=[("selected", ACC)],
                  foreground=[("selected", "#ffffff")])

        self._nb = ttk.Notebook(self.container)
        self._nb.pack(fill="both", expand=True)

        self._tab_hotkeys(self._nb)
        self._tab_overlay(self._nb)
        self._tab_typing(self._nb)
        self._tab_audio(self._nb)
        self._tab_models(self._nb)

    def _make_scrollable_frame(self, parent: tk.Frame) -> tk.Frame:
        """Helper to create a scrollable frame within a tab."""
        canvas = tk.Canvas(parent, bg=BG2, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG2)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Bind mousewheel to canvas and its children
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Create window with a width that fits the detail panel
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=540)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return scrollable_frame

    def _make_tab(self, nb: ttk.Notebook, title: str) -> tk.Frame:
        frame = tk.Frame(nb, bg=BG2)
        nb.add(frame, text=title)
        
        # Add scrollable inner frame
        inner = self._make_scrollable_frame(frame)
        
        # Add some padding inside the scrollable frame
        container_inner = tk.Frame(inner, bg=BG2, padx=10, pady=8)
        container_inner.pack(fill="both", expand=True)
        return container_inner

    def _row(self, parent, label, var_key, default):
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill="x", pady=2)
        _label(row, label + ":").pack(side="left", padx=(0, 8))
        var = tk.StringVar(value=str(default))
        self._vars[var_key] = var
        tk.Entry(row, textvariable=var, bg=ENTRY_BG, fg=ENTRY_FG,
                 font=("Segoe UI", 10), relief="flat", bd=0,
                 insertbackground=ACC, width=24).pack(side="left")

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _tab_hotkeys(self, nb) -> None:
        t = self._make_tab(nb, "⌨  Hotkeys")
        hk = self._cfg.hotkeys
        fields = [
            ("Add Screenshot",    "add_screenshot",  hk.add_screenshot),
            ("Send / Analyze",    "send",            hk.send),
            ("Clear Queue",       "clear_queue",     hk.clear_queue),
            ("Toggle Overlay",    "toggle_overlay",  hk.toggle_overlay),
            ("Clear Memory",      "clear_memory",    hk.clear_memory),
            ("Pause Typing",      "pause_typing",    hk.pause_typing),
            ("Stop Typing",       "stop_typing",     hk.stop_typing),
            ("Next File",         "next_file",       hk.next_file),
            ("Re-type",           "retype",          hk.retype),
            ("Send Transcript",   "send_transcript", hk.send_transcript),
            ("Send +Screenshot",  "send_with_shot",  hk.send_with_shot),
        ]
        for label, key, val in fields:
            self._row(t, label, f"hk_{key}", val)

        _section(t, "Mode Switching")
        switch_fields = [
            ("To Clipboard",     "switch_clipboard",    hk.switch_clipboard),
            ("To Auto-Type",     "switch_autotype",     hk.switch_autotype),
            ("To General AI",    "switch_general",      hk.switch_general),
            ("To MCQ AI",        "switch_mcq",          hk.switch_mcq),
            ("To Full Control",  "switch_full_control", hk.switch_full_control),
        ]
        for label, key, val in switch_fields:
            self._row(t, label, f"hk_{key}", val)

        _label(t, "Format: key+key  e.g. k+,  or  m+n", fg="#555577").pack(pady=(8, 0))

    def _tab_overlay(self, nb) -> None:
        t = self._make_tab(nb, "🎨  Overlay")
        o = self._cfg.overlay
        fields = [
            ("Alpha (0–1)",       "ov_alpha",       o.alpha),
            ("Background Color",  "ov_bg",          o.bg_color),
            ("Foreground Color",  "ov_fg",          o.fg_color),
            ("Accent Color",      "ov_accent",      o.accent_color),
            ("Width (px)",        "ov_width",       o.width),
            ("Height (px)",       "ov_height",      o.height),
        ]
        for label, key, val in fields:
            self._row(t, label, key, val)

    def _tab_typing(self, nb) -> None:
        t = self._make_tab(nb, "⌚  Typing")
        ty = self._cfg.typing
        self._row(t, "Min Delay (s)",    "ty_min",   ty.delay_min)
        self._row(t, "Max Delay (s)",    "ty_max",   ty.delay_max)
        self._row(t, "Startup Delay (s)","ty_start", ty.startup_delay)

    def _tab_audio(self, nb) -> None:
        t = self._make_tab(nb, "🎤  Audio")
        a = self._cfg.audio
        self._row(t, "Flush Interval (s)", "au_interval",  a.interval)
        self._row(t, "Volume Threshold",   "au_threshold", a.threshold)
        _label(t, "Higher threshold = less hallucination", fg="#555577").pack(pady=(8, 0))

    def _tab_models(self, nb) -> None:
        t = self._make_tab(nb, "🤖  Models")
        
        # API Key Section
        _label(t, "Gemini API Key:", fg=ACC, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        var = tk.StringVar(value=self._cfg.api_key)
        self._vars["api_key"] = var
        tk.Entry(t, textvariable=var, bg=ENTRY_BG, fg=ENTRY_FG,
                 font=("Segoe UI", 10), relief="flat", bd=0,
                 insertbackground=ACC, width=40, show="*").pack(anchor="w", pady=(2, 12), fill="x")

        _label(t, "Model Priority (Models are tried in order):", fg=FG).pack(anchor="w", pady=(8, 2))
        for i, m in enumerate(self._cfg.models):
            self._row(t, f"Model {i+1}", f"model_{i}", m)
        _label(t, "Get a free key at aistudio.google.com/app/apikey", fg="#555577").pack(pady=(8, 0))

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        v = self._vars
        def g(key, typ=str):
            try:
                return typ(v[key].get())
            except Exception:
                return typ()

        self._cfg.api_key = g("api_key")
        hk = self._cfg.hotkeys
        hk.add_screenshot  = g("hk_add_screenshot")
        hk.send            = g("hk_send")
        hk.clear_queue     = g("hk_clear_queue")
        hk.toggle_overlay  = g("hk_toggle_overlay")
        hk.clear_memory    = g("hk_clear_memory")
        hk.pause_typing    = g("hk_pause_typing")
        hk.stop_typing     = g("hk_stop_typing")
        hk.next_file       = g("hk_next_file")
        hk.retype          = g("hk_retype")
        hk.send_transcript   = g("hk_send_transcript")
        hk.send_with_shot    = g("hk_send_with_shot")
        hk.switch_clipboard   = g("hk_switch_clipboard")
        hk.switch_autotype    = g("hk_switch_autotype")
        hk.switch_general     = g("hk_switch_general")
        hk.switch_mcq         = g("hk_switch_mcq")
        hk.switch_full_control = g("hk_switch_full_control")

        o = self._cfg.overlay
        o.alpha       = g("ov_alpha",  float)
        o.bg_color    = g("ov_bg")
        o.fg_color    = g("ov_fg")
        o.accent_color= g("ov_accent")
        o.width       = g("ov_width",  int)
        o.height      = g("ov_height", int)

        ty = self._cfg.typing
        ty.delay_min     = g("ty_min",   float)
        ty.delay_max     = g("ty_max",   float)
        ty.startup_delay = g("ty_start", float)

        a = self._cfg.audio
        a.interval  = g("au_interval",  float)
        a.threshold = g("au_threshold", float)

        models = []
        for i in range(3):
            m = g(f"model_{i}")
            if m:
                models.append(m)
        if models:
            self._cfg.models = models

        save_config(self._cfg)
        self._on_save(self._cfg)
        print("✅  Settings saved.", flush=True)
