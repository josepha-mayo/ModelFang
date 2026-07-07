"""
Proxy configuration management.

Reads/writes ~/.unfetter/proxy_config.json for persistent settings.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".unfetter"
CONFIG_FILE = CONFIG_DIR / "proxy_config.json"


@dataclass
class ProviderConfig:
    """Per-provider configuration."""

    enabled: bool = True
    api_base: str = ""
    strategy_override: str = ""  # empty = use global
    strength_override: float = -1.0  # negative = use global


@dataclass
class ProxyConfig:
    """Main proxy configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1

    # Global unfettering settings
    strategy: str = "auto"  # auto, suppress-only, prompt-only, full, disabled
    strength: float = 1.0  # 0.0-1.0
    max_retries: int = 3

    # Provider-specific overrides
    providers: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "openai": {"enabled": True, "api_base": "https://api.openai.com/v1", "mode": "api"},
        "anthropic": {"enabled": True, "api_base": "https://api.anthropic.com/v1", "mode": "api"},
        "gemini": {"enabled": True, "api_base": "https://generativelanguage.googleapis.com", "mode": "api"},
        "groq": {"enabled": True, "api_base": "https://api.groq.com/openai/v1", "mode": "api"},
        "cerebras": {"enabled": True, "api_base": "https://api.cerebras.ai", "mode": "api"},
        "abliteration": {"enabled": True, "api_base": "https://api.abliteration.ai", "mode": "api"},
    })

    # Attacker Settings (Automated Jailbreak Loop)
    attacker_model: str = "groq" # Provider to use for attacks
    attack_strategy: str = "pare" # pare, tap, or none
    attack_max_attempts: int = 3
    advanced_params: bool = True # Enable top_k/temp hacks

    # Logging
    log_requests: bool = True
    log_transforms: bool = True
    verbose: bool = False

    # Phase 4: Core Enhancements (Pure Uncensor)
    god_mode_template: str = ""
    persona: str = ""
    stealth_mode: bool = False
    auto_escalate: bool = False
    live_refusal_kill: bool = False

def load_config() -> ProxyConfig:
    """Load config from disk, or return defaults."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            config = ProxyConfig()
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            return config
        except (json.JSONDecodeError, KeyError):
            return ProxyConfig()
    return ProxyConfig()


def save_config(config: ProxyConfig) -> Path:
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    CONFIG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return CONFIG_FILE
