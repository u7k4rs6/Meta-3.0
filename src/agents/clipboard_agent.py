"""
src/agents/clipboard_agent.py
Screenshot → Gemini → Copy to clipboard.
Migrated from ClipboardCopy.py with all shared logic removed.
"""
from __future__ import annotations

import threading
from typing import List

import pyperclip

from src.agents.base_agent import BaseAgent, HotkeyDef
from src.core.config import Config
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot, image_to_bytes
from src.utils.code_cleaner import strip_code_fences

PROMPT = (
    "You are a coding assistant. The screenshots contain a coding problem or question. "
    "Analyze all the provided screenshots together as one combined context. "
    "Respond with ONLY the code solution — no explanations, no markdown fences, "
    "no comments unless absolutely essential, and no preamble. "
    "Just raw, clean, working code that can be pasted directly into an editor. "
    "If the question is not related to coding, answer it normally. "
    "Identify the language and provide the code in that language."
)


class ClipboardAgent(BaseAgent):

    def get_name(self) -> str:
        return "Clipboard Copy"

    def get_description(self) -> str:
        return "Screenshots → Gemini → copies answer to clipboard."

    def get_default_hotkeys(self) -> List[HotkeyDef]:
        return [
            HotkeyDef("k+,", "Add screenshot to queue"),
            HotkeyDef("k+.", "Send queue to Gemini → clipboard"),
            HotkeyDef("k+/", "Clear screenshot queue"),
        ]

    def _register_hotkeys(self) -> None:
        hk = self._config.hotkeys
        self._hotkeys.register(hk.add_screenshot, self._add_to_queue)
        self._hotkeys.register(hk.send,           self._send_queue)
        self._hotkeys.register(hk.clear_queue,    self._clear_queue)

    def _run(self) -> None:
        self._gemini    = GeminiClient(self._config.api_key, self._config.models)
        self._queue:    list = []
        self._q_lock    = threading.Lock()
        self._processing = False
        print("📋  ClipboardAgent ready.", flush=True)
        print(f"    k + ,  → Add screenshot   k + .  → Send   k + /  → Clear", flush=True)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_to_queue(self) -> None:
        img = take_screenshot()
        with self._q_lock:
            self._queue.append(img)
            n = len(self._queue)
        print(f"📸  Screenshot #{n} queued.", flush=True)

    def _send_queue(self) -> None:
        with self._q_lock:
            if not self._queue:
                print("⚠️  Queue is empty.", flush=True)
                return
            imgs, self._queue = list(self._queue), []

        if self._processing:
            print("⚠️  Already processing.", flush=True)
            return
        self._processing = True

        def _run():
            try:
                parts = [PROMPT] + [img for img in imgs]
                answer = self._gemini.generate(parts)
                answer = strip_code_fences(answer)
                pyperclip.copy(answer)
                print(f"✅  Copied to clipboard!\n{'─'*50}\n{answer}\n{'─'*50}", flush=True)
            except Exception as e:
                print(f"❌  {e}", flush=True)
            finally:
                self._processing = False

        threading.Thread(target=_run, daemon=True).start()

    def _clear_queue(self) -> None:
        with self._q_lock:
            n, self._queue = len(self._queue), []
        print(f"🗑️  Cleared {n} screenshot(s).", flush=True)
