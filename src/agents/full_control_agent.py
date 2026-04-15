"""
src/agents/full_control_agent.py
Unified Full Control agent — merges "Full Control" + "Real-Time Transcript".

Two modes:
  Manual  — Screenshot queue (k+, / k+.) + typed follow-ups + hold-mic.
  Auto    — Debounce VAD listener: speech pause → transcribe → Gemini auto-reply.
            Toggle with the 🔊 button in the overlay.

Memory layer persists across both modes (same conversation history).
Responses in Auto mode are kept concise (interviewer-style).
"""
from __future__ import annotations

import threading
from typing import List

from google.genai import types

from src.agents.base_agent import BaseAgent, HotkeyDef
from src.audio.mic_recorder import MicRecorder
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot, image_to_bytes

# ── Prompts ───────────────────────────────────────────────────────────────────

MANUAL_SYSTEM_PROMPT = (
    "You are a helpful AI assistant embedded in a floating overlay. "
    "The user sends you screenshots of problems they are looking at, "
    "or asks follow-up questions in text. "
    "Analyze and respond with the most useful answer. "
    "- Coding problem → working solution with brief explanation. "
    "- Theory / concept → clear structured answer. "
    "- MCQ → correct option and why. "
    "- Math → solution with steps. "
    "- Anything else → most helpful concise answer. "
    "Format in clean Markdown. Use ## headings, **bold**, and ```language code blocks. "
    "For follow-up questions, use the full conversation context."
)

AUTO_SYSTEM_PROMPT = (
    "You are a real-time interview assistant embedded in a floating overlay. "
    "You are given transcribed speech from an interviewer or the user. "
    "Identify the most recent question or problem and provide a CONCISE, helpful answer. "
    "Keep responses SHORT (2-4 sentences or a small code snippet). "
    "If the transcript is small talk or unclear, reply with a very brief acknowledgement. "
    "Use minimal Markdown — only inline code and **bold** where needed."
)

MAX_TURNS = 12


class FullControlAgent(BaseAgent):

    def get_name(self) -> str:
        return "Full Control"

    def get_description(self) -> str:
        return (
            "Unified overlay: Screenshot + Mic + auto real-time audio detection. "
            "Manual = screenshot/chat. Auto = live transcript → auto Gemini reply."
        )

    def get_default_hotkeys(self) -> List[HotkeyDef]:
        return [
            HotkeyDef("k+,", "Add screenshot to queue"),
            HotkeyDef("k+.", "Send screenshots to Gemini"),
            HotkeyDef("k+/", "Clear screenshot queue"),
            HotkeyDef("k+c", "Clear memory & chat"),
            HotkeyDef("m+n", "Toggle overlay"),
        ]

    def _register_hotkeys(self) -> None:
        hk = self._config.hotkeys
        self._hotkeys.register(hk.add_screenshot, self._add_to_queue)
        self._hotkeys.register(hk.send,           self._send_queue)
        self._hotkeys.register(hk.clear_queue,    self._clear_queue)
        self._hotkeys.register(hk.clear_memory,   self._clear_memory)
        self._hotkeys.register(hk.toggle_overlay, self._toggle_overlay)

    # ── Startup ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        from src.ui.chat_overlay import ChatOverlay
        from src.audio.debounce_listener import DebounceAudioListener

        self._gemini = GeminiClient(self._config.api_key, self._config.models)
        self._mic    = MicRecorder()

        self._overlay = ChatOverlay(cfg=self._config.overlay)
        self._overlay.on_send              = self._handle_followup
        self._overlay.on_clear             = self._clear_memory
        self._overlay.on_mic_start         = self._mic.start
        self._overlay.on_mic_stop          = self._on_mic_stop
        self._overlay.on_auto_toggle       = self._on_auto_toggle
        self._overlay.on_screenshot        = self._add_to_queue_and_send
        self._overlay.start()

        # Screenshot queue
        self._queue:      list = []
        self._q_lock      = threading.Lock()
        self._processing  = False

        # Conversation memory
        self._history:    list = []
        self._hist_lock   = threading.Lock()

        # Auto mode (debounce listener runs continuously when toggled on)
        self._auto_active: bool = False
        self._debounce = DebounceAudioListener(
            silence_ms=1200,
            rms_threshold=self._config.audio.threshold,
            min_speech_ms=400,
        )
        self._debounce.on_mic_audio = self._on_auto_mic_audio
        self._debounce.on_sys_audio = self._on_auto_sys_audio

        print("👑  FullControlAgent ready.", flush=True)
        print("    k+,  Queue screenshot   k+.  Send   k+c  Clear   m+n  Toggle", flush=True)
        print("    🔊  Click in overlay to toggle live audio auto-mode", flush=True)

    def stop(self) -> None:
        if hasattr(self, "_debounce"):
            self._debounce.stop()
        super().stop()

    # ── Screenshot (Manual mode) ───────────────────────────────────────────────

    def _add_to_queue(self) -> None:
        img = take_screenshot()
        with self._q_lock:
            self._queue.append(img)
            n = len(self._queue)
        print(f"📸  Screenshot #{n} queued.", flush=True)

    def _add_to_queue_and_send(self) -> None:
        """One-shot: screenshot → immediately send."""
        img = take_screenshot()
        with self._q_lock:
            self._queue = [img]
        self._send_queue()

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
                self._overlay.set_thinking(True)
                self._overlay.show()
                parts = [types.Part(text=MANUAL_SYSTEM_PROMPT)] + [
                    self._gemini.make_image_part(image_to_bytes(img)) for img in imgs
                ]
                with self._hist_lock:
                    self._history.clear()
                    self._history.append({"role": "user", "parts": parts})
                contents = [types.Content(role="user", parts=parts)]
                answer   = self._gemini.generate(contents)
                with self._hist_lock:
                    self._history.append({"role": "model", "parts": [types.Part(text=answer)]})
                self._overlay.add_ai_message(answer)
            except Exception as e:
                self._overlay.add_ai_message(f"**Error:** {e}")
            finally:
                self._processing = False

        threading.Thread(target=_run, daemon=True).start()

    def _clear_queue(self) -> None:
        with self._q_lock:
            n, self._queue = len(self._queue), []
        print(f"🗑️  Cleared {n} screenshot(s).", flush=True)

    def _toggle_overlay(self) -> None:
        self._overlay.toggle()

    # ── Follow-up & memory ────────────────────────────────────────────────────

    def _handle_followup(self, text: str) -> None:
        """Manual text typed in the input box (works in both modes)."""
        self._overlay.add_user_message(text)
        self._overlay.set_thinking(True)

        with self._hist_lock:
            new_part = types.Part(text=text)
            if not self._history:
                self._history.append({
                    "role": "user",
                    "parts": [types.Part(text=MANUAL_SYSTEM_PROMPT + "\n\nUser: " + text)]
                })
            else:
                self._history.append({"role": "user", "parts": [new_part]})
            contents = [types.Content(role=t["role"], parts=t["parts"]) for t in self._history]

        def _run():
            try:
                answer = self._gemini.generate(contents)
                with self._hist_lock:
                    self._history.append({"role": "model", "parts": [types.Part(text=answer)]})
                    self._trim_history()
                self._overlay.add_ai_message(answer)
            except Exception as e:
                self._overlay.add_ai_message(f"**Error:** {e}")

        threading.Thread(target=_run, daemon=True).start()

    def _clear_memory(self) -> None:
        with self._hist_lock:
            self._history.clear()
        self._overlay.clear_chat()
        print("🗑️  Memory cleared.", flush=True)

    def _trim_history(self) -> None:
        max_items = MAX_TURNS * 2
        if len(self._history) > max_items:
            first   = self._history[:2]
            rest    = self._history[2:]
            self._history[:] = first + rest[-(max_items - 2):]

    # ── Mic (hold-to-talk) ────────────────────────────────────────────────────

    def _on_mic_stop(self) -> None:
        self._overlay.set_mic_transcribing(True)
        audio = self._mic.stop()
        self._overlay.set_mic_transcribing(False)
        if audio is not None:
            text = self._gemini.transcribe(audio)
            if text:
                self._overlay.set_input_text(text)

    # ── Auto mode (debounce VAD) ───────────────────────────────────────────────

    def _on_auto_toggle(self, active: bool) -> None:
        """Called when the 🔊 button in the overlay is clicked."""
        self._auto_active = active
        if active:
            self._debounce.start()
            print("logs: 🔊 Auto-mode ON — debounce listener active.", flush=True)
        else:
            self._debounce.stop()
            print("logs: 🔊 Auto-mode OFF.", flush=True)

    def _on_auto_mic_audio(self, audio_data) -> None:
        """Mic speech detected → transcribe → put in followup queue."""
        if not self._auto_active:
            return
        text = self._gemini.transcribe(audio_data)
        if not text or not text.strip():
            return
        print(f"logs: [You (auto)]: {text}", flush=True)
        # Show user speech in chat
        self._overlay.add_user_message(f"🎤 {text}")
        # Auto-query Gemini
        self._auto_query(text, source="You")

    def _on_auto_sys_audio(self, audio_data) -> None:
        """System (interviewer) speech detected → transcribe → auto Gemini."""
        if not self._auto_active:
            return
        text = self._gemini.transcribe(audio_data)
        if not text or not text.strip():
            return
        print(f"logs: [Interviewer (auto)]: {text}", flush=True)
        # Show interviewer speech in chat as system transcript
        self._overlay.add_system_audio_transcript(text)
        # Auto-query Gemini
        self._auto_query(text, source="Interviewer")

    def _auto_query(self, text: str, source: str = "Interviewer") -> None:
        """
        Send a detected transcript segment to Gemini with the concise prompt.
        Memory persists — follow-up context is maintained.
        """
        if self._processing:
            return  # Don't pile up requests during typing

        prompt = f"[{source}]: {text}"

        with self._hist_lock:
            if not self._history:
                # First turn — include system prompt
                self._history.append({
                    "role": "user",
                    "parts": [types.Part(text=AUTO_SYSTEM_PROMPT + "\n\n" + prompt)]
                })
            else:
                self._history.append({"role": "user", "parts": [types.Part(text=prompt)]})
            contents = [types.Content(role=t["role"], parts=t["parts"]) for t in self._history]

        self._overlay.set_thinking(True)
        self._overlay.show()

        def _run():
            try:
                answer = self._gemini.generate(contents)
                with self._hist_lock:
                    self._history.append({"role": "model", "parts": [types.Part(text=answer)]})
                    self._trim_history()
                self._overlay.add_ai_message(answer)
            except Exception as e:
                self._overlay.add_ai_message(f"**Error:** {e}")

        threading.Thread(target=_run, daemon=True).start()
