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
        self.root.attributes('-alpha', 1.0)
        # Use a specific color for transparency key
        self.root.attributes('-transparentcolor', '#000001')
        self.root.configure(bg='#000001')
        self.root.withdraw()
        self.visible = False

        self.root.update()
        self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())

        self._apply_capture_exclusion()

        # ── Answer display ───────────────────────────────────────────────────
        self.answer_var = tk.StringVar(value="—")
        self.answer_label = tk.Label(
            self.root,
            textvariable=self.answer_var,
            bg='#000001', fg='#00ff88',
            font=('Segoe UI', 14, 'bold'),
            anchor='center'
        )
        self.answer_label.pack(fill='both', expand=True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # Compact geometry for just the answer
        self.root.geometry(f"80x40+{sw - 110}+{sh - 110}")

        # Drag on label
        self.answer_label.bind('<Button-1>',  self._drag_start)
        self.answer_label.bind('<B1-Motion>', self._drag_move)

    # ── Public API ────────────────────────────────────────────────────────────
    def set_thinking(self):
        if not self.root:
            return
        def _u():
            self.answer_var.set("...")
            self.answer_label.config(fg='#555577')
        self.root.after(0, _u)

    def set_answer(self, answer: str):
        if not self.root:
            return
        def _u():
            self.answer_var.set(answer)
            self.answer_label.config(fg='#00ff88')
        self.root.after(0, _u)

    def set_error(self):
        if not self.root:
            return
        def _u():
            self.answer_var.set("✕")
            self.answer_label.config(fg='#ff5555')
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
