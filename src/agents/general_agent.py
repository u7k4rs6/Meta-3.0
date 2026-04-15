"""
src/agents/general_agent.py
General-purpose screenshot → Gemini → auto-type.
Handles coding, MCQ, theory, math, anything.
Migrated from general.py.
"""
from __future__ import annotations

import random
import threading
import time
from typing import List

from pynput.keyboard import Controller, Key

from src.agents.base_agent import BaseAgent, HotkeyDef
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot

PROMPT = (
    "Analyze this screenshot carefully and respond with the most useful answer possible. "
    "- Coding problem → working code solution, no explanations. "
    "- Theory / concept → clear, concise answer. "
    "- MCQ → correct option and one-line reason. "
    "- Math → solution with steps. "
    "- Anything else → most helpful, concise answer. "
    "No markdown formatting, no backticks, no unnecessary padding."
)


class GeneralAgent(BaseAgent):

    def get_name(self) -> str:
        return "General AI"

    def get_description(self) -> str:
        return "Adaptive Q&A — handles coding, MCQ, theory, math and more."

    def get_default_hotkeys(self) -> List[HotkeyDef]:
        return [
            HotkeyDef("k+,", "Add screenshot"),
            HotkeyDef("k+.", "Send to Gemini → type answer"),
            HotkeyDef("k+/", "Clear queue"),
            HotkeyDef("a+s", "Pause / Resume typing"),
            HotkeyDef("k+x", "Stop typing"),
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
        print("🧠  GeneralAgent ready.", flush=True)

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
            return
        self._processing = True

        def _run():
            try:
                answer = self._gemini.generate([PROMPT] + imgs)
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
        print(f"🗑️  Cleared {n}.", flush=True)

    def _deliver(self, answer: str) -> None:
        t = self._config.typing
        print(f"⌨️  Typing in {t.startup_delay}s...", flush=True)
        time.sleep(t.startup_delay)
        self._is_typing = True
        self._is_stopped = False
        for char in answer:
            if not self._pause_event.wait() or self._is_stopped:
                break
            self._kb.type(char)
            time.sleep(random.uniform(t.delay_min, t.delay_max))
        self._is_typing = False
        if not self._is_stopped:
            print("✅  Done!", flush=True)

    def _toggle_pause(self) -> None:
        if not self._is_typing:
            return
        if self._is_paused:
            self._is_paused = False
            self._pause_event.set()
            print("▶️  Resumed.", flush=True)
        else:
            self._is_paused = True
            self._pause_event.clear()
            print("⏸️  Paused.", flush=True)

    def _stop(self) -> None:
        if self._is_typing:
            self._is_stopped = True
            self._pause_event.set()
            print("⛔  Stopped.", flush=True)
