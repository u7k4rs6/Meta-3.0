import tkinter as tk
import threading
import ctypes

WDA_EXCLUDEFROMCAPTURE   = 0x00000011
DWMWA_WINDOW_CORNER_PREF = 33
DWMWCP_ROUND             = 2


class MCQOverlay:
    def __init__(self):
        self.root    = None
        self._ready  = threading.Event()
        self._hwnd   = None
        self.visible = False
        self._drag_x = 0
        self._drag_y = 0

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        self._ready.wait()

    def _run(self):
        self.root = tk.Tk()
        self._build()
        self._ready.set()
        self.root.mainloop()

    def _apply_capture_exclusion(self):
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(self._hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass

    def _build(self):
        self.root.title("mcq")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.25)
        self.root.configure(bg='#0a0a14')
        self.root.withdraw()
        self.visible = False

        self.root.update()
        self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())

        # Rounded corners (Windows 11)
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

        inner = tk.Frame(outer, bg='#0a0a14', padx=6, pady=4)
        inner.pack(fill='both', expand=True)

        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(inner, bg='#0a0a14')
        header.pack(fill='x', pady=(0, 2))

        tk.Label(
            header, text="◈ MCQ",
            bg='#0a0a14', fg='#7c6af7',
            font=('Segoe UI', 7, 'bold')
        ).pack(side='left')

        self.status_label = tk.Label(
            header, text="",
            bg='#0a0a14', fg='#333355',
            font=('Segoe UI', 6)
        )
        self.status_label.pack(side='right')

        tk.Frame(inner, bg='#1a1a30', height=1).pack(fill='x', pady=(0, 4))

        # ── Answer display ───────────────────────────────────────────────────
        self.answer_var = tk.StringVar(value="—")
        self.answer_label = tk.Label(
            inner,
            textvariable=self.answer_var,
            bg='#0a0a14', fg='#00ff88',
            font=('Segoe UI', 14, 'bold'),
            anchor='center'
        )
        self.answer_label.pack(fill='x', pady=(0, 0))

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # Position in bottom-right corner, 100x64 size
        self.root.geometry(f"100x64+{sw - 110}+{sh - 110}")

        # Drag on header
        header.bind('<Button-1>',  self._drag_start)
        header.bind('<B1-Motion>', self._drag_move)

    # ── Public API ────────────────────────────────────────────────────────────
    def set_thinking(self):
        if not self.root:
            return
        def _u():
            self.answer_var.set("...")
            self.answer_label.config(fg='#555577')
            self.status_label.config(text="thinking")
        self.root.after(0, _u)

    def set_answer(self, answer: str):
        if not self.root:
            return
        def _u():
            self.answer_var.set(answer)
            self.answer_label.config(fg='#00ff88')
            self.status_label.config(text="")
        self.root.after(0, _u)

    def set_error(self):
        if not self.root:
            return
        def _u():
            self.answer_var.set("✕")
            self.answer_label.config(fg='#ff5555')
            self.status_label.config(text="error")
        self.root.after(0, _u)

    def show(self):
        if not self.root:
            return
        def _u():
            self.root.deiconify()
            self.root.lift()
            self.root.update()
            self._apply_capture_exclusion()
            self.visible = True
        self.root.after(0, _u)

    def hide(self):
        if not self.root:
            return
        def _u():
            self.root.withdraw()
            self.visible = False
        self.root.after(0, _u)

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
