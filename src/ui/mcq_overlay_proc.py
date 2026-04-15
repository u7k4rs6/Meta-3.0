import sys
import tkinter as tk
import threading
import ctypes
import queue

WDA_EXCLUDEFROMCAPTURE = 0x00000011

class MCQOverlayProc:
    """Runs the exact legacy transparent MCQ overlay logic isolated in its own process."""
    def __init__(self):
        self.root = tk.Tk()
        self.q = queue.Queue()
        self.visible = False
        self._drag_x = 0
        self._drag_y = 0
        self._build()

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
        self.root.attributes('-transparentcolor', '#000001')
        self.root.configure(bg='#000001')
        self.root.withdraw()
        self.visible = False

        self.root.update()
        self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        self._apply_capture_exclusion()

        self.answer_var = tk.StringVar(value="—")
        self.answer_label = tk.Label(
            self.root,
            textvariable=self.answer_var,
            bg='#000001', fg='#00ff88',
            font=('Segoe UI', 16, 'bold'),
            anchor='center'
        )
        self.answer_label.pack(fill='both', expand=True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # Ensure it is visible, adjust slightly away from bottom-right corner Taskbar overlap
        self.root.geometry(f"120x60+{sw - 150}+{sh - 180}")

        self.answer_label.bind('<Button-1>',  self._drag_start)
        self.answer_label.bind('<B1-Motion>', self._drag_move)

        # Start listening to stdin queue
        self.root.after(100, self._process_queue)

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _process_queue(self):
        while not self.q.empty():
            msg = self.q.get()
            if msg == "TOGGLE":
                if self.visible:
                    self.root.withdraw()
                    self.visible = False
                else:
                    self.root.deiconify()
                    self.root.lift()
                    self.root.update()
                    self._apply_capture_exclusion()
                    self.visible = True
            elif msg == "SHOW":
                self.root.deiconify()
                self.root.lift()
                self.root.update()
                self._apply_capture_exclusion()
                self.visible = True
            elif msg == "HIDE":
                self.root.withdraw()
                self.visible = False
            elif msg.startswith("THINK:"):
                self.answer_var.set("...")
                self.answer_label.config(fg='#555577')
            elif msg.startswith("ERR:"):
                self.answer_var.set("✕")
                self.answer_label.config(fg='#ff5555')
            elif msg.startswith("ANS:"):
                ans = msg.split("ANS:", 1)[1]
                self.answer_var.set(ans)
                self.answer_label.config(fg='#00ff88')
            elif msg == "EXIT":
                self.root.destroy()
                return
        
        self.root.after(50, self._process_queue)

    def run(self):
        # Start stdin listener thread
        def listen_stdin():
            for line in sys.stdin:
                self.q.put(line.strip())
        t = threading.Thread(target=listen_stdin, daemon=True)
        t.start()

        self.root.mainloop()

if __name__ == "__main__":
    app = MCQOverlayProc()
    app.run()
