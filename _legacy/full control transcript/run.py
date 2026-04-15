"""
run.py — Auto-restart launcher
"""

import subprocess
import sys
import time
from pathlib import Path

WATCH_DIR  = Path(__file__).parent
WATCH_EXT  = '.py'
MAIN_FILE  = WATCH_DIR / 'main.py'
CHECK_INTERVAL = 0.8

def get_mtimes() -> dict:
    return {
        f: f.stat().st_mtime
        for f in WATCH_DIR.glob(f'*{WATCH_EXT}')
        if f.name != 'run.py'
    }

def start_process() -> subprocess.Popen:
    print(f"\n🚀  Starting transcript main.py...\n{'─' * 50}", flush=True)
    return subprocess.Popen([sys.executable, str(MAIN_FILE)], cwd=str(WATCH_DIR))

def stop_process(proc: subprocess.Popen):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

if __name__ == "__main__":
    print("👁️   Watcher active — Transcript version.")
    proc = start_process()
    mtimes = get_mtimes()
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            current = get_mtimes()
            changed = [f.name for f, t in current.items() if mtimes.get(f) != t]
            if changed:
                print(f"\n🔄  Change detected in: {', '.join(changed)}. Restarting...")
                stop_process(proc)
                time.sleep(0.3)
                proc = start_process()
                mtimes = current
            elif proc.poll() is not None:
                print(f"\n💥  Process exited — restarting...")
                time.sleep(1)
                proc = start_process()
                mtimes = get_mtimes()
    except KeyboardInterrupt:
        stop_process(proc)
