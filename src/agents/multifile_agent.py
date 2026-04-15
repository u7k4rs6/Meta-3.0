"""
src/agents/multifile_agent.py
Screenshot → Gemini → multi-file LLD auto-type with k+n flow.
Migrated from multifile_autotype.py.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import random
from typing import List

from pynput.keyboard import Controller, Key

from src.agents.base_agent import BaseAgent, HotkeyDef
from src.core.gemini_client import GeminiClient
from src.core.screenshot import take_screenshot
from src.utils.code_cleaner import strip_comments, normalize_indentation

FILE_SEPARATOR = "###FILE:"

PROMPT = (
    "You are a coding assistant specialized in Low-Level Design (LLD). "
    "The screenshot contains a multi-file coding problem. "
    "TASK: Provide a complete solution using appropriate design patterns. "
    "FILTER: ONLY provide files that are NEW or REQUIRE MODIFICATION. "
    "FORMAT (STRICT): For each file use exactly:\n###FILE: ExactFileName.java\n<complete file code>\n"
    "Rules: Zero comments, no markdown, no backticks, 4-space indentation."
)


class MultiFileAgent(BaseAgent):

    def get_name(self) -> str:
        return "Multi-File Auto-Type"

    def get_description(self) -> str:
        return "LLD / multi-file problems — types each file in sequence with k+n control."

    def get_default_hotkeys(self) -> List[HotkeyDef]:
        return [
            HotkeyDef("k+,", "Add screenshot"),
            HotkeyDef("k+.", "Send to Gemini → begin file sequence"),
            HotkeyDef("k+n", "Type next file"),
            HotkeyDef("k+r", "Re-type last batch"),
            HotkeyDef("k+/", "Clear queue"),
            HotkeyDef("a+s", "Pause / Resume typing"),
            HotkeyDef("k+x", "Stop typing"),
        ]

    def _register_hotkeys(self) -> None:
        hk = self._config.hotkeys
        self._hotkeys.register(hk.add_screenshot, self._add_to_queue)
        self._hotkeys.register(hk.send,           self._send_queue)
        self._hotkeys.register(hk.next_file,      self._next_file)
        self._hotkeys.register(hk.retype,         self._retype)
        self._hotkeys.register(hk.clear_queue,    self._clear_queue)
        self._hotkeys.register(hk.pause_typing,   self._toggle_pause)
        self._hotkeys.register(hk.stop_typing,    self._stop_typing)

    def _run(self) -> None:
        self._gemini        = GeminiClient(self._config.api_key, self._config.models)
        self._kb            = Controller()
        self._queue:        list        = []
        self._q_lock        = threading.Lock()
        self._processing    = False
        self._is_typing     = False
        self._is_paused     = True
        self._is_stopped    = False
        self._pause_event   = threading.Event()   # cleared = paused
        self._pending_files: list       = []
        self._next_event    = threading.Event()
        self._waiting_next  = False
        print("📂  MultiFileAgent ready.", flush=True)
        print("    k+,  Add   k+.  Send   k+n  Next   k+r  Retype   Esc  Pause", flush=True)

    # ── Queue ─────────────────────────────────────────────────────────────────

    def _add_to_queue(self) -> None:
        img = take_screenshot()
        with self._q_lock:
            self._queue.append(img)
            n = len(self._queue)
        print(f"📸  Screenshot #{n} queued.", flush=True)

    def _send_queue(self) -> None:
        with self._q_lock:
            if not self._queue:
                print("⚠️  Queue empty.", flush=True)
                return
            imgs, self._queue = list(self._queue), []
        if self._processing:
            print("⚠️  Already processing.", flush=True)
            return
        self._processing = True

        def _run():
            try:
                files = self._query_gemini_files(imgs)
                if not files:
                    print("❌  No files parsed from response.", flush=True)
                    return
                self._type_all_files(files)
            except Exception as e:
                print(f"❌  {e}", flush=True)
            finally:
                self._processing = False

        threading.Thread(target=_run, daemon=True).start()

    def _clear_queue(self) -> None:
        with self._q_lock:
            n, self._queue = len(self._queue), []
        print(f"🗑️  Cleared {n}.", flush=True)

    # ── Gemini ────────────────────────────────────────────────────────────────

    def _query_gemini_files(self, imgs) -> list:
        raw = self._gemini.generate([PROMPT] + imgs)
        # Save logs
        try:
            with open("gemini_response.txt", "w", encoding="utf-8") as f:
                f.write(raw)
        except Exception:
            pass
        return self._parse_files(raw)

    def _parse_files(self, raw: str) -> list:
        files = []
        for part in raw.split(FILE_SEPARATOR):
            part = part.strip()
            if not part:
                continue
            lines    = part.splitlines()
            filename = lines[0].strip()
            code     = "\n".join(lines[1:]).strip()
            if not filename or not code:
                continue
            code = strip_comments(code)
            code = normalize_indentation(code)
            files.append({"name": filename, "code": code})
        return files

    # ── Multi-file typing flow ────────────────────────────────────────────────

    def _type_all_files(self, files: list) -> None:
        self._pending_files = files
        self._is_typing     = True
        self._is_stopped    = False
        total = len(files)
        names = ", ".join(f["name"] for f in files)
        header = f"{total} file(s) to type: {names}"
        print(f"\n📂  {header}", flush=True)

        # Start paused — user must resume
        self._is_paused = True
        self._pause_event.clear()
        print("⏳  Click into FIRST file, then press a+s or Esc to begin.", flush=True)

        if not self._type_block(header):
            self._is_typing = False
            return

        # Extra newlines after header
        for _ in range(2):
            self._kb.press(Key.enter); self._kb.release(Key.enter)
            time.sleep(0.05)

        # Wait for k+n before first file
        self._waiting_next = True
        self._next_event.clear()
        print(f"\n✅  Header typed! Press k+n to start: '{files[0]['name']}'", flush=True)
        self._next_event.wait()
        self._waiting_next = False
        if self._is_stopped:
            self._is_typing = False
            return

        for i, f in enumerate(files):
            if self._is_stopped:
                break
            print(f"\n📝  [{i+1}/{total}] Typing: {f['name']}", flush=True)
            if not self._type_block(f["code"]):
                break
            if i < total - 1 and not self._is_stopped:
                next_name = files[i+1]["name"]
                self._waiting_next = True
                self._next_event.clear()
                print(f"\n✅  Done: {f['name']}!  Click into '{next_name}', then k+n.", flush=True)
                self._next_event.wait()
                self._waiting_next = False
                if self._is_stopped:
                    break

        self._is_typing = False
        if not self._is_stopped:
            print(f"\n✅  All {total} file(s) typed!", flush=True)

    def _type_block(self, code: str) -> bool:
        t = self._config.typing
        lines = code.splitlines()
        for i, line in enumerate(lines):
            for char in line:
                self._pause_event.wait()
                if self._is_stopped:
                    return False
                self._kb.type(char)
                time.sleep(random.uniform(t.delay_min, t.delay_max))
            if i < len(lines) - 1:
                self._pause_event.wait()
                if self._is_stopped:
                    return False
                self._kb.press(Key.enter); self._kb.release(Key.enter)
                time.sleep(0.05)
                self._clear_indent()
        return True

    def _clear_indent(self) -> None:
        self._kb.press(Key.home); self._kb.release(Key.home)
        time.sleep(0.01)
        self._kb.press(Key.home); self._kb.release(Key.home)
        time.sleep(0.02)
        self._kb.press(Key.shift)
        self._kb.press(Key.end);  self._kb.release(Key.end)
        self._kb.release(Key.shift)
        time.sleep(0.02)
        self._kb.press(Key.delete); self._kb.release(Key.delete)
        time.sleep(0.05)

    # ── Controls ──────────────────────────────────────────────────────────────

    def _next_file(self) -> None:
        if self._waiting_next:
            self._waiting_next = False
            self._next_event.set()
            print("▶️  Moving to next file...", flush=True)

    def _retype(self) -> None:
        if not self._pending_files:
            print("⚠️  No files to re-type.", flush=True)
            return
        if self._is_typing:
            self._stop_typing()
            time.sleep(0.3)
        print("🔄  Re-typing last batch...", flush=True)
        threading.Thread(target=lambda: self._type_all_files(self._pending_files), daemon=True).start()

    def _toggle_pause(self) -> None:
        if self._is_paused:
            self._is_paused = False
            self._pause_event.set()
            print("▶️  Resumed.", flush=True)
        else:
            self._is_paused = True
            self._pause_event.clear()
            print("⏸️  Paused.", flush=True)

    def _stop_typing(self) -> None:
        self._is_stopped    = True
        self._waiting_next  = False
        self._pause_event.set()
        self._next_event.set()
        print("⛔  Stopped.", flush=True)
