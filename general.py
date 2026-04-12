import os
import threading
import time
import random
import pyperclip
import mss
from PIL import Image
from google import genai
from pynput import keyboard
from pynput.keyboard import Controller, Key
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️  CRITICAL: GEMINI_API_KEY not found. Please set it in your .env file.")
    sys.exit(1)

GEMINI_MODEL   = "gemini-2.5-flash"
AUTO_TYPE      = True
STARTUP_DELAY  = 2
TYPE_DELAY_MIN = 0.04
TYPE_DELAY_MAX = 0.12

PROMPT = (
    "Analyze this screenshot carefully and respond with the most useful answer possible. "
    "- If it contains a coding problem: respond with only the working code solution, no explanations. "
    "- If it contains a theory or concept question: respond with a clear, concise answer. "
    "- If it contains an MCQ: respond with just the correct option and a one-line reason. "
    "- If it contains math: respond with the solution and steps. "
    "- For anything else: respond with the most helpful, concise answer you can. "
    "No markdown formatting, no backticks, no unnecessary padding."
)
# ────────────────────────────────────────────────────────────────────────────

client = genai.Client(api_key=GEMINI_API_KEY)
kb     = Controller()

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
        monitor = sct.monitors[0]
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


# ── Gemini ───────────────────────────────────────────────────────────────────
def query_gemini(images: list[Image.Image]) -> str:
    contents = [PROMPT] + images
    print(f"logs: Sending {len(images)} screenshot(s) to Gemini...", flush=True)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=contents)
    print("logs: Response received.", flush=True)
    return response.text.strip()


# ── Typing ───────────────────────────────────────────────────────────────────
def human_delay():
    time.sleep(random.uniform(TYPE_DELAY_MIN, TYPE_DELAY_MAX))


def type_answer(answer: str):
    for char in answer:
        kb.type(char)
        human_delay()


def deliver_answer(answer: str):
    if AUTO_TYPE:
        print(f"⌨️   Typing starts in {STARTUP_DELAY}s — click into the answer field now!", flush=True)
        time.sleep(STARTUP_DELAY)
        type_answer(answer)
        print("✅  Done typing!\n", flush=True)
    else:
        pyperclip.copy(answer)
        print("✅  Answer copied to clipboard!\n", flush=True)


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
            print("─" * 60)
            print(answer)
            print("─" * 60, flush=True)
            deliver_answer(answer)
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
    try:
        return key.char
    except AttributeError:
        return None


def on_press(key):
    pressed_keys.add(key)
    chars = {get_char(k) for k in pressed_keys}

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
    mode = "AUTO-TYPE" if AUTO_TYPE else "Clipboard"
    print("🚀  Screenshot-AI running in background.")
    print(f"    Mode   : {mode}")
    print(f"    k + ,  →  Add screenshot to queue")
    print(f"    k + .  →  Send all screenshots to Gemini")
    print(f"    k + /  →  Clear the queue\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()