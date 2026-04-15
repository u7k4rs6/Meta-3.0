import os
import threading
import mss
from PIL import Image
from google import genai
from pynput import keyboard
import sys
from dotenv import load_dotenv
from mcq_overlay import MCQOverlay

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️  GEMINI_API_KEY not found.")
    sys.exit(1)

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro"
]

PROMPT = (
    "Extract the correct option letter(s) (A, B, C, D, etc.) from the MCQ images. "
    "If options are not labeled, assign them letters A, B, C, D... consecutively. "
    "If multiple answers are potentially correct for one question, return them as a comma-separated list. "
    "If there are multiple distinct questions in the screenshot, separate the answers for each question with a pipe character (|). "
    "Order answers by confidence. Response must contain ONLY option characters, commas, and pipes — no words or explanations."
)
# ────────────────────────────────────────────────────────────────────────────

client   = genai.Client(api_key=GEMINI_API_KEY)
overlay  = MCQOverlay()

screenshot_queue: list[Image.Image] = []
queue_lock   = threading.Lock()
processing   = False
pressed_keys = set()

KEY_ANCHOR = 'k'
KEY_ADD    = ','
KEY_SEND   = '.'
KEY_CLEAR  = '/'


# ── Screenshot ───────────────────────────────────────────────────────────────
def take_screenshot() -> Image.Image:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[0])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


# ── Gemini with fallback ──────────────────────────────────────────────────────
def query_gemini(images: list[Image.Image]) -> str:
    contents   = [PROMPT] + images
    last_error = None

    for model in GEMINI_MODELS:
        try:
            print(f"logs: Trying {model}...", flush=True)
            response = client.models.generate_content(model=model, contents=contents)
            answer   = response.text.strip()
            
            # Post-processing: Extract option letters, commas, and pipes
            import re
            valid_parts = re.findall(r'[A-Ga-g,| ]', answer)
            if valid_parts:
                answer = "".join(valid_parts).upper()
            else:
                # Fallback: take first letter found if no valid pattern
                match = re.search(r'[a-zA-Z]', answer)
                if match:
                    answer = match.group(0).upper()

            print(f"logs: ✅ {model} → {answer}", flush=True)
            return answer
        except Exception as e:
            print(f"logs: ⚠️  {model} failed — {e}", flush=True)
            last_error = e

    raise RuntimeError(f"All models failed: {last_error}")


# ── Hotkey actions ───────────────────────────────────────────────────────────
def add_to_queue():
    img = take_screenshot()
    with queue_lock:
        screenshot_queue.append(img)
        count = len(screenshot_queue)
    print(f"📸  Screenshot #{count} queued.", flush=True)


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
            overlay.set_thinking()
            answer = query_gemini(images_to_send)
            overlay.set_answer(answer)
        except Exception as e:
            overlay.set_error()
            print(f"❌  {e}", flush=True)
        finally:
            processing = False

    threading.Thread(target=run, daemon=True).start()


def clear_queue():
    with queue_lock:
        count = len(screenshot_queue)
        screenshot_queue.clear()
    print(f"🗑️   Queue cleared ({count}).", flush=True)


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

    # m + n → toggle overlay
    if 'm' in lower and 'n' in lower:
        pressed_keys.clear()
        overlay.toggle()
        return

    if KEY_ANCHOR in lower:
        if KEY_ADD in chars:
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

    print("🚀  MCQ-AI running.")
    print(f"    k + ,  →  Add screenshot to queue")
    print(f"    k + .  →  Send to Gemini → answer on overlay")
    print(f"    k + /  →  Clear queue")
    print(f"    m + n  →  Hide / show overlay\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
