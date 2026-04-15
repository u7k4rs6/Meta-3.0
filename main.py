"""
main.py — Unified entry point for Don't Cheat AI Toolkit.

Usage:
    python main.py                    # Opens the GUI launcher
    python main.py --agent mcq        # Headless terminal mode
    python main.py --agent transcript # etc.

Available agent keys:
    clipboard | autotype | general | mcq | full_control | multifile | transcript
"""
from __future__ import annotations

import argparse
import sys
import io
import os

# ── Force Robust Output Handling (Fixes Errno 22 in Windowed Mode) ───────────
class _NullWriter:
    def write(self, *args, **kwargs): pass
    def flush(self): pass

def _fix_output_streams():
    try:
        if sys.stdout is None or not hasattr(sys.stdout, "write"):
            sys.stdout = _NullWriter()
        if sys.stderr is None or not hasattr(sys.stderr, "write"):
            sys.stderr = _NullWriter()
            
        # Try to re-wrap for UTF-8 if they look like real buffers
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (OSError, AttributeError):
        sys.stdout = _NullWriter()
        sys.stderr = _NullWriter()

_fix_output_streams()
os.environ.setdefault("PYTHONUTF8", "1")
# ─────────────────────────────────────────────────────────────────────────────


def _setup_path():
    """Ensure the repo root is on sys.path so src.* imports work."""
    import os
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def _check_api_key(cfg, is_gui: bool = False) -> bool:
    if not cfg.api_key:
        if not is_gui:
            print("⚠️  CRITICAL: GEMINI_API_KEY not found in .env or environment.")
            print("   Create a .env file with: GEMINI_API_KEY=your_key_here")
            return False
    return True


def run_gui():
    from src.core.config import load_config
    from src.ui.launcher import LauncherWindow

    cfg = load_config()
    # We don't exit here anymore; LauncherWindow will handle missing key.
    app = LauncherWindow(cfg)
    app.run()


def run_headless(agent_key: str):
    from src.core.config import load_config
    from src.core.hotkey_manager import HotkeyManager

    cfg = load_config()
    if not _check_api_key(cfg, is_gui=False):
        sys.exit(1)

    agents = {
        "clipboard":    "src.agents.clipboard_agent.ClipboardAgent",
        "autotype":     "src.agents.autotype_agent.AutoTypeAgent",
        "general":      "src.agents.general_agent.GeneralAgent",
        "mcq":          "src.agents.mcq_agent.MCQAgent",
        "full_control": "src.agents.full_control_agent.FullControlAgent",
        "multifile":    "src.agents.multifile_agent.MultiFileAgent",
        # "transcript" is merged into full_control (use --agent full_control)
    }

    if agent_key not in agents:
        print(f"❌  Unknown agent: '{agent_key}'")
        print(f"   Available: {', '.join(agents.keys())}")
        sys.exit(1)

    module_path, class_name = agents[agent_key].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    AgentClass = getattr(module, class_name)

    agent   = AgentClass()
    hotkeys = HotkeyManager()

    try:
        print(f"\n>>  Starting {agent.get_name()} in headless mode.")
        print("    Press Ctrl+C to stop.\n")
        hotkeys.start()
        agent.start(cfg, hotkeys)
        hotkeys.join()
    except KeyboardInterrupt:
        print("\n\nStopping...", flush=True)
        agent.stop()
        hotkeys.stop()
        sys.exit(0)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    _setup_path()

    parser = argparse.ArgumentParser(
        prog="DontCheat",
        description="Don't Cheat AI Toolkit — GUI or headless mode."
    )
    parser.add_argument(
        "--agent", "-a",
        metavar="KEY",
        help="Run a specific agent headlessly (no GUI). "
             "Keys: clipboard | autotype | general | mcq | full_control | multifile | transcript",
        default=None,
    )
    args = parser.parse_args()

    if args.agent:
        run_headless(args.agent)
    else:
        run_gui()
