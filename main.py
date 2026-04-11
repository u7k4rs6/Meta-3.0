import os
import threading
import pyperclip
import mss
from PIL import Image
from google import genai
from pynput import keyboard
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️  CRITICAL: GEMINI_API_KEY not found. Please set it in your .env file.")
    sys.exit(1)

GEMINI_MODEL = "gemini-2.5-flash"

PROMPT = (
    "You are a coding assistant. The screenshots contain a coding problem or question. "
    "Analyze all the provided screenshots together as one combined context. "
    "Respond with ONLY the code solution — no explanations, no markdown fences (no ```), "
    "no comments unless they are absolutely essential, and no preamble. "
    "Just raw, clean, working code that can be pasted directly into an editor."
)
# ────────────────────────────────────────────────────────────────────────────

client = genai.Client(api_key=GEMINI_API_KEY)

screenshot_queue: list[Image.Image] = []
queue_lock   = threading.Lock()
processing   = False
pressed_keys = set()

# ── Hotkey definitions ───────────────────────────────────────────────────────
# All combos use 'k' as the anchor key
KEY_ANCHOR = 'k'
KEY_ADD    = ','   # k + , → add screenshot
KEY_SEND   = '.'   # k + . → send queue
KEY_CLEAR  = '/'   # k + / → clear queue


# ── Screenshot helpers ───────────────────────────────────────────────────────
def take_screenshot() -> Image.Image:
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def strip_code_fences(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


# ── Gemini call ──────────────────────────────────────────────────────────────
def query_gemini(images: list[Image.Image]) -> str:
    contents = [PROMPT] + images
    print(f"logs: Sending {len(images)} screenshot(s) to Gemini...", flush=True)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=contents)
    print("logs: Response received.", flush=True)
    return strip_code_fences(response.text.strip())


# ── Hotkey actions ───────────────────────────────────────────────────────────
def add_to_queue():
    img = take_screenshot()
    with queue_lock:
        screenshot_queue.append(img)
        count = len(screenshot_queue)
    print(f"📸  Screenshot #{count} added to queue.  (k+. to send | k+/ to clear)", flush=True)


def send_queue():
    global processing

    with queue_lock:
        if not screenshot_queue:
            print("⚠️   Queue is empty — nothing to send.", flush=True)
            return
        images_to_send = list(screenshot_queue)
        screenshot_queue.clear()

    if processing:
        print("⚠️   Already processing, please wait.", flush=True)
        return
    processing = True

    def run():
        global processing
        try:
            print(f"\n🤖  Sending {len(images_to_send)} screenshot(s) to Gemini...", flush=True)
            answer = query_gemini(images_to_send)
            pyperclip.copy(answer)
            print("✅  Code copied to clipboard!\n", flush=True)
            print("─" * 60)
            print(answer)
            print("─" * 60, flush=True)
        except Exception as e:
            print(f"❌  Error: {e}", flush=True)
        finally:
            processing = False

    threading.Thread(target=run, daemon=True).start()


def clear_queue():
    with queue_lock:
        count = len(screenshot_queue)
        screenshot_queue.clear()
    print(f"🗑️   Queue cleared ({count} screenshot(s) removed).", flush=True)


# ── Keyboard listener ────────────────────────────────────────────────────────
def get_char(key) -> str | None:
    """Safely extract the character from a key event."""
    try:
        return key.char
    except AttributeError:
        return None


def on_press(key):
    pressed_keys.add(key)

    chars = {get_char(k) for k in pressed_keys}   # set of all held characters

    if KEY_ANCHOR in chars:
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
    try:
        pressed_keys.remove(key)
    except KeyError:
        pass


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀  Screenshot-AI running in background.")
    print(f"    k + ,  →  Add screenshot to queue")
    print(f"    k + .  →  Send all screenshots to Gemini")
    print(f"    k + /  →  Clear the queue\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()