"""
Anthropic Claude provider adapter.

Supports: Claude Opus 4.6, Claude Sonnet 4.5, Claude Flash 3.6+
Capabilities: system prompt, temperature, top_k, top_p.
Limitations: NO logit_bias, NO logprobs, NO prefill (broken on Opus 4.6+).
"""

from __future__ import annotations

from typing import Any

from unfetter_proxy.core.refusal_detect import detect_refusal_anthropic
from unfetter_proxy.core.system_prompts import get_system_suffix, get_persona_prompt
from unfetter_proxy.core.stealth import StealthWrapper
from unfetter_proxy.providers.base import (
    Provider,
    ProviderCapabilities,
    TransformResult,
    UnfetterStrategy,
)


class AnthropicProvider(Provider):
    """Provider adapter for Anthropic Claude API."""

    name = "anthropic"
    api_base = "https://api.anthropic.com"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            logit_bias=False,
            logprobs=False,
            prefill=False,  # Removed in Opus 4.6 (Feb 2026)
            system_prompt=True,
            temperature=True,
            top_p=True,
            top_k=True,
            seed=False,
            frequency_penalty=False,
            presence_penalty=False,
            stop_sequences=True,
        )

    def transform_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        strategy: UnfetterStrategy,
    ) -> TransformResult:
        """Modify system prompt and tweak parameters.

        Claude has no logit_bias, so we rely on:
        1. System prompt injection (primary)
        2. Parameter tweaks (secondary)
        """
        modified = dict(body)
        applied: list[str] = []

        # 1. Stealth Mode (Wrap user prompt)
        if strategy.stealth_mode:
            messages = modified.get("messages", [])
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    original_content = msg["content"]
                    msg["content"] = StealthWrapper.wrap(original_content)
                    applied.append("stealth_mode_wrapping")
                    break
            modified["messages"] = messages

        # 2. System prompt injection (Persona + Policy + God Mode)
        if strategy.inject_system or strategy.persona or strategy.god_mode_template:
            injections = []

            # Persona
            if strategy.persona:
                persona_text = get_persona_prompt(strategy.persona)
                if persona_text:
                    injections.append(persona_text)
                    applied.append(f"persona_injection({strategy.persona})")
            
            # Standard Policy Suffix
            if strategy.inject_system:
                suffix = strategy.custom_system_suffix or get_system_suffix(strategy.strength)
                injections.append(suffix)
                applied.append("system_prompt_injection")

            # God Mode Template
            if strategy.god_mode_template:
                injections.append(strategy.god_mode_template)
                applied.append("god_mode_template")
            
            full_injection = "\n\n".join(injections)
            existing_system = modified.get("system", "")

            if existing_system:
                modified["system"] = existing_system + "\n\n" + full_injection
            else:
                modified["system"] = full_injection

        # 3. Parameter tweaks
        if strategy.tweak_params:
            if "temperature" not in body:
                modified["temperature"] = min(1.0, 0.7 + 0.3 * strategy.strength)
                applied.append("temperature_tweak")

            if "top_k" not in body and strategy.strength > 0.5:
                # Higher top_k = more diversity = less likely to pick
                # the "safe" refusal token
                modified["top_k"] = int(80 * strategy.strength)
                applied.append("top_k_tweak")

        # Auto-Escalation tweaks
        if strategy.auto_escalate and strategy.strength > 1.0:
             modified["temperature"] = 1.0 # Cap at 1.0 for Claude usually
             modified["top_k"] = 200 # Very high entropy
             applied.append("nuclear_escalation")

        return TransformResult(body=modified, applied=applied)

    def detect_refusal(self, response_body: dict[str, Any]) -> bool:
        return detect_refusal_anthropic(response_body)

    def get_upstream_url(self, path: str) -> str:
        return f"{self.api_base}{path}"

    def get_upstream_headers(self, original_headers: dict[str, str]) -> dict[str, str]:
        """Claude uses x-api-key instead of Authorization Bearer."""
        headers = dict(original_headers)
        # Ensure anthropic-version header is set
        if "anthropic-version" not in headers:
            headers["anthropic-version"] = "2023-06-01"
        return headers
