"""
src/agents/mcq_agent.py
Screenshot → Gemini → MCQ answer on transparent overlay.
Migrated from mcq/main.py.
"""
from __future__ import annotations

import re
import threading
from typing import List

from src.agents.base_agent import BaseAgent, HotkeyDef
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot

PROMPT = (
    "Extract the correct option letter(s) (A, B, C, D, etc.) from the MCQ images. "
    "If options are not labeled, assign them letters A, B, C, D... consecutively. "
    "If multiple answers are potentially correct for one question, return them as a comma-separated list. "
    "If there are multiple distinct questions in the screenshot, separate the answers for each question with a pipe character (|). "
    "Order answers by confidence. Response must contain ONLY option characters, commas, and pipes — no words or explanations."
)


class MCQAgent(BaseAgent):

    def get_name(self) -> str:
        return "MCQ AI"

    def get_description(self) -> str:
        return "Multiple-choice questions → answer shown on a tiny transparent overlay."

    def get_default_hotkeys(self) -> List[HotkeyDef]:
        return [
            HotkeyDef("k+,", "Add MCQ screenshot"),
            HotkeyDef("k+.", "Send to Gemini → show answer"),
            HotkeyDef("k+/", "Clear queue"),
            HotkeyDef("m+n", "Toggle overlay"),
        ]

    def _register_hotkeys(self) -> None:
        hk = self._config.hotkeys
        self._hotkeys.register(hk.add_screenshot, self._add_to_queue)
        self._hotkeys.register(hk.send,           self._send_queue)
        self._hotkeys.register(hk.clear_queue,    self._clear_queue)
        self._hotkeys.register(hk.toggle_overlay, self._toggle_overlay)

    def _run(self) -> None:
        from src.ui.mcq_overlay import MCQOverlay
        self._gemini     = GeminiClient(self._config.api_key, self._config.models)
        self._overlay    = MCQOverlay()
        self._overlay.start()
        self._queue:     list = []
        self._q_lock     = threading.Lock()
        self._processing = False
        print("🎯  MCQAgent ready.", flush=True)
        print("    k+,  Add    k+.  Send    m+n  Toggle overlay", flush=True)

    def stop(self) -> None:
        if self._overlay:
            self._overlay.stop()
        super().stop()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_to_queue(self) -> None:
        img = take_screenshot()
        with self._q_lock:
            self._queue.append(img)
            n = len(self._queue)
        print(f"📸  Screenshot #{n} queued.", flush=True)
        if hasattr(self, '_overlay') and self._overlay:
            self._overlay.set_log(f"Queued {n} image(s)")

    def _send_queue(self) -> None:
        with self._q_lock:
            if not self._queue:
                print("⚠️  Queue empty.", flush=True)
                if hasattr(self, '_overlay') and self._overlay:
                    self._overlay.set_log("Queue empty")
                return
            imgs, self._queue = list(self._queue), []

        if self._processing:
            return
        self._processing = True

        def _run():
            try:
                if hasattr(self, '_overlay') and self._overlay:
                    self._overlay.set_thinking()
                answer = self._gemini.generate([PROMPT] + imgs)
                answer = self._clean_mcq(answer)
                if hasattr(self, '_overlay') and self._overlay:
                    self._overlay.set_answer(answer)
                print(f"✅  MCQ answer: {answer}", flush=True)
            except Exception as e:
                if hasattr(self, '_overlay') and self._overlay:
                    # Provide snippet of error to the UI
                    err_str = str(e)
                    short_err = err_str if len(err_str) < 30 else err_str[:27] + "..."
                    self._overlay.set_error(short_err)
                print(f"❌  {e}", flush=True)
            finally:
                self._processing = False

        threading.Thread(target=_run, daemon=True).start()

    def _clear_queue(self) -> None:
        with self._q_lock:
            n, self._queue = len(self._queue), []
        print(f"🗑️  Cleared {n}.", flush=True)
        if hasattr(self, '_overlay') and self._overlay:
            self._overlay.set_log("Queue cleared")

    def _toggle_overlay(self) -> None:
        self._overlay.toggle()

    @staticmethod
    def _clean_mcq(answer: str) -> str:
        valid = re.findall(r'[A-Ga-g,| ]', answer)
        if valid:
            return "".join(valid).upper().strip()
        m = re.search(r'[a-zA-Z]', answer)
        return m.group(0).upper() if m else "?"
