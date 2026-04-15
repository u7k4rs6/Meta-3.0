import os
import threading
import mss
from PIL import Image
from google import genai
from google.genai import types
from pynput import keyboard
from pynput.keyboard import KeyCode
import sys
import io
from dotenv import load_dotenv
from overlay import OverlayWindow
from audio import MicRecorder, SystemAudioListener

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
MAX_TURNS    = 10   # max conversation turns kept in memory (each turn = 1 user + 1 model)

SYSTEM_PROMPT = (
    "You are a helpful AI assistant embedded in a floating overlay. "
    "The user will send you screenshots of problems they are looking at. "
    "Analyze the screenshot and respond with the most useful answer. "
    "- Coding problem → working solution with brief explanation. "
    "- Theory / concept → clear structured answer. "
    "- MCQ → correct option and why. "
    "- Math → solution with steps. "
    "- Anything else → most helpful concise answer. "
    "Format in clean Markdown. Use ## headings, **bold**, and ```language code blocks. "
    "For follow-up questions, use the full conversation context."
)
# ────────────────────────────────────────────────────────────────────────────

client  = genai.Client(api_key=GEMINI_API_KEY)
overlay = OverlayWindow()
mic     = MicRecorder(client, GEMINI_MODELS)
sysaudio = SystemAudioListener(client, GEMINI_MODELS, on_transcript=None)   # callback set below

screenshot_queue: list[Image.Image] = []
queue_lock   = threading.Lock()
processing   = False
pressed_keys = set()

KEY_ANCHOR = 'k'
KEY_ADD    = ','
KEY_SEND   = '.'
KEY_CLEAR  = '/'
VK_SLASH   = KeyCode.from_vk(0xBF)

# ── Conversation memory ───────────────────────────────────────────────────────
conversation_history: list[dict] = []
history_lock = threading.Lock()


def _trim_history():
    """Keep only the last MAX_TURNS pairs. Images are only in turn 0 so we
    keep them even if they fall outside the window — they anchor context."""
    with history_lock:
        # A "pair" = 1 user entry + 1 model entry = 2 items
        max_items = MAX_TURNS * 2
        if len(conversation_history) > max_items:
            # Always keep the very first turn (has the screenshots)
            first = conversation_history[:2]
            rest  = conversation_history[2:]
            trimmed = rest[-(max_items - 2):]
            conversation_history.clear()
            conversation_history.extend(first + trimmed)
            print(f"logs: History trimmed to {len(conversation_history)} entries.", flush=True)


def clear_memory():
    with history_lock:
        conversation_history.clear()
    overlay.clear_chat()
    print("🗑️   Memory & chat cleared.", flush=True)


# ── Screenshot ────────────────────────────────────────────────────────────────
def take_screenshot() -> Image.Image:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[0])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def image_to_part(img: Image.Image) -> types.Part:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return types.Part(inline_data=types.Blob(mime_type="image/png", data=buf.getvalue()))


# ── Gemini calls with fallback ────────────────────────────────────────────────
def query_gemini_screenshot(images: list[Image.Image]) -> str:
    parts = [types.Part(text=SYSTEM_PROMPT)] + [image_to_part(i) for i in images]
    user_turn = types.Content(role="user", parts=parts)

    with history_lock:
        conversation_history.clear()
        conversation_history.append({"role": "user", "parts": parts})

    print(f"logs: Sending {len(images)} screenshot(s) to Gemini...", flush=True)
    last_error = None

    for model in GEMINI_MODELS:
        try:
            print(f"logs: Trying model {model}...", flush=True)
            response = client.models.generate_content(model=model, contents=[user_turn])
            answer = response.text.strip()
            print(f"logs: ✅ Response from {model}", flush=True)

            with history_lock:
                conversation_history.append({"role": "model", "parts": [types.Part(text=answer)]})
            
            return answer
        except Exception as e:
            print(f"logs: ⚠️  {model} failed — {e}", flush=True)
            last_error = e

    raise RuntimeError(f"All models failed for screenshot. Last error: {last_error}")


def query_gemini_followup(text: str) -> str:
    new_part = types.Part(text=text)

    with history_lock:
        conversation_history.append({"role": "user", "parts": [new_part]})
        contents = [
            types.Content(role=t["role"], parts=t["parts"])
            for t in conversation_history
        ]

    turns = len(contents)
    print(f"logs: Follow-up → Gemini (history: {turns} turns)...", flush=True)
    last_error = None

    for model in GEMINI_MODELS:
        try:
            print(f"logs: Trying model {model} for follow-up...", flush=True)
            response = client.models.generate_content(model=model, contents=contents)
            answer = response.text.strip()
            print(f"logs: ✅ Response from {model}", flush=True)

            with history_lock:
                conversation_history.append({"role": "model", "parts": [types.Part(text=answer)]})

            _trim_history()
            return answer
        except Exception as e:
            print(f"logs: ⚠️  {model} failed — {e}", flush=True)
            last_error = e

    raise RuntimeError(f"All models failed for follow-up. Last error: {last_error}")


# ── Follow-up handler ─────────────────────────────────────────────────────────
def handle_followup(text: str):
    if not conversation_history:
        with history_lock:
            conversation_history.append({
                "role": "user",
                "parts": [types.Part(text=SYSTEM_PROMPT + "\n\n" + text)]
            })

    overlay.add_user_message(text)
    overlay.set_thinking(True)

    try:
        answer = query_gemini_followup(text)
        overlay.add_ai_message(answer)
    except Exception as e:
        overlay.add_ai_message(f"**Error:** {e}")
        print(f"❌  Follow-up error: {e}", flush=True)


# ── Mic handlers ──────────────────────────────────────────────────────────────
def on_mic_start():
    mic.start()


def on_mic_stop():
    overlay.set_mic_transcribing(True)
    text = mic.stop()
    overlay.set_mic_transcribing(False)
    if text:
        overlay.set_input_text(text)   # put transcription in input field — user can edit then send


# ── System audio handler ──────────────────────────────────────────────────────
def on_sysaudio_transcript(text: str):
    """Called when system audio is transcribed — show it and auto-ask Gemini."""
    print(f"logs: 🔊 Interviewer said: {text}", flush=True)
    overlay.add_system_audio_transcript(text)
    handle_followup(f"[Interviewer asked]: {text}")


def on_sysaudio_toggle(active: bool):
    if active:
        sysaudio.on_transcript = on_sysaudio_transcript
        sysaudio.start()
    else:
        sysaudio.stop()


# ── Hotkey actions ───────────────────────────────────────────────────────────
def add_to_queue():
    img = take_screenshot()
    with queue_lock:
        screenshot_queue.append(img)
        count = len(screenshot_queue)
    print(f"📸  Screenshot #{count} added to queue.", flush=True)


def send_queue():
    global processing
    with queue_lock:
        if not screenshot_queue:
            print("⚠️   Queue empty.", flush=True)
            return
        images_to_send = list(screenshot_queue)
        screenshot_queue.clear()
    if processing:
        return
    processing = True

    def run():
        global processing
        try:
            overlay.set_thinking(True)
            overlay.show()
            answer = query_gemini_screenshot(images_to_send)
            overlay.add_ai_message(answer)
        except Exception as e:
            overlay.add_ai_message(f"**Error:** {e}")
            print(f"❌  {e}", flush=True)
        finally:
            processing = False

    threading.Thread(target=run, daemon=True).start()


def clear_queue():
    with queue_lock:
        count = len(screenshot_queue)
        screenshot_queue.clear()
    print(f"🗑️   Queue cleared ({count} screenshots).", flush=True)


# ── Test mode ─────────────────────────────────────────────────────────────────
TEST_MD = """## Binary Search

**Concept:** Repeatedly halve the search space by comparing to the middle element.

**Time complexity:** `O(log n)`

### Solution

```java
public int search(int[] nums, int target) {
    int left = 0, right = nums.length - 1;
    while (left <= right) {
        int mid = left + (right - left) / 2;
        if (nums[mid] == target) return mid;
        if (nums[mid] < target) left = mid + 1;
        else right = mid - 1;
    }
    return -1;
}
```

- Returns `-1` if target not found
- `left + (right - left) / 2` avoids **integer overflow**
"""


# ── Keyboard listener ─────────────────────────────────────────────────────────
def get_char(key):
    try:
        return key.char
    except AttributeError:
        return None


def on_press(key):
    pressed_keys.add(key)
    chars = {get_char(k) for k in pressed_keys}
    lower = {c.lower() for c in chars if c}

    if 'm' in lower and 'n' in lower:
        pressed_keys.clear()
        overlay.toggle()
        return

    if KEY_ANCHOR in lower:
        if 't' in lower:
            pressed_keys.clear()
            overlay.show()
            overlay.add_ai_message(TEST_MD)
        elif 'c' in lower:
            pressed_keys.clear()
            clear_memory()
        elif KEY_ADD in chars:
            pressed_keys.clear()
            add_to_queue()
        elif KEY_SEND in chars:
            pressed_keys.clear()
            send_queue()
        elif KEY_CLEAR in chars:
            pressed_keys.clear()
            clear_queue()


def on_release(key):
    pressed_keys.discard(key)


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    overlay.start()
    overlay.on_send           = handle_followup
    overlay.on_clear          = clear_memory
    overlay.on_mic_start      = on_mic_start
    overlay.on_mic_stop       = on_mic_stop
    overlay.on_sysaudio_toggle = on_sysaudio_toggle

    print("🚀  Screenshot-AI (Overlay) running.")
    print(f"    k + ,   →  Add screenshot to queue")
    print(f"    k + .   →  Send to Gemini")
    print(f"    k + /   →  Clear screenshot queue")
    print(f"    k + c   →  Clear memory + chat  (MAX_TURNS = {MAX_TURNS})")
    print(f"    k + t   →  Test overlay")
    print(f"    m + n   →  Toggle overlay")
    print(f"    🎤      →  Hold mic button to record, release to transcribe")
    print(f"    🔊      →  Click to toggle system audio (interviewer) listener\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()