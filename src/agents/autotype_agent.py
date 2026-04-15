"""
src/agents/autotype_agent.py
Screenshot → Gemini → human-like auto-typing with pause/stop.
Migrated from AutoType.py.
"""
from __future__ import annotations

import random
import threading
import time
from typing import List

from pynput.keyboard import Controller, Key

from src.agents.base_agent import BaseAgent, HotkeyDef
from src.core.config import Config
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot
from src.utils.code_cleaner import clean_code_response

PROMPT = (
    "You are a coding assistant. The screenshots contain a coding problem or question. "
    "Analyze all provided screenshots together as one combined context. "
    "Output ONLY the raw executable code. "
    "ABSOLUTE RULES: "
    "1. Zero comments of any kind — no #, no //, no /* */, no docstrings. "
    "2. No markdown, no backticks, no code fences. "
    "3. No explanations, no preamble, no trailing text. "
    "4. Use exactly 4 spaces per indent level — no tabs. "
    "If you add anything other than raw code, you have failed the task."
)


class AutoTypeAgent(BaseAgent):

    def get_name(self) -> str:
        return "Auto-Type"

    def get_description(self) -> str:
        return "Screenshots → Gemini → types code character by character."

    def get_default_hotkeys(self) -> List[HotkeyDef]:
        return [
            HotkeyDef("k+,", "Add screenshot to queue"),
            HotkeyDef("k+.", "Send queue to Gemini → type answer"),
            HotkeyDef("k+/", "Clear screenshot queue"),
            HotkeyDef("a+s", "Pause / Resume typing"),
            HotkeyDef("k+x", "Stop typing immediately"),
        ]

    def _register_hotkeys(self) -> None:
        hk = self._config.hotkeys
        self._hotkeys.register(hk.add_screenshot, self._add_to_queue)
        self._hotkeys.register(hk.send,           self._send_queue)
        self._hotkeys.register(hk.clear_queue,    self._clear_queue)
        self._hotkeys.register(hk.pause_typing,   self._toggle_pause)
        self._hotkeys.register(hk.stop_typing,    self._stop)

    def _run(self) -> None:
        self._gemini      = GeminiClient(self._config.api_key, self._config.models)
        self._kb          = Controller()
        self._queue:      list  = []
        self._q_lock      = threading.Lock()
        self._processing  = False
        self._is_typing   = False
        self._is_paused   = False
        self._is_stopped  = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        print("⌨️  AutoTypeAgent ready.", flush=True)
        t = self._config.typing
        print(f"    k+,  Add    k+.  Send    a+s  Pause    k+x  Stop", flush=True)
        print(f"    Typing delay: {t.delay_min}–{t.delay_max}s  Startup: {t.startup_delay}s", flush=True)

    # ── Queue actions ─────────────────────────────────────────────────────────

    def _add_to_queue(self) -> None:
        img = take_screenshot()
        with self._q_lock:
            self._queue.append(img)
            n = len(self._queue)
        print(f"📸  Screenshot #{n} queued.", flush=True)

    def _send_queue(self) -> None:
        with self._q_lock:
            if not self._queue:
                print("⚠️  Queue empty.", flush=True)
                return
            imgs, self._queue = list(self._queue), []

        if self._processing:
            print("⚠️  Already processing.", flush=True)
            return
        self._processing = True

        def _run():
            try:
                answer = self._gemini.generate([PROMPT] + imgs)
                answer = clean_code_response(answer)
                print(f"{'─'*50}\n{answer}\n{'─'*50}", flush=True)
                self._deliver(answer)
            except Exception as e:
                print(f"❌  {e}", flush=True)
            finally:
                self._processing = False

        threading.Thread(target=_run, daemon=True).start()

    def _clear_queue(self) -> None:
        with self._q_lock:
            n, self._queue = len(self._queue), []
        print(f"🗑️  Cleared {n} screenshot(s).", flush=True)

    # ── Typing engine ─────────────────────────────────────────────────────────

    def _deliver(self, answer: str) -> None:
        t = self._config.typing
        print(f"⌨️  Typing in {t.startup_delay}s — click into target field!", flush=True)
        time.sleep(t.startup_delay)
        self._type_answer(answer)
        if not self._is_stopped:
            print("✅  Done typing!", flush=True)

    def _type_answer(self, answer: str) -> None:
        self._is_typing  = True
        self._is_stopped = False
        t = self._config.typing

        lines = answer.splitlines()
        for i, line in enumerate(lines):
            for char in line:
                if not self._wait_if_paused():
                    self._is_typing = False
                    return
                self._kb.type(char)
                time.sleep(random.uniform(t.delay_min, t.delay_max))

            if i < len(lines) - 1:
                if not self._wait_if_paused():
                    self._is_typing = False
                    return
                self._kb.press(Key.enter)
                self._kb.release(Key.enter)
                time.sleep(0.05)
                self._clear_auto_indent()

        self._is_typing = False

    def _wait_if_paused(self) -> bool:
        self._pause_event.wait()
        return not self._is_stopped

    def _clear_auto_indent(self) -> None:
        self._kb.press(Key.home);  self._kb.release(Key.home)
        time.sleep(0.03)
        self._kb.press(Key.shift)
        self._kb.press(Key.end);   self._kb.release(Key.end)
        self._kb.release(Key.shift)
        time.sleep(0.03)
        self._kb.press(Key.delete); self._kb.release(Key.delete)
        time.sleep(0.03)

    def _toggle_pause(self) -> None:
        if not self._is_typing:
            return
        if self._is_paused:
            self._is_paused = False
            self._pause_event.set()
            print("▶️  Typing resumed.", flush=True)
        else:
            self._is_paused = True
            self._pause_event.clear()
            print("⏸️  Typing paused.", flush=True)

    def _stop(self) -> None:
        if not self._is_typing:
            return
        self._is_stopped = True
        self._pause_event.set()
        print("⛔  Typing stopped.", flush=True)
