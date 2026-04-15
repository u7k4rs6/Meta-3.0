import os
import threading
import mss
import io
from PIL import Image
from google import genai
from google.genai import types
from pynput import keyboard
from pynput.keyboard import KeyCode
import sys
from dotenv import load_dotenv
from overlay import OverlayWindow
from audio import ContinuousAudioListener

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️  CRITICAL: GEMINI_API_KEY not found.")
    sys.exit(1)

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]

SYSTEM_PROMPT = (
    "You are an interview assistant. You are provided with a real-time transcript "
    "of a conversation between a User and an Interviewer, and potentially a screenshot."
    "Your goal is to identify the most recent question or problem posed by the interviewer "
    "and provide a helpful, concise solution or answer for the User. "
    "If the interviewer is asking a coding question, provide clean code and a brief explanation. "
    "If a screenshot is provided, use it to understand the problem better (e.g. looking at a coding challenge). "
    "Always maintain context from the previous parts of the transcript."
)

# ── Screenshot ────────────────────────────────────────────────────────────────
def take_screenshot() -> Image.Image:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[0])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

def image_to_part(img: Image.Image) -> types.Part:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return types.Part(inline_data=types.Blob(mime_type="image/png", data=buf.getvalue()))

# ────────────────────────────────────────────────────────────────────────────

client = genai.Client(api_key=GEMINI_API_KEY)
overlay = OverlayWindow()
listener = ContinuousAudioListener(client, GEMINI_MODELS, interval=10.0)

transcript_lock = threading.Lock()
transcript_history = []  # List of (role, text)

pressed_keys = set()
KEY_ANCHOR = 'k'

# ── Transcription Handlers ──────────────────────────────────────────────────

def on_user_transcript(text: str):
    print(f"logs: [User]: {text}", flush=True)
    with transcript_lock:
        transcript_history.append(("User", text))
    overlay.add_user_message(text)

def on_interviewer_transcript(text: str):
    print(f"logs: [Interviewer]: {text}", flush=True)
    with transcript_lock:
        transcript_history.append(("Interviewer", text))
    overlay.add_system_audio_transcript(text)

# ── Gemini Query ────────────────────────────────────────────────────────────

def query_gemini_transcript(image: Image.Image = None):
    with transcript_lock:
        if not transcript_history and not image:
            print("⚠️ Transcript and image empty.", flush=True)
            return
        
        # Build prompt from history
        context_str = "\n".join([f"[{role}]: {text}" for role, text in transcript_history])
    
    text_part = types.Part(text=f"{SYSTEM_PROMPT}\n\nTRANSCRIPT:\n{context_str}\n\n[Action]: Provide the answer to the latest interviewer question.")
    parts = [text_part]
    if image:
        parts.append(image_to_part(image))
        print("logs: Sending transcript + screenshot to Gemini...", flush=True)
    else:
        print("logs: Sending transcript to Gemini...", flush=True)

    overlay.set_thinking(True)
    overlay.show()
    
    def run():
        last_error = None
        for model in GEMINI_MODELS:
            try:
                print(f"logs: Querying {model}...", flush=True)
                response = client.models.generate_content(
                    model=model,
                    contents=[types.Content(role="user", parts=parts)]
                )
                answer = response.text.strip()
                overlay.add_ai_message(answer)
                return
            except Exception as e:
                print(f"logs: ⚠️ {model} failed: {e}", flush=True)
                last_error = e
        
        overlay.add_ai_message(f"**Error:** All models failed. {last_error}")

    threading.Thread(target=run, daemon=True).start()

def handle_followup(text: str):
    """Manual follow-up query."""
    overlay.set_thinking(True)
    
    with transcript_lock:
        context_str = "\n".join([f"[{role}]: {text}" for role, text in transcript_history])
    
    full_prompt = f"Transcript Context:\n{context_str}\n\nUser Question: {text}"
    
    def run():
        for model in GEMINI_MODELS:
            try:
                response = client.models.generate_content(model=model, contents=[full_prompt])
                overlay.add_ai_message(response.text.strip())
                return
            except: continue
    
    threading.Thread(target=run, daemon=True).start()

def clear_memory():
    with transcript_lock:
        transcript_history.clear()
    overlay.clear_chat()
    print("🗑️ Transcript and chat cleared.", flush=True)

# ── Keyboard Listeners ──────────────────────────────────────────────────────

def get_char(key):
    try:
        return key.char
    except AttributeError:
        return None

def on_press(key):
    pressed_keys.add(key)
    chars = {get_char(k) for k in pressed_keys}
    lower = {c.lower() for c in chars if c}

    # m + n -> toggle
    if 'm' in lower and 'n' in lower:
        pressed_keys.clear()
        overlay.toggle()
        return

    if KEY_ANCHOR in lower:
        # k + . -> query transcript only
        if '.' in chars:
            pressed_keys.clear()
            query_gemini_transcript()
        # k + , -> query transcript + screenshot
        elif ',' in chars:
            pressed_keys.clear()
            img = take_screenshot()
            query_gemini_transcript(image=img)
        elif 'c' in lower:
            pressed_keys.clear()
            clear_memory()

def on_release(key):
    if key in pressed_keys:
        pressed_keys.discard(key)

# ── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    overlay.start()
    overlay.on_send = handle_followup
    overlay.on_clear = clear_memory
    
    listener.on_mic_transcript = on_user_transcript
    listener.on_sys_transcript = on_interviewer_transcript
    listener.start()
    
    print("🚀 Real-time Transcript AI started.")
    print("    Always listening to Mic and System Audio.")
    print("    k + .        -> Send transcript to Gemini")
    print("    k + ,        -> Send transcript + screenshot to Gemini")
    print("    k + c        -> Clear transcript buffer")
    print("    m + n        -> Toggle overlay")
    
    with keyboard.Listener(on_press=on_press, on_release=on_release) as kb_listener:
        kb_listener.join()
