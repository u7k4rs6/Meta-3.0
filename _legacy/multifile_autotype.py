import os
import threading
import time
import random
import re
import mss
from PIL import Image
from google import genai
from pynput import keyboard
from pynput.keyboard import Controller, Key
import sys
from dotenv import load_dotenv
import json

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️  GEMINI_API_KEY not found.")
    sys.exit(1)

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]

TYPE_DELAY_MIN = 0.05
TYPE_DELAY_MAX = 0.10

FILE_SEPARATOR = "###FILE:"   # Gemini uses this to separate files

PROMPT = (
    "You are a coding assistant specialized in Low-Level Design (LLD). "
    "The screenshot contains a multi-file coding problem. "
    "TASK: Provide a complete LLD solution using appropriate design patterns (Builder, Factory, etc.). "
    "FILTER RULES (VERY IMPORTANT): "
    "1. ONLY provide files that are NEW or REQUIRE MODIFICATION. "
    "2. DO NOT return files that are already correct or provided as boilerplate if they don't need changes. "
    "3. I will be PENALIZED if you include unchanged files. "
    "FORMATTING RULES: "
    "1. Format your response EXACTLY like this for each file: "
    "###FILE: ExactFileName.java "
    "<complete file code here> "
    "2. Output the COMPLETE file content for each file — not just the changed parts. "
    "3. Zero comments of any kind — no #, no //, no /* */, no docstrings. "
    "4. No markdown, no backticks, no code fences, no explanations. "
    "5. Use exactly 4 spaces per indent level — no tabs. "
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
KEY_NEXT   = 'n'   # k + n → type next file
KEY_STOP   = 'x'   # k + x → abort everything
KEY_RETYPE = 'r'   # k + r → re-type last batch

# ── Typing state ─────────────────────────────────────────────────────────────
is_typing    = False
is_paused    = True
is_stopped   = False
pause_event  = threading.Event()
pause_event.clear()

# ── Multi-file state ──────────────────────────────────────────────────────────
pending_files: list[dict] = []    # [{"name": "Foo.java", "code": "..."}]
current_file_index = 0
waiting_for_next   = False        # True when paused between files
next_file_event    = threading.Event()


def pause_typing():
    global is_paused
    is_paused = True
    pause_event.clear()
    print("⏸️   Paused. Press Esc or a+s to resume, k+x to stop.", flush=True)


def resume_typing():
    global is_paused
    is_paused = False
    pause_event.set()
    print("▶️   Resumed.", flush=True)


def stop_typing():
    global is_stopped, waiting_for_next
    if not is_typing and not waiting_for_next:
        return
    is_stopped     = True
    waiting_for_next = False
    pause_event.set()
    next_file_event.set()
    print("⛔  Stopped. Ready for new commands.", flush=True)


def toggle_pause():
    if is_paused:
        resume_typing()
    else:
        pause_typing()


def trigger_next_file():
    """Called when user presses k+n to advance to the next file."""
    global waiting_for_next
    if waiting_for_next:
        waiting_for_next = False
        next_file_event.set()
        print("▶️   Moving to next file...", flush=True)


# ── Screenshot ───────────────────────────────────────────────────────────────
def take_screenshot() -> Image.Image:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[0])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


# ── Post-processing ──────────────────────────────────────────────────────────
def strip_comments(code: str) -> str:
    clean_lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('#'):
            continue
        if stripped.startswith('*') or stripped.startswith('/*') or stripped == '*/':
            continue
        line = re.sub(r'\s*//(?![\'"])[^\n]*', '', line)
        line = re.sub(r'(?<![\'"\w])#[^\n]*', '', line)
        clean_lines.append(line.rstrip())
    return "\n".join(l for l in clean_lines if l.strip() != '' or l == '')


def normalize_indentation(code: str) -> str:
    lines = []
    for line in code.splitlines():
        line = line.replace('\t', '    ')
        stripped     = line.lstrip(' ')
        raw_spaces   = len(line) - len(stripped)
        indent_level = round(raw_spaces / 4)
        lines.append('    ' * indent_level + stripped)
    return "\n".join(lines)


def parse_files(raw: str) -> list[dict]:
    """
    Parse Gemini response into a list of {name, code} dicts.
    Splits on ###FILE: markers.
    """
    files   = []
    parts   = raw.split(FILE_SEPARATOR)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # First line is the filename, rest is code
        lines    = part.splitlines()
        filename = lines[0].strip()
        code     = "\n".join(lines[1:]).strip()

        if not filename or not code:
            continue

        code = strip_comments(code)
        code = normalize_indentation(code)
        files.append({"name": filename, "code": code})

    return files


# ── Gemini with fallback ──────────────────────────────────────────────────────
def query_gemini(images: list[Image.Image]) -> list[dict]:
    contents   = [PROMPT] + images
    last_error = None

    for model in GEMINI_MODELS:
        try:
            print(f"logs: Trying {model}...", flush=True)
            response = client.models.generate_content(model=model, contents=contents)
            print(f"logs: ✅ Response from {model}", flush=True)
            
            # Save raw and structured response
            try:
                raw_text = response.text
                with open("gemini_response.txt", "w", encoding="utf-8") as f1:
                    f1.write(raw_text)
                    f1.flush()
                    os.fsync(f1.fileno())
                
                log_data = {
                    "timestamp": time.ctime(),
                    "model": model,
                    "files": parse_files(raw_text)
                }
                with open("last_gemini_response.json", "w", encoding="utf-8") as f2:
                    json.dump(log_data, f2, indent=4)
                    f2.flush()
                    os.fsync(f2.fileno())
                print(f"logs: Response saved to gemini_response.txt and last_gemini_response.json", flush=True)
            except Exception as e:
                print(f"logs: ⚠️  Failed to save logs: {e}", flush=True)

            files = parse_files(response.text)
            if not files:
                print(f"logs: ⚠️  Could not parse files from response.", flush=True)
                print(response.text[:500], flush=True)
            return files
        except Exception as e:
            print(f"logs: ⚠️  {model} failed — {e}", flush=True)
            last_error = e

    raise RuntimeError(f"All models failed: {last_error}")


# ── Typing ───────────────────────────────────────────────────────────────────
def human_delay():
    time.sleep(random.uniform(TYPE_DELAY_MIN, TYPE_DELAY_MAX))


def wait_if_paused() -> bool:
    pause_event.wait()
    return not is_stopped


def clear_auto_indent():
    """Removes any auto-indentation added by the editor by clearing the current line."""
    # Press Home twice to ensure we're at column 0 (some editors toggle on first Home)
    kb.press(Key.home);    kb.release(Key.home)
    time.sleep(0.01)
    kb.press(Key.home);    kb.release(Key.home)
    time.sleep(0.02)
    kb.press(Key.shift)
    kb.press(Key.end);     kb.release(Key.end)
    kb.release(Key.shift)
    time.sleep(0.02)
    kb.press(Key.delete);  kb.release(Key.delete)
    time.sleep(0.05)   # Slightly longer wait for editor stability


def type_block(code: str):
    """Type code line by line, clearing auto-indentation after each Enter."""
    lines = code.splitlines()
    for i, line in enumerate(lines):
        for char in line:
            if not wait_if_paused():
                return False
            kb.type(char)
            human_delay()

        if i < len(lines) - 1:
            if not wait_if_paused():
                return False
            kb.press(Key.enter); kb.release(Key.enter)
            time.sleep(0.05)
            clear_auto_indent()
    return True


# ── Multi-file typing flow ────────────────────────────────────────────────────
def type_all_files(files: list[dict]):
    global is_typing, is_stopped, waiting_for_next, current_file_index, pending_files

    pending_files      = files    # Save for re-typing if needed
    is_typing          = True
    is_stopped         = False
    current_file_index = 0

    total = len(files)
    file_names = ", ".join(f["name"] for f in files)
    header_str = f"{total} file(s) to type: {file_names}"

    print(f"\n📂  {header_str}", flush=True)

    pause_typing()
    print(f"\n⏳  Click into the FIRST file now, then press Esc or a+s to start typing!", flush=True)
    print(f"    (The file list will be typed first, then the code.)", flush=True)
    print(f"    k+n=next file  |  k+x=stop\n", flush=True)

    # Type the summary header first
    if not type_block(header_str):
        is_typing = False
        return
    
    # Add a couple of trailing enters manually to separate from header
    kb.press(Key.enter); kb.release(Key.enter)
    time.sleep(0.05)
    kb.press(Key.enter); kb.release(Key.enter)
    time.sleep(0.05)

    # Wait for k+n before typing the first file
    waiting_for_next = True
    next_file_event.clear()
    print(f"\n✅  Header typed!", flush=True)
    print(f"    👉  Press  k+n  to start typing the first file: '{files[0]['name']}'", flush=True)
    next_file_event.wait()
    waiting_for_next = False

    if is_stopped:
        is_typing = False
        return

    for i, file in enumerate(files):
        if is_stopped:
            break

        current_file_index = i
        print(f"\n📝  [{i+1}/{total}] Typing: {file['name']}", flush=True)

        success = type_block(file['code'])

        if not success or is_stopped:
            break

        # If there's a next file, pause and wait for user to click into it
        if i < total - 1:
            next_name = files[i + 1]['name']
            waiting_for_next = True
            next_file_event.clear()

            print(f"\n✅  Done with {file['name']}!", flush=True)
            print(f"    👉  Click into  '{next_name}'  then press  k+n  to continue.", flush=True)

            next_file_event.wait()   # blocks here until k+n or k+x

            if is_stopped:
                break

    is_typing = False

    if not is_stopped:
        print(f"\n✅  All {total} file(s) typed successfully!\n", flush=True)


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
        print("⚠️   Already processing.", flush=True)
        return
    processing = True

    def run():
        global processing
        try:
            print(f"\n🤖  Sending {len(images_to_send)} screenshot(s) to Gemini...", flush=True)
            files = query_gemini(images_to_send)

            if not files:
                print("❌  No files parsed from response.", flush=True)
                return

            type_all_files(files)

        except Exception as e:
            print(f"❌  Error: {e}", flush=True)
        finally:
            processing = False

    threading.Thread(target=run, daemon=True).start()


def clear_queue():
    with queue_lock:
        count = len(screenshot_queue)
        screenshot_queue.clear()
    print(f"🗑️   Queue cleared ({count}).", flush=True)


def retype_last_batch():
    global is_typing, processing, is_stopped
    if processing:
        print("⚠️   Cannot re-type while Gemini is processing.", flush=True)
        return
        
    if is_typing:
        print("🛑  Stopping current session to restart...", flush=True)
        stop_typing()
        # Wait briefly for thread to exit
        for _ in range(10):
            if not is_typing:
                break
            time.sleep(0.1)

    if not pending_files:
        print("⚠️   No files to re-type in memory.", flush=True)
        return
    
    print("\n🔄  Re-starting last batch...", flush=True)
    threading.Thread(target=lambda: type_all_files(pending_files), daemon=True).start()


# ── Keyboard listener ─────────────────────────────────────────────────────────
def get_char(key):
    try:
        return key.char
    except AttributeError:
        return None


def on_press(key):
    if key == Key.esc:
        toggle_pause()
        return

    pressed_keys.add(key)
    chars = {get_char(k) for k in pressed_keys}
    lower = {c.lower() for c in chars if c}

    # Pause/Resume with a + s
    if {'a', 's'}.issubset(lower):
        pressed_keys.clear()
        toggle_pause()
        return

    if KEY_ANCHOR in lower:
        if KEY_STOP in lower:       # k + x → stop
            pressed_keys.clear()
            stop_typing()
        elif KEY_NEXT in lower:     # k + n → next file
            pressed_keys.clear()
            trigger_next_file()
        elif KEY_ADD in chars:      # k + , → add screenshot
            pressed_keys.clear()
            add_to_queue()
        elif KEY_SEND in chars:     # k + . → send to Gemini
            pressed_keys.clear()
            send_queue()
        elif KEY_CLEAR in chars:    # k + / → clear queue
            pressed_keys.clear()
            clear_queue()
        elif KEY_RETYPE in lower:   # k + r → re-type
            print("debug: k+r detected", flush=True)
            pressed_keys.clear()
            retype_last_batch()


def on_release(key):
    pressed_keys.discard(key)


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀  Multi-File Auto-Type running.")
    print(f"    k + ,  →  Add screenshot to queue")
    print(f"    k + .  →  Send to Gemini → type all files")
    print(f"    k + n  →  Move to next file (after current file is done)")
    print(f"    k + /  →  Clear queue")
    print(f"    k + r  →  Re-type last batch (if finished or stopped)")
    print(f"    Esc    →  Pause / Resume typing")
    print(f"    a + s  →  Pause / Resume typing")
    print(f"    k + x  →  Stop typing immediately\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
