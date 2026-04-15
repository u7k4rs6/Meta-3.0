"""
src/ui/launcher.py
Main launcher window — dark sidebar layout.
Left panel: agent cards. Right panel: description + hotkeys + settings toggle.
"""
from __future__ import annotations

import sys
import threading
import tkinter as tk
from typing import Optional

from src.core.config import Config, save_config
from src.core.hotkey_manager import HotkeyManager

BG      = "#07070f"
SIDEBAR = "#0e0e1a"
CARD_BG = "#12121e"
CARD_SEL= "#1e1a40"
FG      = "#c8c8d0"
FG2     = "#666688"
ACC     = "#7c6af7"
ACC2    = "#9b8fff"
GREEN   = "#3a9f6e"
RED     = "#ff5566"


class AgentCard:
    """Represents one clickable agent card in the sidebar."""

    def __init__(self, parent, name: str, emoji: str, description: str, on_click):
        self.frame = tk.Frame(parent, bg=CARD_BG, cursor="hand2", padx=12, pady=10)
        self.frame.pack(fill="x", padx=8, pady=4)

        self.name_lbl = tk.Label(self.frame, text=f"{emoji}  {name}", bg=CARD_BG,
                                 fg=FG, font=("Segoe UI", 11, "bold"), anchor="w")
        self.name_lbl.pack(fill="x")

        self.desc_lbl = tk.Label(self.frame, text=description, bg=CARD_BG,
                                 fg=FG2, font=("Segoe UI", 9), wraplength=200, anchor="w")
        self.desc_lbl.pack(fill="x")

        for w in (self.frame, self.name_lbl, self.desc_lbl):
            w.bind("<Button-1>", lambda e: on_click())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))

    def select(self, selected: bool) -> None:
        c = CARD_SEL if selected else CARD_BG
        for w in (self.frame, self.name_lbl, self.desc_lbl):
            w.config(bg=c)
        self.name_lbl.config(fg=ACC if selected else FG)

    def _hover(self, on: bool) -> None:
        c = CARD_SEL if on else CARD_BG
        for w in (self.frame, self.name_lbl, self.desc_lbl):
            w.config(bg=c)


class LauncherWindow:
    """
    Main application window.
    Sidebar (left) lists all agents.
    Detail panel (right) shows hotkeys, launch/stop, and settings.
    """

    AGENTS = [
        ("clipboard",   "📋", "Clipboard Copy"),
        ("autotype",    "⌨️",  "Auto-Type"),
        ("general",     "🧠", "General AI"),
        ("mcq",         "🎯", "MCQ AI"),
        # Full Control now includes real-time transcript + auto-mode
        ("full_control","👑", "Full Control"),
    ]

    def __init__(self, cfg: Config):
        self._cfg             = cfg
        self._hotkeys         = HotkeyManager()
        self._active_agent    = None
        self._selected_key    = None
        self._cards:  dict    = {}
        self._show_settings   = False
        self._status_var      = None
        self._detail_frame    = None
        self._settings_frame  = None

        self._root = tk.Tk()
        self._build()

    def run(self) -> None:
        self._hotkeys.start()
        self._root.mainloop()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        r = self._root
        r.title("Don't Cheat — AI Toolkit")
        r.configure(bg=BG)
        r.geometry("820x580")
        r.resizable(False, False)
        r.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            r.iconbitmap(default="")
        except Exception:
            pass

        # ── Main layout: sidebar + detail ─────────────────────────────────────
        sidebar_outer = tk.Frame(r, bg=SIDEBAR, width=240)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        self._detail_frame = tk.Frame(r, bg=BG)
        self._detail_frame.pack(side="right", fill="both", expand=True)

        # Sidebar header (Fixed at top)
        tk.Label(sidebar_outer, text="✦ Don't Cheat", bg=SIDEBAR, fg=ACC,
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 4), padx=12, anchor="w")
        tk.Label(sidebar_outer, text="AI Toolkit v2.0", bg=SIDEBAR, fg=FG2,
                 font=("Segoe UI", 9)).pack(padx=12, anchor="w")
        tk.Frame(sidebar_outer, bg="#1a1a30", height=1).pack(fill="x", pady=12, padx=8)

        # Settings toggle (Fixed at bottom)
        settings_frame = tk.Frame(sidebar_outer, bg=SIDEBAR)
        settings_frame.pack(side="bottom", fill="x", pady=(0, 12))
        tk.Frame(settings_frame, bg="#1a1a30", height=1).pack(fill="x", pady=(0, 12), padx=8)
        settings_lbl = tk.Label(settings_frame, text="⚙  Settings", bg=SIDEBAR, fg=FG2,
                                font=("Segoe UI", 10), cursor="hand2")
        settings_lbl.pack(anchor="w", padx=16)
        settings_lbl.bind("<Button-1>", lambda e: self._toggle_settings())
        settings_lbl.bind("<Enter>", lambda e: settings_lbl.config(fg=ACC))
        settings_lbl.bind("<Leave>", lambda e: settings_lbl.config(fg=FG2))

        # Scrollable middle section for Agent Cards
        canvas = tk.Canvas(sidebar_outer, bg=SIDEBAR, highlightthickness=0)
        scrollbar = tk.Scrollbar(sidebar_outer, orient="vertical", command=canvas.yview, width=8)
        
        sidebar_cards = tk.Frame(canvas, bg=SIDEBAR)
        
        sidebar_cards.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.create_window((0, 0), window=sidebar_cards, anchor="nw", width=230)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        # We only pack scrollbar if the list is getting too long to look clean, 
        # but leaving it packed on the right works.
        # scrollbar.pack(side="right", fill="y")

        # Agent cards (inside scrollable frame)
        for key, emoji, name in self.AGENTS:
            agent = self._get_agent(key)
            desc  = agent.get_description() if agent else ""
            card  = AgentCard(sidebar_cards, name, emoji, desc,
                              on_click=lambda k=key: self._select(k))
            self._cards[key] = card

        # Initial view
        if not self._cfg.api_key:
            self._toggle_settings()
        else:
            self._show_welcome()

    def _show_welcome(self) -> None:
        self._clear_detail()
        f = self._detail_frame
        tk.Label(f, text="✦", bg=BG, fg=ACC, font=("Segoe UI", 40)).pack(pady=(80, 4))
        tk.Label(f, text="Don't Cheat AI Toolkit", bg=BG, fg=FG,
                 font=("Segoe UI", 18, "bold")).pack()
        tk.Label(f, text="Select a feature from the sidebar to get started.",
                 bg=BG, fg=FG2, font=("Segoe UI", 11)).pack(pady=(8, 0))

    def _select(self, key: str) -> None:
        if self._selected_key == key:
            return
        if self._selected_key:
            self._cards[self._selected_key].select(False)
        self._selected_key = key
        self._cards[key].select(True)
        self._show_settings = False
        self._show_agent_detail(key)

    def _show_agent_detail(self, key: str) -> None:
        self._clear_detail()
        agent = self._get_agent(key)
        if not agent:
            return
        f = self._detail_frame

        # Title row
        title_row = tk.Frame(f, bg=BG)
        title_row.pack(fill="x", padx=24, pady=(24, 4))

        _, emoji, name = next(x for x in self.AGENTS if x[0] == key)
        tk.Label(title_row, text=f"{emoji}  {name}", bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(side="left")

        # Status
        self._status_var = tk.StringVar(value="● Stopped")
        self._status_lbl = tk.Label(title_row, textvariable=self._status_var,
                                    bg=BG, fg=RED, font=("Segoe UI", 10, "bold"))
        self._status_lbl.pack(side="right")

        # Description
        tk.Label(f, text=agent.get_description(), bg=BG, fg=FG2,
                 font=("Segoe UI", 10), wraplength=520, anchor="w").pack(
            fill="x", padx=24, pady=(0, 12))

        tk.Frame(f, bg="#1a1a30", height=1).pack(fill="x", padx=24, pady=(0, 16))

        # Hotkey table
        hk_frame = tk.Frame(f, bg=BG)
        hk_frame.pack(fill="x", padx=24)
        tk.Label(hk_frame, text="Hotkeys", bg=BG, fg=ACC,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        for hk in agent.get_default_hotkeys():
            row = tk.Frame(hk_frame, bg=CARD_BG, padx=10, pady=6)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=hk.combo, bg=CARD_BG, fg=ACC,
                     font=("Cascadia Code", 10) if True else ("Consolas", 10),
                     width=12, anchor="w").pack(side="left")
            tk.Label(row, text=hk.description, bg=CARD_BG, fg=FG,
                     font=("Segoe UI", 10), anchor="w").pack(side="left")

        # Optional Toggle for Multi-File (Auto-Type only)
        if key == "autotype":
            toggle_row = tk.Frame(f, bg=BG)
            toggle_row.pack(fill="x", padx=24, pady=(16, 0))
            
            self._mf_var = tk.BooleanVar(value=self._cfg.typing.multifile_mode)
            def _on_mf_toggle():
                self._cfg.typing.multifile_mode = self._mf_var.get()
                save_config(self._cfg)
                # Refresh hotkeys if needed, or just update UI labels?
                # For now just refreshing description/hotkeys in place is complex, 
                # but we'll reload the detail view to show new hotkeys if they differ.
                self._show_agent_detail("autotype")

            mf_cb = tk.Checkbutton(
                toggle_row, text="Multi-File Mode (LLD)", variable=self._mf_var,
                command=_on_mf_toggle, bg=BG, fg=ACC, activebackground=BG,
                activeforeground=ACC2, selectcolor=CARD_BG,
                font=("Segoe UI", 10, "bold"), bd=0, highlightthickness=0
            )
            mf_cb.pack(side="left")
            
            tk.Label(toggle_row, text="(Enables k+n for next file)", bg=BG, fg=FG2,
                     font=("Segoe UI", 9)).pack(side="left", padx=8)

        # Launch / Stop buttons
        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(pady=24)

        self._launch_btn = tk.Label(btn_row, text="  ▶  Launch  ", bg=GREEN, fg="#fff",
                                    font=("Segoe UI", 11, "bold"), cursor="hand2", pady=8, padx=16)
        self._launch_btn.pack(side="left", padx=8)
        self._launch_btn.bind("<Button-1>", lambda e: self._launch(key))
        self._launch_btn.bind("<Enter>", lambda e: self._launch_btn.config(bg="#48c88a"))
        self._launch_btn.bind("<Leave>", lambda e: self._launch_btn.config(bg=GREEN))

        # API Key Warning
        if not self._cfg.api_key:
            tk.Label(f, text="⚠️ API Key Missing! Go to Settings to setup.", bg=BG, fg=RED,
                     font=("Segoe UI", 9, "bold")).pack(pady=(0, 10))

        stop_btn = tk.Label(btn_row, text="  ■  Stop  ", bg=RED, fg="#fff",
                            font=("Segoe UI", 11, "bold"), cursor="hand2", pady=8, padx=16)
        stop_btn.pack(side="left", padx=8)
        stop_btn.bind("<Button-1>", lambda e: self._stop_agent())
        stop_btn.bind("<Enter>", lambda e: stop_btn.config(bg="#ff7788"))
        stop_btn.bind("<Leave>", lambda e: stop_btn.config(bg=RED))

    def _toggle_settings(self) -> None:
        self._show_settings = not self._show_settings
        if self._show_settings:
            self._show_settings_panel()
        elif self._selected_key:
            self._show_agent_detail(self._selected_key)
        else:
            self._show_welcome()

    def _show_settings_panel(self) -> None:
        from src.ui.settings_panel import SettingsPanel
        self._clear_detail()
        SettingsPanel(self._detail_frame, self._cfg, on_save=self._on_settings_saved)

    def _on_settings_saved(self, cfg: Config) -> None:
        self._cfg = cfg
        # Re-wire hotkeys if an agent is active
        if self._active_agent:
            self._hotkeys.clear()
            self._active_agent._register_hotkeys()

    # ── Agent lifecycle ───────────────────────────────────────────────────────

    def _launch(self, key: str) -> None:
        if not self._cfg.api_key:
            from tkinter import messagebox
            messagebox.showwarning("API Key Required", "Please enter your Gemini API Key in the Settings panel before launching an agent.")
            self._toggle_settings()
            return

        if self._active_agent:
            self._stop_agent()

        agent = self._get_agent(key)
        if not agent:
            return

        self._hotkeys.clear()
        self._active_agent = agent

        def _run():
            try:
                agent.start(self._cfg, self._hotkeys)
                self._set_status("● Running", GREEN)
            except Exception as e:
                print(f"❌  Agent error: {e}", flush=True)
                self._set_status("● Error", RED)
                self._active_agent = None

        threading.Thread(target=_run, daemon=True).start()

    def _stop_agent(self) -> None:
        if self._active_agent:
            self._active_agent.stop()
            self._active_agent = None
            self._hotkeys.clear()
            self._set_status("● Stopped", RED)

    def _set_status(self, text: str, color: str) -> None:
        if self._status_var and self._root:
            self._root.after(0, lambda: (
                self._status_var.set(text),
                self._status_lbl.config(fg=color)
            ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear_detail(self) -> None:
        for w in self._detail_frame.winfo_children():
            w.destroy()

    def _get_agent(self, key: str):
        from src.agents.clipboard_agent    import ClipboardAgent
        from src.agents.autotype_agent     import AutoTypeAgent
        from src.agents.general_agent      import GeneralAgent
        from src.agents.mcq_agent          import MCQAgent
        from src.agents.full_control_agent import FullControlAgent
        from src.agents.multifile_agent    import MultiFileAgent

        agents_map = {
            "clipboard":    ClipboardAgent,
            "autotype":     AutoTypeAgent,
            "general":      GeneralAgent,
            "mcq":          MCQAgent,
            "full_control": FullControlAgent,
        }

        agent_class = agents_map.get(key)
        if key == "autotype" and self._cfg.typing.multifile_mode:
            agent_class = MultiFileAgent

        return agent_class() if agent_class else None

    def _on_close(self) -> None:
        # Hide the window to system tray
        self._root.withdraw()
        threading.Thread(target=self._create_tray_icon, daemon=True).start()

    def _create_tray_icon(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw

            # Create a simple generic icon for the tray
            image = Image.new('RGB', (64, 64), color=(124, 106, 247))
            d = ImageDraw.Draw(image)
            d.text((16, 24), "DC", fill=(255, 255, 255))

            def on_show(icon, item):
                icon.stop()
                self._root.after(0, self._root.deiconify)

            def on_exit(icon, item):
                icon.stop()
                self._root.after(0, self._quit_app)

            menu = pystray.Menu(
                pystray.MenuItem("Show Don't Cheat", on_show, default=True),
                pystray.MenuItem('Exit completely', on_exit)
            )

            icon = pystray.Icon("DontCheat", image, "Don't Cheat AI Toolkit", menu)
            # This blocks the thread, which is fine since we are in a daemon thread.
            icon.run()
        except ImportError:
            # Fallback if pystray not installed for some reason
            self._quit_app()

    def _quit_app(self) -> None:
        self._stop_agent()
        self._hotkeys.stop()
        self._root.destroy()
        sys.exit(0)
