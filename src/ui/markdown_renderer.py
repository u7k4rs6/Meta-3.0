"""
src/ui/markdown_renderer.py
Shared Markdown-to-Tkinter renderer.
Single implementation — no more duplication between overlay files.
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import font as tkfont


class MarkdownRenderer:
    """Renders Markdown text into a tk.Text widget with styled tags."""

    def __init__(self, text_widget: tk.Text,
                 fg: str = "#c8c8d0", bg: str = "#0e0e1a", accent: str = "#7c6af7"):
        self.widget = text_widget
        self.fg     = fg
        self.bg     = bg
        self.accent = accent
        self._define_tags()

    def _define_tags(self) -> None:
        mono = ("Cascadia Code", 10) if "Cascadia Code" in tkfont.families() else ("Consolas", 10)
        w = self.widget
        w.tag_configure("h1",          font=("Segoe UI", 17, "bold"),   foreground="#ffffff",  spacing3=5)
        w.tag_configure("h2",          font=("Segoe UI", 14, "bold"),   foreground="#e2e2e2",  spacing3=4)
        w.tag_configure("h3",          font=("Segoe UI", 12, "bold"),   foreground="#c0c0c0",  spacing3=3)
        w.tag_configure("bold",        font=("Segoe UI", 11, "bold"),   foreground="#f0f0f0")
        w.tag_configure("italic",      font=("Segoe UI", 11, "italic"), foreground="#d0d0d0")
        w.tag_configure("normal",      font=("Segoe UI", 11),           foreground=self.fg)
        w.tag_configure("inline_code", font=mono,  foreground="#7dd3a8", background="#1a1a2e")
        w.tag_configure("code_block",  font=mono,  foreground="#a8d8ea", background="#0d0d1a",
                        lmargin1=10, lmargin2=10, rmargin=10, spacing1=2, spacing3=2)
        w.tag_configure("code_lang",   font=(mono[0], 9), foreground="#44446a", background="#0d0d1a")
        w.tag_configure("bullet",      font=("Segoe UI", 11), foreground=self.accent, lmargin1=8, lmargin2=22)
        w.tag_configure("divider",     font=("Segoe UI", 3),  foreground="#22223a")
        w.tag_configure("ai_header",   font=("Segoe UI", 9, "bold"), foreground=self.accent,  spacing1=10, spacing3=4)
        w.tag_configure("user_header", font=("Segoe UI", 9, "bold"), foreground="#3a9f6e",    spacing1=10, spacing3=4)
        w.tag_configure("user_text",   font=("Segoe UI", 11),         foreground="#a0e8c0",   lmargin1=4)
        w.tag_configure("thinking",    font=("Segoe UI", 10, "italic"), foreground="#555577")
        w.tag_configure("sys_header",  font=("Segoe UI", 9, "bold"), foreground="#e0a050",    spacing1=10, spacing3=4)
        w.tag_configure("sys_text",    font=("Segoe UI", 11, "italic"), foreground="#e8c88a", lmargin1=4)

    # ── Public append methods ─────────────────────────────────────────────────

    def append_ai(self, md: str) -> None:
        self._ins("✦ AI  " + "─" * 42 + "\n", "ai_header")
        self._render_md(md)
        self._ins("\n", "normal")

    def append_user(self, text: str) -> None:
        self._ins("You  " + "─" * 43 + "\n", "user_header")
        self._ins(text + "\n", "user_text")
        self._ins("\n", "normal")

    def append_system_audio(self, text: str) -> None:
        self._ins("🔊 Interviewer  " + "─" * 35 + "\n", "sys_header")
        self._ins(text + "\n", "sys_text")
        self._ins("\n", "normal")

    def show_thinking(self) -> None:
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, "● thinking...\n", "thinking")
        self.widget.configure(state="disabled")
        self.widget.see(tk.END)

    def hide_thinking(self) -> None:
        self.widget.configure(state="normal")
        idx = self.widget.search("● thinking...", "1.0", tk.END)
        if idx:
            self.widget.delete(idx, f"{idx} lineend+1c")
        self.widget.configure(state="disabled")

    def clear(self) -> None:
        self.widget.configure(state="normal")
        self.widget.delete("1.0", tk.END)
        self.widget.configure(state="disabled")

    # ── Markdown rendering internals ──────────────────────────────────────────

    def _render_md(self, md: str) -> None:
        lines         = md.splitlines()
        i             = 0
        in_code_block = False
        code_lang     = ""
        code_buf:     list = []

        while i < len(lines):
            line = lines[i]
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_lang     = line.strip()[3:].strip()
                    code_buf      = []
                else:
                    in_code_block = False
                    if code_lang:
                        self._ins(f" {code_lang}\n", "code_lang")
                    self._ins("\n".join(code_buf) + "\n", "code_block")
                    self._ins("\n", "normal")
                    code_lang = ""
                    code_buf  = []
                i += 1
                continue
            if in_code_block:
                code_buf.append(line)
                i += 1
                continue
            if line.startswith("### "):
                self._ins(line[4:] + "\n", "h3")
            elif line.startswith("## "):
                self._ins(line[3:] + "\n", "h2")
            elif line.startswith("# "):
                self._ins(line[2:] + "\n", "h1")
            elif line.strip() in ("---", "***", "___"):
                self._ins("─" * 52 + "\n", "divider")
            elif re.match(r"^(\*|-|\+) ", line):
                self._ins("• ", "bullet")
                self._inline(line[2:])
                self._ins("\n", "normal")
            elif line.strip() == "":
                self._ins("\n", "normal")
            else:
                self._inline(line)
                self._ins("\n", "normal")
            i += 1

    def _inline(self, text: str) -> None:
        for part in re.split(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)", text):
            if part.startswith("`") and part.endswith("`") and len(part) > 2:
                self._ins(part[1:-1], "inline_code")
            elif part.startswith("**") and part.endswith("**"):
                self._ins(part[2:-2], "bold")
            elif part.startswith("*") and part.endswith("*"):
                self._ins(part[1:-1], "italic")
            else:
                self._ins(part, "normal")

    def _ins(self, text: str, tag: str) -> None:
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, text, tag)
        self.widget.configure(state="disabled")
        self.widget.see(tk.END)
