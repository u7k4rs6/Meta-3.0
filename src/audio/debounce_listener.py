"""
src/audio/debounce_listener.py
Voice-Activity-Detection (VAD) debounce audio listener.

Instead of a fixed interval flush, we accumulate audio while speech
is detected (RMS > threshold) and fire the callback automatically
when silence of SILENCE_MS duration is detected — exactly like Cluely.

Both mic and system loopback (interviewer) are handled independently.
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


class DebounceAudioListener:
    """
    Simultaneously captures microphone and system loopback audio.

    - Buffers frames whenever RMS > rms_threshold (speech detected)
    - When silence >= silence_ms, fires the callback with accumulated audio
    - Clips shorter than min_speech_ms are silently dropped
    - Monitor loop polls every 100 ms — very responsive

    Usage:
        listener = DebounceAudioListener(silence_ms=1200, rms_threshold=180)
        listener.on_mic_audio = fn   # called with np.ndarray int16
        listener.on_sys_audio = fn
        listener.start()
        ...
        listener.stop()
    """

    def __init__(
        self,
        silence_ms:   int   = 1200,
        rms_threshold: float = 180.0,
        min_speech_ms: int  = 400,
    ):
        self.silence_ms    = silence_ms
        self.rms_threshold = rms_threshold
        self.min_speech_ms = min_speech_ms

        self.on_mic_audio: Optional[Callable[[np.ndarray], None]] = None
        self.on_sys_audio: Optional[Callable[[np.ndarray], None]] = None

        self._lock       = threading.Lock()
        self._running    = False

        # Mic state
        self._mic_frames:     list  = []
        self._mic_last_active: float = 0.0
        self._mic_has_speech: bool  = False

        # Sys state
        self._sys_frames:     list  = []
        self._sys_last_active: float = 0.0
        self._sys_has_speech: bool  = False

        self._mic_stream = None
        self._pa         = None
        self._sys_stream = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        now = time.monotonic()
        self._running         = True
        self._mic_frames      = []
        self._sys_frames      = []
        self._mic_last_active = now
        self._sys_last_active = now
        self._mic_has_speech  = False
        self._sys_has_speech  = False

        self._start_mic()
        self._start_sys_audio()
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        print("logs: 🎤+🔊 Debounce audio listener started.", flush=True)

    def stop(self) -> None:
        self._running = False
        for attr in ("_mic_stream", "_sys_stream"):
            s = getattr(self, attr, None)
            if s:
                try:
                    if hasattr(s, "stop"):   s.stop()
                    if hasattr(s, "close"):  s.close()
                    if hasattr(s, "stop_stream"): s.stop_stream()
                except Exception:
                    pass
        if self._pa:
            try: self._pa.terminate()
            except Exception: pass
        print("logs: Debounce listener stopped.", flush=True)

    # ── Mic ───────────────────────────────────────────────────────────────────

    def _start_mic(self) -> None:
        def callback(indata, frames, time_info, status):
            chunk = indata.copy().flatten().astype(np.int16)
            rms   = _rms(chunk)
            with self._lock:
                if not self._running:
                    return
                if rms > self.rms_threshold:
                    self._mic_frames.append(chunk)
                    self._mic_last_active = time.monotonic()
                    self._mic_has_speech  = True
                elif self._mic_has_speech:
                    # Buffer mild-silence within an active speech segment
                    self._mic_frames.append(chunk)

        try:
            self._mic_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=callback,
                blocksize=CHUNK,
            )
            self._mic_stream.start()
        except Exception as e:
            print(f"❌  Mic stream error: {e}", flush=True)

    # ── System audio (WASAPI loopback) ────────────────────────────────────────

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
                print("❌  No WASAPI loopback found — system audio disabled.", flush=True)
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
                        chunk = arr.flatten()
                        rms   = _rms(chunk)
                        with self._lock:
                            if rms > self.rms_threshold:
                                self._sys_frames.append(chunk)
                                self._sys_last_active = time.monotonic()
                                self._sys_has_speech  = True
                            elif self._sys_has_speech:
                                self._sys_frames.append(chunk)
                    except Exception:
                        break

            threading.Thread(target=_sys_thread, daemon=True).start()
            print(f"logs: 🔊 Loopback: {loopback_info['name']} @ {rate}Hz", flush=True)

        except ImportError:
            print("❌  pyaudiowpatch not installed — system audio disabled.", flush=True)
        except Exception as e:
            print(f"❌  System audio init error: {e}", flush=True)

    # ── Monitor loop (debounce) ───────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        """Polls every 100 ms. When silence >= silence_ms after speech, fires callback."""
        silence_secs   = self.silence_ms    / 1000.0
        min_speech_sec = self.min_speech_ms / 1000.0

        while self._running:
            time.sleep(0.1)
            now = time.monotonic()

            with self._lock:
                # ── Mic check ────────────────────────────────────────────────
                if (self._mic_has_speech
                        and self._mic_frames
                        and (now - self._mic_last_active) >= silence_secs):
                    frames, self._mic_frames = list(self._mic_frames), []
                    self._mic_has_speech = False
                    if frames:
                        audio = np.concatenate(frames)
                        dur   = len(audio) / SAMPLE_RATE
                        if dur >= min_speech_sec and self.on_mic_audio:
                            cb = self.on_mic_audio
                            threading.Thread(
                                target=cb, args=(audio,), daemon=True
                            ).start()

                # ── Sys check ─────────────────────────────────────────────────
                if (self._sys_has_speech
                        and self._sys_frames
                        and (now - self._sys_last_active) >= silence_secs):
                    frames, self._sys_frames = list(self._sys_frames), []
                    self._sys_has_speech = False
                    if frames:
                        audio = np.concatenate(frames)
                        dur   = len(audio) / SAMPLE_RATE
                        if dur >= min_speech_sec and self.on_sys_audio:
                            cb = self.on_sys_audio
                            threading.Thread(
                                target=cb, args=(audio,), daemon=True
                            ).start()
