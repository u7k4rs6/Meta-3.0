"""
src/core/gemini_client.py
Single Gemini wrapper with model-fallback and transcription.
All agents use this — zero duplication.
"""
from __future__ import annotations

import io
import wave
from typing import List, Optional, Any

import numpy as np
from google import genai
from google.genai import types


class GeminiClient:
    """
    Wraps google.genai with:
    - Automatic model fallback (Flash → Pro → Flash-Lite)
    - Unified generate() for text/image content
    - Unified transcribe() for audio bytes
    """

    TRANSCRIBE_PROMPT = (
        "Transcribe this audio exactly as spoken. "
        "Output only the transcribed text — no labels, no punctuation fixes, no commentary. "
        "If the audio contains only background noise, silence, or is unintelligible, return an empty string. "
        "Do not hallucinate or add any phrases not present in the audio."
    )

    def __init__(self, api_key: str, models: List[str]):
        self._client = genai.Client(api_key=api_key)
        self.models  = models

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self, contents: Any, models: Optional[List[str]] = None) -> str:
        """
        Call Gemini with fallback.
        `contents` can be a string, list of strings/Parts, or a Content object.
        Returns the text response.
        Raises RuntimeError if all models fail.
        """
        model_list = models or self.models
        last_error = None
        for model in model_list:
            try:
                print(f"logs: Trying {model}...", flush=True)
                response = self._client.models.generate_content(
                    model=model, contents=contents
                )
                text = response.text.strip()
                print(f"logs: ✅ {model} responded.", flush=True)
                return text
            except Exception as e:
                print(f"logs: ⚠️  {model} failed — {e}", flush=True)
                last_error = e
        raise RuntimeError(f"All Gemini models failed. Last: {last_error}")

    def transcribe(self, audio_data: np.ndarray,
                   sample_rate: int = 16000,
                   models: Optional[List[str]] = None) -> Optional[str]:
        """
        Transcribe raw int16 numpy audio via Gemini.
        Returns transcribed string or None on failure.
        """
        wav_bytes  = self._to_wav(audio_data, sample_rate)
        model_list = models or self.models
        last_error = None
        for model in model_list:
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=[
                        self.TRANSCRIBE_PROMPT,
                        types.Part(inline_data=types.Blob(
                            mime_type="audio/wav", data=wav_bytes
                        ))
                    ]
                )
                text = response.text.strip()
                return text if text else None
            except Exception as e:
                print(f"logs: ⚠️  Transcribe {model} failed — {e}", flush=True)
                last_error = e

        print(f"❌  All transcription models failed: {last_error}", flush=True)
        return None

    def make_image_part(self, img_bytes: bytes) -> types.Part:
        return types.Part(inline_data=types.Blob(mime_type="image/png", data=img_bytes))

    def make_content(self, role: str, parts: list) -> types.Content:
        return types.Content(role=role, parts=parts)

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_wav(audio_data: np.ndarray, sample_rate: int) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)    # int16 = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())
        return buf.getvalue()
