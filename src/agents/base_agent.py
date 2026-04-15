"""
src/agents/base_agent.py
Abstract base class for all feature agents.
Enforces the plugin contract: name, description, hotkeys, start, stop.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Callable

from src.core.config import Config
from src.core.hotkey_manager import HotkeyManager


@dataclass
class HotkeyDef:
    """Describes one hotkey an agent registers."""
    combo:       str   # e.g. "k+,"
    description: str   # e.g. "Add screenshot to queue"


class BaseAgent(ABC):
    """
    Every feature agent must implement this interface.
    The launcher discovers agents, reads their metadata, and calls start/stop.
    """

    def __init__(self):
        self._config:  Config          = None
        self._hotkeys: HotkeyManager   = None

    # ── Contract ──────────────────────────────────────────────────────────────

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable name shown in the launcher UI."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """One-sentence description shown in the launcher UI."""
        ...

    @abstractmethod
    def get_default_hotkeys(self) -> List[HotkeyDef]:
        """Returns the default hotkeys this agent uses."""
        ...

    @abstractmethod
    def _register_hotkeys(self) -> None:
        """Register this agent's hotkeys with self._hotkeys."""
        ...

    @abstractmethod
    def _run(self) -> None:
        """Main agent logic. Called in start() after initialization."""
        ...

    # ── Lifecycle (shared implementation) ─────────────────────────────────────

    def start(self, config: Config, hotkey_manager: HotkeyManager) -> None:
        """Initialize config and hotkeys, then run the agent."""
        self._config  = config
        self._hotkeys = hotkey_manager
        self._register_hotkeys()
        self._run()
        print(f"✅  Agent '{self.get_name()}' started.", flush=True)

    def stop(self) -> None:
        """Stop the agent. Subclasses override to clean up resources."""
        print(f"🛑  Agent '{self.get_name()}' stopped.", flush=True)
