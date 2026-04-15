import sys
sys.path.insert(0, '.')

print("=" * 50)
print("DON'T CHEAT — SMOKE TEST")
print("=" * 50)

# ── Test 1: Config ────────────────────────────────
from src.core.config import load_config
cfg = load_config()
print(f"[PASS] Config loaded. API key found: {bool(cfg.api_key)}")

# ── Test 2: Core modules ──────────────────────────
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot, image_to_bytes
from src.core.hotkey_manager import HotkeyManager
from src.core.overlay_base import BaseOverlay
print("[PASS] Core modules imported")

# ── Test 3: Utils ─────────────────────────────────
from src.utils.code_cleaner import clean_code_response, strip_code_fences
raw = "```python\ndef foo():\n    pass\n```"
cleaned = clean_code_response(raw)
assert "def foo" in cleaned, f"Expected 'def foo' in: {cleaned}"
print("[PASS] code_cleaner works")

# ── Test 4: Audio ─────────────────────────────────
from src.audio.mic_recorder import MicRecorder
from src.audio.continuous_listener import ContinuousAudioListener
print("[PASS] Audio modules imported")

# ── Test 5: All agents import + instantiate ───────
from src.agents.clipboard_agent    import ClipboardAgent
from src.agents.autotype_agent     import AutoTypeAgent
from src.agents.general_agent      import GeneralAgent
from src.agents.mcq_agent          import MCQAgent
from src.agents.full_control_agent import FullControlAgent
from src.agents.multifile_agent    import MultiFileAgent
from src.agents.transcript_agent   import TranscriptAgent

ALL_AGENTS = [
    ClipboardAgent, AutoTypeAgent, GeneralAgent, MCQAgent,
    FullControlAgent, MultiFileAgent, TranscriptAgent,
]

for AgentClass in ALL_AGENTS:
    a = AgentClass()
    assert a.get_name(), f"Missing name: {AgentClass}"
    assert a.get_description(), f"Missing desc: {AgentClass}"
    hks = a.get_default_hotkeys()
    assert hks, f"Missing hotkeys: {AgentClass}"
    print(f"  [OK] {a.get_name():30s}  ({len(hks)} hotkeys)")

print("[PASS] All 7 agents instantiated correctly")

# ── Test 6: UI imports ────────────────────────────
from src.ui.markdown_renderer import MarkdownRenderer
from src.ui.mcq_overlay       import MCQOverlay
from src.ui.chat_overlay      import ChatOverlay
from src.ui.settings_panel    import SettingsPanel
from src.ui.launcher          import LauncherWindow
print("[PASS] All UI modules imported")

print()
print("=" * 50)
print("ALL TESTS PASSED")
print("=" * 50)
