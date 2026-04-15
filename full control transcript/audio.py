"""
audio.py — Continuous Mic and System Audio capture + transcription via Gemini
"""
import io
import threading
import wave
import numpy as np
import sounddevice as sd
import time
from google import genai
from google.genai import types

SAMPLE_RATE  = 16000
CHANNELS     = 1
DTYPE        = 'int16'
CHUNK        = 1024

TRANSCRIBE_PROMPT = (
    "Transcribe this audio exactly as spoken. "
    "Output only the transcribed text — no labels, no punctuation fixes, no commentary. "
    "If the audio contains only background noise, silence, or is unintelligible, return an empty string. "
    "Do not hallucinate or add any religious or generic phrases that are not present."
)

def get_rms(audio_data):
    """Calculate the Root Mean Square volume of the audio data."""
    if audio_data is None or len(audio_data) == 0:
        return 0
    return np.sqrt(np.mean(audio_data.astype(float)**2))

class ContinuousAudioListener:
    """
    Simultaneously listens to Mic and System Audio (loopback).
    Periodically flushes and transcribes each stream.
    """
    def __init__(self, gemini_client: genai.Client, models: list[str], interval=10.0, threshold=150.0):
        self.client = gemini_client
        self.models = models
        self.interval = interval
        self.threshold = threshold # Volume threshold to avoid transcribing silence
        
        self.on_mic_transcript = None # Callback(text)
        self.on_sys_transcript = None # Callback(text)
        
        self._mic_frames = []
        self._sys_frames = []
        self._lock = threading.Lock()
        self._running = False
        
        self._mic_stream = None
        self._sys_stream = None
        self._pa = None

    def start(self):
        self._running = True
        self._mic_frames = []
        self._sys_frames = []
        
        # Start Mic Stream (sounddevice)
        def mic_callback(indata, frames, time_info, status):
            with self._lock:
                if self._running:
                    self._mic_frames.append(indata.copy())

        self._mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=mic_callback,
            blocksize=CHUNK
        )
        self._mic_stream.start()
        
        # Start System Audio Stream (pyaudiowpatch)
        self._start_sys_audio()
        
        # Start Transcription Loop
        threading.Thread(target=self._transcription_loop, daemon=True).start()
        print("logs: 🎤+🔊 Continuous listening started.", flush=True)

    def stop(self):
        self._running = False
        if self._mic_stream:
            self._mic_stream.stop()
            self._mic_stream.close()
        if self._sys_stream:
            try:
                self._sys_stream.stop_stream()
                self._sys_stream.close()
            except: pass
        if self._pa:
            try: self._pa.terminate()
            except: pass

    def _start_sys_audio(self):
        try:
            import pyaudiowpatch as pyaudio
            self._pa = pyaudio.PyAudio()

            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = wasapi_info["defaultOutputDevice"]
            default_info = self._pa.get_device_info_by_index(default_out)
            default_name = default_info.get("name", "")

            loopback = None
            for i in range(self._pa.get_device_count()):
                d = self._pa.get_device_info_by_index(i)
                if d.get("isLoopbackDevice") and default_name in d.get("name", ""):
                    loopback = i
                    loopback_info = d
                    break
            
            if loopback is None:
                for i in range(self._pa.get_device_count()):
                    d = self._pa.get_device_info_by_index(i)
                    if d.get("isLoopbackDevice") and int(d.get("maxInputChannels", 0)) > 0:
                        loopback = i
                        loopback_info = d
                        break

            if loopback is None:
                print("❌ No WASAPI loopback found.", flush=True)
                return

            rate = int(loopback_info["defaultSampleRate"])
            channels = min(int(loopback_info["maxInputChannels"]), 2)

            def sys_thread():
                self._sys_stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=loopback,
                    frames_per_buffer=CHUNK
                )
                while self._running:
                    try:
                        data = self._sys_stream.read(CHUNK, exception_on_overflow=False)
                        arr = np.frombuffer(data, dtype=np.int16)
                        if channels == 2:
                            arr = arr.reshape(-1, 2).mean(axis=1).astype(np.int16)
                        with self._lock:
                            self._sys_frames.append(arr.reshape(-1, 1))
                    except: break
            
            threading.Thread(target=sys_thread, daemon=True).start()
            
        except Exception as e:
            print(f"❌ System audio error: {e}", flush=True)

    def _transcription_loop(self):
        while self._running:
            time.sleep(self.interval)
            
            with self._lock:
                mic_audio = np.concatenate(self._mic_frames, axis=0) if self._mic_frames else None
                sys_audio = np.concatenate(self._sys_frames, axis=0) if self._sys_frames else None
                self._mic_frames = []
                self._sys_frames = []
            
            if mic_audio is not None and len(mic_audio) > SAMPLE_RATE * 1: # at least 1s
                vol = get_rms(mic_audio)
                if vol > self.threshold:
                    threading.Thread(target=self._proc_transcription, args=(mic_audio, "user"), daemon=True).start()
                else:
                    pass # Ignore silence

            if sys_audio is not None and len(sys_audio) > SAMPLE_RATE * 1:
                vol = get_rms(sys_audio)
                if vol > self.threshold:
                    threading.Thread(target=self._proc_transcription, args=(sys_audio, "interviewer"), daemon=True).start()
                else:
                    pass

    def _proc_transcription(self, audio_data, source):
        wav_bytes = self._to_wav(audio_data)
        text = self._gemini_transcribe(wav_bytes)
        if text and text.strip():
            if source == "user" and self.on_mic_transcript:
                self.on_mic_transcript(text)
            elif source == "interviewer" and self.on_sys_transcript:
                self.on_sys_transcript(text)

    def _gemini_transcribe(self, wav_bytes):
        for model in self.models:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=[
                        TRANSCRIBE_PROMPT,
                        types.Part(inline_data=types.Blob(mime_type="audio/wav", data=wav_bytes))
                    ]
                )
                return response.text.strip()
            except: continue
        return None

    def _to_wav(self, audio_data: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        return buf.getvalue()
