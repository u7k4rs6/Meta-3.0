"""
src/audio/mic_recorder.py
Press-to-talk microphone recorder.
Consolidated from full Control/audio.py MicRecorder class.
"""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS    = 1
DTYPE       = "int16"
CHUNK       = 1024


class MicRecorder:
    """
    Call start() to begin recording microphone input.
    Call stop() to end recording and return the raw numpy audio array.
    Transcription is handled by GeminiClient.transcribe().
    """

    def __init__(self):
        self._frames:   list  = []
        self._stream:   Optional[sd.InputStream] = None
        self._lock      = threading.Lock()
        self.recording  = False

    def start(self) -> None:
        self._frames  = []
        self.recording = True

        def callback(indata, frames, time, status):
            with self._lock:
                if self.recording:
                    self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=callback,
            blocksize=CHUNK,
        )
        self._stream.start()
        print("logs: 🎤 Mic recording started.", flush=True)

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording. Returns numpy int16 array or None if no audio."""
        self.recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = list(self._frames)

        if not frames:
            return None

        print("logs: 🎤 Mic stopped.", flush=True)
        return np.concatenate(frames, axis=0)
