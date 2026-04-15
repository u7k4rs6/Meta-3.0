"""
src/audio/continuous_listener.py
Dual-stream continuous audio capture (mic + system loopback).
Volume-gated to prevent hallucinations.
Consolidated from full control transcript/audio.py.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS    = 1
DTYPE       = "int16"
CHUNK       = 1024


def _rms(audio: np.ndarray) -> float:
    if audio is None or len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(float) ** 2)))


class ContinuousAudioListener:
    """
    Simultaneously listens to:
    - Microphone (sounddevice)
    - System loopback (pyaudiowpatch WASAPI)

    Every `interval` seconds, chunks are volume-checked and, if above
    `threshold`, handed off for transcription via callbacks.

    Callbacks receive raw np.ndarray[int16]; caller handles transcription.
    """

    def __init__(self, interval: float = 10.0, threshold: float = 150.0):
        self.interval  = interval
        self.threshold = threshold

        # Set these before calling start()
        self.on_mic_audio: Optional[Callable[[np.ndarray], None]] = None
        self.on_sys_audio: Optional[Callable[[np.ndarray], None]] = None

        self._mic_frames: list  = []
        self._sys_frames: list  = []
        self._lock = threading.Lock()
        self._running = False

        self._mic_stream: Optional[sd.InputStream] = None
        self._pa   = None
        self._sys_stream = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._mic_frames = []
        self._sys_frames = []
        self._start_mic()
        self._start_sys_audio()
        threading.Thread(target=self._flush_loop, daemon=True).start()
        print("logs: 🎤+🔊 Continuous audio listener started.", flush=True)

    def stop(self) -> None:
        self._running = False
        if self._mic_stream:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
        if self._sys_stream:
            try:
                self._sys_stream.stop_stream()
                self._sys_stream.close()
            except Exception:
                pass
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass

    # ── Mic ───────────────────────────────────────────────────────────────────

    def _start_mic(self) -> None:
        def callback(indata, frames, time_info, status):
            with self._lock:
                if self._running:
                    self._mic_frames.append(indata.copy())

        self._mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=callback,
            blocksize=CHUNK,
        )
        self._mic_stream.start()

    # ── System audio ──────────────────────────────────────────────────────────

    def _start_sys_audio(self) -> None:
        try:
            import pyaudiowpatch as pyaudio

            self._pa = pyaudio.PyAudio()
            wasapi   = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            def_out  = wasapi["defaultOutputDevice"]
            def_name = self._pa.get_device_info_by_index(def_out).get("name", "")

            loopback_idx  = None
            loopback_info = None

            for i in range(self._pa.get_device_count()):
                d = self._pa.get_device_info_by_index(i)
                if d.get("isLoopbackDevice") and def_name in d.get("name", ""):
                    loopback_idx  = i
                    loopback_info = d
                    break

            if loopback_idx is None:
                for i in range(self._pa.get_device_count()):
                    d = self._pa.get_device_info_by_index(i)
                    if d.get("isLoopbackDevice") and int(d.get("maxInputChannels", 0)) > 0:
                        loopback_idx  = i
                        loopback_info = d
                        break

            if loopback_idx is None:
                print("❌  No WASAPI loopback device found.", flush=True)
                return

            rate     = int(loopback_info["defaultSampleRate"])
            channels = min(int(loopback_info["maxInputChannels"]), 2)

            def _sys_thread():
                self._sys_stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=loopback_idx,
                    frames_per_buffer=CHUNK,
                )
                while self._running:
                    try:
                        data = self._sys_stream.read(CHUNK, exception_on_overflow=False)
                        arr  = np.frombuffer(data, dtype=np.int16)
                        if channels == 2:
                            arr = arr.reshape(-1, 2).mean(axis=1).astype(np.int16)
                        with self._lock:
                            self._sys_frames.append(arr.reshape(-1, 1))
                    except Exception:
                        break

            threading.Thread(target=_sys_thread, daemon=True).start()

        except ImportError:
            print("❌  pyaudiowpatch not installed. System audio disabled.", flush=True)
        except Exception as e:
            print(f"❌  System audio error: {e}", flush=True)

    # ── Flush loop ────────────────────────────────────────────────────────────

    def _flush_loop(self) -> None:
        while self._running:
            time.sleep(self.interval)

            with self._lock:
                mic_audio = np.concatenate(self._mic_frames, axis=0) if self._mic_frames else None
                sys_audio = np.concatenate(self._sys_frames, axis=0) if self._sys_frames else None
                self._mic_frames = []
                self._sys_frames = []

            if mic_audio is not None and len(mic_audio) > SAMPLE_RATE:
                if _rms(mic_audio) > self.threshold and self.on_mic_audio:
                    threading.Thread(
                        target=self.on_mic_audio, args=(mic_audio,), daemon=True
                    ).start()

            if sys_audio is not None and len(sys_audio) > SAMPLE_RATE:
                if _rms(sys_audio) > self.threshold and self.on_sys_audio:
                    threading.Thread(
                        target=self.on_sys_audio, args=(sys_audio,), daemon=True
                    ).start()
