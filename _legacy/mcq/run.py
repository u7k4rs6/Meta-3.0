"""
run.py — Auto-restart launcher

Run this instead of main.py:
    python run.py

Watches all .py files in the folder. When you save any of them,
it kills the running process and starts it fresh automatically.
"""

import subprocess
import sys
import time
import os
from pathlib import Path

WATCH_DIR  = Path(__file__).parent
WATCH_EXT  = '.py'
MAIN_FILE  = WATCH_DIR / 'main.py'
CHECK_INTERVAL = 0.8   # seconds between file checks


def get_mtimes() -> dict:
    """Return a dict of {filepath: last_modified_time} for all .py files."""
    return {
        f: f.stat().st_mtime
        for f in WATCH_DIR.glob(f'*{WATCH_EXT}')
        if f.name != 'run.py'   # don't watch ourselves
    }


def start_process() -> subprocess.Popen:
    print(f"\n🚀  Starting main.py...\n{'─' * 50}", flush=True)
    return subprocess.Popen(
        [sys.executable, str(MAIN_FILE)],
        cwd=str(WATCH_DIR)
    )


def stop_process(proc: subprocess.Popen):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    print("👁️   Watcher active — watching all .py files for changes.")
    print(f"    Folder : {WATCH_DIR}")
    print(f"    Polling: every {CHECK_INTERVAL}s")
    print("    Save any .py file to auto-restart.\n")

    proc    = start_process()
    mtimes  = get_mtimes()

    try:
        while True:
            time.sleep(CHECK_INTERVAL)

            current = get_mtimes()
            changed = [
                f.name for f, t in current.items()
                if mtimes.get(f) != t
            ]

            if changed:
                print(f"\n🔄  Change detected in: {', '.join(changed)}", flush=True)
                print(f"    Restarting...\n{'─' * 50}", flush=True)
                stop_process(proc)
                time.sleep(0.3)   # brief pause so the OS releases ports/resources
                proc   = start_process()
                mtimes = current

            # If process crashed on its own, restart it
            elif proc.poll() is not None:
                print(f"\n💥  Process exited (code {proc.returncode}) — restarting...", flush=True)
                time.sleep(1)
                proc   = start_process()
                mtimes = get_mtimes()

    except KeyboardInterrupt:
        print("\n\n🛑  Watcher stopped.", flush=True)
        stop_process(proc)
        