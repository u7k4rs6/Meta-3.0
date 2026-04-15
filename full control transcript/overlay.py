import tkinter as tk
from tkinter import font as tkfont
import threading
import ctypes
import re

WDA_EXCLUDEFROMCAPTURE   = 0x00000011
DWMWA_WINDOW_CORNER_PREF = 33
DWMWCP_ROUND             = 2


class MarkdownRenderer:
    def __init__(self, text_widget: tk.Text):
        self.widget = text_widget
        self._define_tags()

    def _define_tags(self):
        mono = ('Cascadia Code', 10) if 'Cascadia Code' in tkfont.families() else ('Consolas', 10)
        self.widget.tag_configure('h1',          font=('Segoe UI', 17, 'bold'), foreground='#ffffff', spacing3=5)
        self.widget.tag_configure('h2',          font=('Segoe UI', 14, 'bold'), foreground='#e2e2e2', spacing3=4)
        self.widget.tag_configure('h3',          font=('Segoe UI', 12, 'bold'), foreground='#c0c0c0', spacing3=3)
        self.widget.tag_configure('bold',        font=('Segoe UI', 11, 'bold'), foreground='#f0f0f0')
        self.widget.tag_configure('italic',      font=('Segoe UI', 11, 'italic'), foreground='#d0d0d0')
        self.widget.tag_configure('normal',      font=('Segoe UI', 11), foreground='#c8c8d0')
        self.widget.tag_configure('inline_code', font=mono, foreground='#7dd3a8', background='#1a1a2e')
        self.widget.tag_configure('code_block',  font=mono, foreground='#a8d8ea', background='#0d0d1a',
                                  lmargin1=10, lmargin2=10, rmargin=10, spacing1=2, spacing3=2)
        self.widget.tag_configure('code_lang',   font=(mono[0], 9), foreground='#44446a', background='#0d0d1a')
        self.widget.tag_configure('bullet',      font=('Segoe UI', 11), foreground='#7c6af7', lmargin1=8, lmargin2=22)
        self.widget.tag_configure('divider',     font=('Segoe UI', 3), foreground='#22223a')
        self.widget.tag_configure('ai_header',   font=('Segoe UI', 9, 'bold'), foreground='#7c6af7', spacing1=10, spacing3=4)
        self.widget.tag_configure('user_header', font=('Segoe UI', 9, 'bold'), foreground='#3a9f6e', spacing1=10, spacing3=4)
        self.widget.tag_configure('user_text',   font=('Segoe UI', 11), foreground='#a0e8c0', lmargin1=4)
        self.widget.tag_configure('thinking',    font=('Segoe UI', 10, 'italic'), foreground='#555577')
        self.widget.tag_configure('sys_header',  font=('Segoe UI', 9, 'bold'), foreground='#e0a050', spacing1=10, spacing3=4)
        self.widget.tag_configure('sys_text',    font=('Segoe UI', 11, 'italic'), foreground='#e8c88a', lmargin1=4)

    def append_ai(self, md: str):
        self._ins('✦ AI  ' + '─' * 42 + '\n', 'ai_header')
        self._render_md(md)
        self._ins('\n', 'normal')

    def append_user(self, text: str):
        self._ins('You  ' + '─' * 43 + '\n', 'user_header')
        self._ins(text + '\n', 'user_text')
        self._ins('\n', 'normal')

    def append_system_audio(self, text: str):
        """Show transcribed interviewer audio distinctly."""
        self._ins('🔊 Interviewer  ' + '─' * 35 + '\n', 'sys_header')
        self._ins(text + '\n', 'sys_text')
        self._ins('\n', 'normal')

    def show_thinking(self):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, '● thinking...\n', 'thinking')
        self.widget.configure(state='disabled')
        self.widget.see(tk.END)

    def hide_thinking(self):
        self.widget.configure(state='normal')
        idx = self.widget.search('● thinking...', '1.0', tk.END)
        if idx:
            self.widget.delete(idx, f"{idx} lineend+1c")
        self.widget.configure(state='disabled')

    def clear(self):
        self.widget.configure(state='normal')
        self.widget.delete('1.0', tk.END)
        self.widget.configure(state='disabled')

    def _render_md(self, md: str):
        lines         = md.splitlines()
        i             = 0
        in_code_block = False
        code_lang     = ''
        code_buf      = []

        while i < len(lines):
            line = lines[i]
            if line.strip().startswith('```'):
                if not in_code_block:
                    in_code_block = True
                    code_lang     = line.strip()[3:].strip()
                    code_buf      = []
                else:
                    in_code_block = False
                    if code_lang:
                        self._ins(f' {code_lang}\n', 'code_lang')
                    self._ins('\n'.join(code_buf) + '\n', 'code_block')
                    self._ins('\n', 'normal')
                    code_lang = ''
                    code_buf  = []
                i += 1
                continue
            if in_code_block:
                code_buf.append(line)
                i += 1
                continue
            if line.startswith('### '):     self._ins(line[4:] + '\n', 'h3')
            elif line.startswith('## '):    self._ins(line[3:] + '\n', 'h2')
            elif line.startswith('# '):     self._ins(line[2:] + '\n', 'h1')
            elif line.strip() in ('---', '***', '___'):
                self._ins('─' * 52 + '\n', 'divider')
            elif re.match(r'^(\*|-|\+) ', line):
                self._ins('• ', 'bullet')
                self._inline(line[2:])
                self._ins('\n', 'normal')
            elif line.strip() == '':
                self._ins('\n', 'normal')
            else:
                self._inline(line)
                self._ins('\n', 'normal')
            i += 1

    def _inline(self, text: str):
        for part in re.split(r'(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)', text):
            if part.startswith('`') and part.endswith('`') and len(part) > 2:
                self._ins(part[1:-1], 'inline_code')
            elif part.startswith('**') and part.endswith('**'):
                self._ins(part[2:-2], 'bold')
            elif part.startswith('*') and part.endswith('*'):
                self._ins(part[1:-1], 'italic')
            else:
                self._ins(part, 'normal')

    def _ins(self, text, tag):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, text, tag)
        self.widget.configure(state='disabled')
        self.widget.see(tk.END)


class OverlayWindow:
    def __init__(self):
        self.root          = None
        self.renderer      = None
        self._ready        = threading.Event()
        self._drag_x       = 0
        self._drag_y       = 0
        self.visible       = False
        self._hwnd         = None
        self.is_thinking   = False

        # Callbacks set by main.py
        self.on_send          = None   # fn(text: str)
        self.on_clear         = None   # fn()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        self._ready.wait()

    def _run(self):
        self.root = tk.Tk()
        self._build_window()
        self._ready.set()
        self.root.mainloop()

    def _apply_capture_exclusion(self):
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(self._hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception as e:
            print(f"logs: Capture exclusion error: {e}", flush=True)

    def _build_window(self):
        self.root.title("ai-overlay")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.92)
        self.root.configure(bg='#0e0e1a')
        self.root.withdraw()

        self.root.update()
        self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())

        try:
            val = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                self._hwnd, DWMWA_WINDOW_CORNER_PREF,
                ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            pass

        self._apply_capture_exclusion()

        # ── Border ──────────────────────────────────────────────────────────
        outer = tk.Frame(self.root, bg='#2a2260', padx=1, pady=1)
        outer.pack(fill='both', expand=True)

        inner = tk.Frame(outer, bg='#0e0e1a', padx=12, pady=10)
        inner.pack(fill='both', expand=True)

        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(inner, bg='#0e0e1a')
        header.pack(fill='x', pady=(0, 6))

        tk.Label(
            header, text="✦  Transcript & AI",
            bg='#0e0e1a', fg='#7c6af7',
            font=('Segoe UI', 10, 'bold')
        ).pack(side='left')

        # Close
        close_btn = tk.Label(header, text=" ✕ ", bg='#0e0e1a', fg='#333360',
                             font=('Segoe UI', 10), cursor='hand2')
        close_btn.pack(side='right')
        close_btn.bind('<Button-1>', lambda e: self.hide())
        close_btn.bind('<Enter>',    lambda e: close_btn.config(fg='#ff5555'))
        close_btn.bind('<Leave>',    lambda e: close_btn.config(fg='#333360'))

        # Clear
        clear_btn = tk.Label(header, text=" ⟳ ", bg='#0e0e1a', fg='#333360',
                             font=('Segoe UI', 10), cursor='hand2')
        clear_btn.pack(side='right')
        clear_btn.bind('<Button-1>', lambda e: self._clear_chat())
        clear_btn.bind('<Enter>',    lambda e: clear_btn.config(fg='#f0a050'))
        clear_btn.bind('<Leave>',    lambda e: clear_btn.config(fg='#333360'))

        tk.Frame(inner, bg='#1a1a30', height=1).pack(fill='x', pady=(0, 6))

        # ── Chat area ───────────────────────────────────────────────────────
        chat_frame = tk.Frame(inner, bg='#0e0e1a')
        chat_frame.pack(fill='both', expand=True)

        scrollbar = tk.Scrollbar(chat_frame, bg='#1a1a30', troughcolor='#0e0e1a',
                                 activebackground='#7c6af7', relief='flat', bd=0, width=4)
        scrollbar.pack(side='right', fill='y')

        self.text_area = tk.Text(
            chat_frame,
            bg='#0e0e1a', fg='#c8c8d0',
            font=('Segoe UI', 11),
            wrap=tk.WORD, relief='flat', bd=0,
            cursor='arrow', state='disabled',
            width=52, height=22,
            yscrollcommand=scrollbar.set,
            padx=4, pady=4,
            selectbackground='#2a2a4a',
        )
        self.text_area.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.text_area.yview)

        self.renderer = MarkdownRenderer(self.text_area)

        # ── Input area ───────────────────────────────────────────────────────
        tk.Frame(inner, bg='#1a1a30', height=1).pack(fill='x', pady=(8, 6))

        input_row = tk.Frame(inner, bg='#0e0e1a')
        input_row.pack(fill='x')

        # Text input
        input_wrap = tk.Frame(input_row, bg='#1a1a35', padx=1, pady=1)
        input_wrap.pack(side='left', fill='x', expand=True, padx=(0, 8))

        self.input_var   = tk.StringVar()
        self.input_field = tk.Entry(
            input_wrap,
            textvariable=self.input_var,
            bg='#13132a', fg='#e0e0f0',
            font=('Segoe UI', 11),
            relief='flat', bd=0,
            insertbackground='#7c6af7',
        )
        self.input_field.pack(fill='x', ipady=7, padx=6)
        self.input_field.bind('<Return>',   self._on_send)
        self.input_field.bind('<FocusIn>',  lambda e: self._placeholder(False))
        self.input_field.bind('<FocusOut>', lambda e: self._placeholder(True))
        self._placeholder(True)

        # Send button
        self.send_btn = tk.Label(input_row, text='  ↵  ', bg='#7c6af7', fg='#ffffff',
                                 font=('Segoe UI', 9, 'bold'), cursor='hand2', pady=6)
        self.send_btn.pack(side='right')
        self.send_btn.bind('<Button-1>', self._on_send)
        self.send_btn.bind('<Enter>',    lambda e: self.send_btn.config(bg='#9b8fff'))
        self.send_btn.bind('<Leave>',    lambda e: self.send_btn.config(bg='#7c6af7'))

        # Hint
        tk.Label(inner, text="m+n hide  •  k+c clear  •  k+. transcript  •  k+, +screenshot",
                 bg='#0e0e1a', fg='#1e1e40', font=('Segoe UI', 8)
                 ).pack(pady=(6, 0))

        # Position & drag
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"580x600+{sw - 610}+24")
        header.bind('<Button-1>',  self._drag_start)
        header.bind('<B1-Motion>', self._drag_move)

    # ── Placeholder ──────────────────────────────────────────────────────────
    def _placeholder(self, show: bool):
        ph = 'Ask a follow-up...'
        cur = self.input_var.get()
        if show and (cur == '' or cur == ph):
            self.input_var.set(ph)
            self.input_field.config(fg='#333360')
        elif not show and cur == ph:
            self.input_var.set('')
            self.input_field.config(fg='#e0e0f0')

    # ── Send ─────────────────────────────────────────────────────────────────
    def _on_send(self, event=None):
        text = self.input_var.get().strip()
        if not text or text == 'Ask a follow-up...' or self.is_thinking:
            return
        self.input_var.set('')
        self._placeholder(True)
        if self.on_send:
            threading.Thread(target=self.on_send, args=(text,), daemon=True).start()

    # ── Clear ────────────────────────────────────────────────────────────────
    def _clear_chat(self):
        self.renderer.clear()
        if hasattr(self, 'on_clear') and self.on_clear:
            threading.Thread(target=self.on_clear, daemon=True).start()

    # ── Public API ────────────────────────────────────────────────────────────
    def show(self, md_text: str = None):
        if not self.root:
            return
        def _update():
            if md_text is not None:
                self.renderer.append_ai(md_text)
            self.root.deiconify()
            self.root.lift()
            self.root.update()
            self._apply_capture_exclusion()
            self.visible = True
        self.root.after(0, _update)

    def add_user_message(self, text: str):
        if self.root:
            self.root.after(0, lambda: self.renderer.append_user(text))

    def add_ai_message(self, md_text: str):
        if not self.root:
            return
        def _update():
            self.renderer.hide_thinking()
            self.renderer.append_ai(md_text)
            self.is_thinking = False
            self.send_btn.config(bg='#7c6af7', text='  ↵  ')
        self.root.after(0, _update)

    def add_system_audio_transcript(self, text: str):
        if self.root:
            self.root.after(0, lambda: self.renderer.append_system_audio(text))

    def set_thinking(self, state: bool):
        if not self.root:
            return
        def _update():
            self.is_thinking = state
            if state:
                self.renderer.show_thinking()
                self.send_btn.config(bg='#333360', text='  ●  ')
            else:
                self.send_btn.config(bg='#7c6af7', text='  ↵  ')
        self.root.after(0, _update)

    def clear_chat(self):
        if self.root:
            self.root.after(0, self.renderer.clear)

    def hide(self):
        if not self.root:
            return
        def _hide():
            self.root.withdraw()
            self.visible = False
        self.root.after(0, _hide)

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")
