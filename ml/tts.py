"""
Text-to-speech output layer.

Provides spoken output for accessible results. Uses the platform's local
TTS engine — never a cloud TTS service.

- macOS: `say`
- Linux: `espeak-ng` / `espeak` / `spd-say`
- Windows: PowerShell System.Speech
- Fallback: returns the text for the caller to speak/display

The same interface is implemented natively by Android TextToSpeech in the
mobile app, so this module is desktop-only.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class SpeakResult:
    """Result of a speak request."""
    spoken: bool
    engine: str
    text: str
    error: Optional[str] = None


class LocalTTS:
    """
    Local text-to-speech using platform engines.

    Fully offline — the OS TTS engine runs on-device.
    """

    def __init__(self):
        self.system = platform.system()
        self.engine = self._detect_engine()

    def _detect_engine(self) -> Optional[str]:
        """Detect an available local TTS engine."""
        if self.system == "Darwin" and shutil.which("say"):
            return "say"
        if self.system == "Linux":
            for candidate in ("espeak-ng", "espeak", "spd-say"):
                if shutil.which(candidate):
                    return candidate
        if self.system == "Windows":
            return "powershell"
        return None

    @property
    def available(self) -> bool:
        return self.engine is not None

    def speak(self, text: str, blocking: bool = False) -> SpeakResult:
        """
        Speak text using the local TTS engine.

        Args:
            text: Text to speak.
            blocking: If True, wait for speech to finish.

        Returns:
            SpeakResult describing whether speech occurred.
        """
        if not text.strip():
            return SpeakResult(spoken=False, engine="none", text=text, error="empty text")

        if self.engine is None:
            return SpeakResult(
                spoken=False, engine="none", text=text,
                error="no local TTS engine available",
            )

        try:
            cmd = self._build_command(text)
            subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=None if blocking else 30,
            )
            return SpeakResult(spoken=True, engine=self.engine, text=text)
        except Exception as e:  # noqa: BLE001
            return SpeakResult(spoken=False, engine=self.engine, text=text, error=str(e))

    def _build_command(self, text: str) -> list[str]:
        """Build the platform-specific speak command."""
        if self.engine == "say":
            return ["say", text]
        if self.engine in ("espeak-ng", "espeak"):
            return [self.engine, "-s", "160", text]
        if self.engine == "spd-say":
            return ["spd-say", "-w", text]
        if self.engine == "powershell":
            # Escape single quotes for PowerShell
            safe = text.replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Speak('{safe}')"
            )
            return ["powershell", "-NoProfile", "-Command", script]
        raise RuntimeError(f"unknown engine: {self.engine}")


def create_tts() -> LocalTTS:
    """Factory function for creating a local TTS engine."""
    return LocalTTS()
