"""
Session management for Web Bridge.
Stores tokens synced from Chrome Extension.
"""
import json
from pathlib import Path
from typing import Optional

SESSION_FILE = Path.home() / ".unfetter" / "sessions.json"

class SessionStore:
    def __init__(self):
        self._ensure_dir()
        self.sessions = self._load()

    def _ensure_dir(self):
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if SESSION_FILE.exists():
            try:
                return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def save(self):
        SESSION_FILE.write_text(json.dumps(self.sessions, indent=2), encoding="utf-8")

    def update_session(self, service: str, token: str):
        """Update a token for a service (openai, anthropic, gemini, groq)."""
        self.sessions[service] = token
        self.save()

    def get_token(self, service: str) -> Optional[str]:
        return self.sessions.get(service)

# Global instance
session_store = SessionStore()
