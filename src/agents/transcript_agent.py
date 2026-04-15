"""
src/agents/transcript_agent.py
Always-on dual-stream transcript → k+. sends to Gemini for answer.
k+, sends transcript + screenshot.
Migrated from full control transcript/main.py.
"""
from __future__ import annotations

import threading
from typing import List

from google.genai import types

from src.agents.base_agent import BaseAgent, HotkeyDef
from src.audio.continuous_listener import ContinuousAudioListener
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot, image_to_bytes

SYSTEM_PROMPT = (
    "You are an interview assistant. You are given a real-time transcript "
    "of a conversation between a User and an Interviewer, and optionally a screenshot. "
    "Identify the most recent question posed by the Interviewer and provide "
    "a clear, helpful answer for the User. "
    "If a coding question is asked, provide clean working code. "
    "If a screenshot is provided, use it to understand the problem visually. "
    "Maintain full context from the transcript."
)


class TranscriptAgent(BaseAgent):

    def get_name(self) -> str:
        return "Real-Time Transcript"

    def get_description(self) -> str:
        return "Continuously listens to mic + system audio, builds a transcript, analyzes on demand."

    def get_default_hotkeys(self) -> List[HotkeyDef]:
        return [
            HotkeyDef("k+.", "Send transcript to Gemini"),
            HotkeyDef("k+,", "Send transcript + screenshot"),
            HotkeyDef("k+c", "Clear transcript buffer"),
            HotkeyDef("m+n", "Toggle overlay"),
        ]

    def _register_hotkeys(self) -> None:
        hk = self._config.hotkeys
        self._hotkeys.register(hk.send_transcript,  self._query_transcript)
        self._hotkeys.register(hk.send_with_shot,   self._query_with_screenshot)
        self._hotkeys.register(hk.clear_memory,     self._clear_transcript)
        self._hotkeys.register(hk.toggle_overlay,   self._toggle_overlay)

    def _run(self) -> None:
        from src.ui.chat_overlay import ChatOverlay
        self._gemini   = GeminiClient(self._config.api_key, self._config.models)
        self._overlay  = ChatOverlay(cfg=self._config.overlay)
        self._overlay.on_send   = self._handle_followup
        self._overlay.on_clear  = self._clear_transcript
        self._overlay.start()

        self._transcript: list  = []   # [(role, text)]
        self._t_lock      = threading.Lock()

        self._audio = ContinuousAudioListener(
            interval=self._config.audio.interval,
            threshold=self._config.audio.threshold,
        )
        self._audio.on_mic_audio = self._on_user_audio
        self._audio.on_sys_audio = self._on_sys_audio
        self._audio.start()

        print("📝  TranscriptAgent running — always listening.", flush=True)
        print("    k+.  Analyze transcript   k+,  +Screenshot   k+c  Clear   m+n  Toggle", flush=True)

    def stop(self) -> None:
        self._audio.stop()
        super().stop()

    # ── Audio callbacks ───────────────────────────────────────────────────────

    def _on_user_audio(self, audio_data) -> None:
        text = self._gemini.transcribe(audio_data)
        if text and text.strip():
            print(f"logs: [User]: {text}", flush=True)
            with self._t_lock:
                self._transcript.append(("User", text))
            self._overlay.add_user_message(text)

    def _on_sys_audio(self, audio_data) -> None:
        text = self._gemini.transcribe(audio_data)
        if text and text.strip():
            print(f"logs: [Interviewer]: {text}", flush=True)
            with self._t_lock:
                self._transcript.append(("Interviewer", text))
            self._overlay.add_system_audio_transcript(text)

    # ── Query ─────────────────────────────────────────────────────────────────

    def _query_transcript(self) -> None:
        self._query(image=None)

    def _query_with_screenshot(self) -> None:
        img = take_screenshot()
        self._query(image=img)

    def _query(self, image=None) -> None:
        with self._t_lock:
            if not self._transcript and image is None:
                print("⚠️  Nothing to send.", flush=True)
                return
            context = "\n".join(f"[{r}]: {t}" for r, t in self._transcript)

        prompt_text = (
            f"{SYSTEM_PROMPT}\n\nTRANSCRIPT:\n{context}\n\n"
            "[Task]: Answer the most recent Interviewer question."
        )
        parts = [types.Part(text=prompt_text)]
        if image is not None:
            parts.append(self._gemini.make_image_part(image_to_bytes(image)))
            print("logs: Sending transcript + screenshot to Gemini...", flush=True)
        else:
            print("logs: Sending transcript to Gemini...", flush=True)

        self._overlay.set_thinking(True)
        self._overlay.show()

        def _run():
            try:
                answer = self._gemini.generate(
                    types.Content(role="user", parts=parts)
                )
                self._overlay.add_ai_message(answer)
            except Exception as e:
                self._overlay.add_ai_message(f"**Error:** {e}")

        threading.Thread(target=_run, daemon=True).start()

    def _handle_followup(self, text: str) -> None:
        """Text typed manually in the overlay input box."""
        with self._t_lock:
            context = "\n".join(f"[{r}]: {t}" for r, t in self._transcript)
        full = f"Transcript context:\n{context}\n\nFollow-up question: {text}"
        self._overlay.set_thinking(True)

        def _run():
            try:
                answer = self._gemini.generate(full)
                self._overlay.add_ai_message(answer)
            except Exception as e:
                self._overlay.add_ai_message(f"**Error:** {e}")

        threading.Thread(target=_run, daemon=True).start()

    def _clear_transcript(self) -> None:
        with self._t_lock:
            self._transcript.clear()
        self._overlay.clear_chat()
        print("🗑️  Transcript cleared.", flush=True)

    def _toggle_overlay(self) -> None:
        self._overlay.toggle()
