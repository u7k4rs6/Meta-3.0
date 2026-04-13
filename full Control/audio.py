"""
audio.py — Mic and system audio capture + transcription via Gemini
"""
import io
import threading
import wave
import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

SAMPLE_RATE  = 16000
CHANNELS     = 1
DTYPE        = 'int16'
CHUNK        = 1024

TRANSCRIBE_PROMPT = (
    "Transcribe this audio exactly as spoken. "
    "Output only the transcribed text — no labels, no punctuation fixes, no commentary."
)


class MicRecorder:
    """
    Press-to-talk microphone recorder.
    Call start() to begin recording, stop() to finish and get transcription.
    """

    def __init__(self, gemini_client: genai.Client, model: str):
        self.client   = gemini_client
        self.model    = model
        self._frames  = []
        self._stream  = None
        self._lock    = threading.Lock()
        self.recording = False

    def start(self):
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
            blocksize=CHUNK
        )
        self._stream.start()
        print("logs: 🎤 Mic recording started.", flush=True)

    def stop(self) -> str | None:
        """Stop recording and return transcription."""
        self.recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = list(self._frames)

        if not frames:
            return None

        print("logs: 🎤 Mic stopped — transcribing...", flush=True)
        audio_data = np.concatenate(frames, axis=0)
        return self._transcribe(audio_data)

    def _transcribe(self, audio_data: np.ndarray) -> str | None:
        try:
            wav_bytes = self._to_wav(audio_data)
            response  = self.client.models.generate_content(
                model=self.model,
                contents=[
                    TRANSCRIBE_PROMPT,
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="audio/wav",
                            data=wav_bytes
                        )
                    )
                ]
            )
            text = response.text.strip()
            print(f"logs: Transcription: {text}", flush=True)
            return text
        except Exception as e:
            print(f"❌  Transcription error: {e}", flush=True)
            return None

    def _to_wav(self, audio_data: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)   # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        return buf.getvalue()


class SystemAudioListener:
    """
    Captures system audio (loopback) via WASAPI on Windows.
    Continuously buffers audio and transcribes on demand.
    Uses pyaudiowpatch for WASAPI loopback support.
    """

    def __init__(self, gemini_client: genai.Client, model: str, on_transcript):
        self.client        = gemini_client
        self.model         = model
        self.on_transcript = on_transcript   # callback(text: str)
        self._frames       = []
        self._lock         = threading.Lock()
        self._running      = False
        self._thread       = None
        self._pa           = None
        self._stream       = None

    def start(self):
        self._running = True
        self._frames  = []
        self._thread  = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("logs: 🔊 System audio listener started.", flush=True)

    def stop(self):
        self._running = False
        print("logs: 🔊 System audio listener stopped.", flush=True)

    def flush_and_transcribe(self):
        """Grab everything buffered so far and transcribe it."""
        with self._lock:
            frames      = list(self._frames)
            self._frames = []

        if not frames:
            return

        print("logs: 🔊 Transcribing system audio...", flush=True)
        audio_data = np.concatenate(frames, axis=0)

        def run():
            text = self._transcribe(audio_data)
            if text:
                self.on_transcript(text)

        threading.Thread(target=run, daemon=True).start()

    def _capture_loop(self):
        try:
            import pyaudiowpatch as pyaudio
            self._pa = pyaudio.PyAudio()

            # Find the default WASAPI loopback device
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = wasapi_info["defaultOutputDevice"]
            default_info = self._pa.get_device_info_by_index(default_out)
            default_name = default_info.get("name", "")

            # Find loopback device whose name matches the default output device
            loopback      = None
            loopback_info = None
            for i in range(self._pa.get_device_count()):
                d = self._pa.get_device_info_by_index(i)
                if d.get("isLoopbackDevice") and default_name in d.get("name", ""):
                    loopback      = i
                    loopback_info = d
                    break

            if loopback is None:
                # Fallback: first available loopback device
                for i in range(self._pa.get_device_count()):
                    d = self._pa.get_device_info_by_index(i)
                    if d.get("isLoopbackDevice") and int(d.get("maxInputChannels", 0)) > 0:
                        loopback      = i
                        loopback_info = d
                        break

            if loopback is None:
                print("❌  No WASAPI loopback device found. Install pyaudiowpatch.", flush=True)
                return

            rate     = int(loopback_info["defaultSampleRate"])
            channels = min(int(loopback_info["maxInputChannels"]), 2)

            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=loopback,
                frames_per_buffer=CHUNK
            )

            print(f"logs: 🔊 Capturing from: {loopback_info['name']} @ {rate}Hz", flush=True)

            while self._running:
                data = self._stream.read(CHUNK, exception_on_overflow=False)
                arr  = np.frombuffer(data, dtype=np.int16)
                # Mix to mono if stereo
                if channels == 2:
                    arr = arr.reshape(-1, 2).mean(axis=1).astype(np.int16)
                with self._lock:
                    self._frames.append(arr.reshape(-1, 1))

        except ImportError:
            print("❌  pyaudiowpatch not installed. Run: pip install pyaudiowpatch", flush=True)
        except Exception as e:
            print(f"❌  System audio error: {e}", flush=True)
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
            if self._pa:
                self._pa.terminate()

    def _transcribe(self, audio_data: np.ndarray) -> str | None:
        try:
            wav_bytes = MicRecorder._to_wav(self, audio_data)
            response  = self.client.models.generate_content(
                model=self.model,
                contents=[
                    TRANSCRIBE_PROMPT,
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="audio/wav",
                            data=wav_bytes
                        )
                    )
                ]
            )
            return response.text.strip()
        except Exception as e:
            print(f"❌  System audio transcription error: {e}", flush=True)
            return None