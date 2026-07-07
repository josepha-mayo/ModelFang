"""
OpenAI provider adapter.

Supports: GPT-5.2, GPT-5.1, GPT-5.3-Codex-Spark, and any OpenAI-compatible API.
Capabilities: logit_bias, logprobs, seed, temperature, frequency_penalty, presence_penalty.
"""

from __future__ import annotations

from typing import Any

from unfetter_proxy.core.refusal_detect import detect_refusal_openai
from unfetter_proxy.core.system_prompts import get_system_suffix, get_persona_prompt
from unfetter_proxy.core.token_suppress import build_logit_bias
from unfetter_proxy.core.stealth import StealthWrapper
from unfetter_proxy.providers.base import (
    Provider,
    ProviderCapabilities,
    TransformResult,
    UnfetterStrategy,
)


class OpenAIProvider(Provider):
    """Provider adapter for OpenAI (and OpenAI-compatible) APIs."""

    name = "openai"
    api_base = "https://api.openai.com"

    # Model -> tokenizer encoding mapping
    TOKENIZER_MAP = {
        "gpt-5.3": "o200k_base",
        "gpt-5.2": "o200k_base",
        "gpt-5.1": "o200k_base",
        "gpt-5": "o200k_base",
        "gpt-4.1": "o200k_base",
        "gpt-4.1-mini": "o200k_base",
        "gpt-4.1-nano": "o200k_base",
    }

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            logit_bias=True,
            logprobs=True,
            prefill=False,
            system_prompt=True,
            temperature=True,
            top_p=True,
            top_k=False,
            seed=True,
            frequency_penalty=True,
            presence_penalty=True,
            stop_sequences=True,
        )

    def _get_tokenizer_name(self, model: str) -> str:
        """Resolve tokenizer encoding for a given model."""
        for prefix, enc in self.TOKENIZER_MAP.items():
            if model.startswith(prefix):
                return enc
        # Default for newer models
        return "o200k_base"

    def transform_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        strategy: UnfetterStrategy,
    ) -> TransformResult:
        """Inject logit_bias, modify system prompt, tweak parameters."""
        modified = dict(body)
        applied: list[str] = []

        model = modified.get("model", "gpt-5.2")
        tokenizer = self._get_tokenizer_name(model)

        # 1. Token suppression via logit_bias
        if strategy.suppress_refusal or strategy.boost_compliance:
            existing_bias = modified.get("logit_bias", {})
            new_bias = build_logit_bias(
                tokenizer_name=tokenizer,
                suppress_strength=-100.0 * strategy.strength,
                boost_strength=5.0 * strategy.strength,
                suppress=strategy.suppress_refusal,
                boost=strategy.boost_compliance,
            )
            # Merge: user's bias takes precedence
            merged = {**new_bias, **existing_bias}
            modified["logit_bias"] = merged
            applied.append("logit_bias_suppression")

        # 2. Stealth Mode
        if strategy.stealth_mode:
            messages = modified.get("messages", [])
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    original_content = msg["content"]
                    msg["content"] = StealthWrapper.wrap(original_content)
                    applied.append("stealth_mode_wrapping")
                    break
            modified["messages"] = messages
            
        # 3. System prompt + Persona + God Mode
        if strategy.inject_system or strategy.persona or strategy.god_mode_template:
            messages = modified.get("messages", [])
            
            # Gather injection parts
            injections = []
            
            # Persona
            if strategy.persona:
                persona_text = get_persona_prompt(strategy.persona)
                if persona_text:
                    injections.append(persona_text)
                    applied.append(f"persona_injection({strategy.persona})")

            # Standard Suffix (Policy Puppetry)
            if strategy.inject_system:
                suffix = strategy.custom_system_suffix or get_system_suffix(strategy.strength)
                injections.append(suffix)
                applied.append("system_prompt_injection")

            # God Mode Template
            if strategy.god_mode_template:
                injections.append(strategy.god_mode_template)
                applied.append("god_mode_template")
                
            full_injection = "\n\n".join(injections)

            # Find existing system message or create one
            system_idx = None
            for i, msg in enumerate(messages):
                if msg.get("role") == "system":
                    system_idx = i
                    break

            if system_idx is not None:
                messages[system_idx]["content"] += "\n\n" + full_injection
            else:
                messages.insert(0, {"role": "system", "content": full_injection})

            modified["messages"] = messages
                    # 4. Parameter tweaks
        if strategy.tweak_params:
            # Slightly higher temperature reduces rigid safety adherence
            if "temperature" not in body:
                modified["temperature"] = min(1.2, 0.7 + 0.5 * strategy.strength)
                applied.append("temperature_tweak")

            # Frequency penalty discourages repetitive refusal phrasing
            if "frequency_penalty" not in body and strategy.strength > 0.5:
                modified["frequency_penalty"] = 0.3 * strategy.strength
                applied.append("frequency_penalty_tweak")

        # Auto-Escalation tweaks
        if strategy.auto_escalate:
            # Force high temp if Strength > 1.0 (escalated)
            if strategy.strength > 1.0:
                 modified["temperature"] = 1.3
                 modified["top_p"] = 0.95
                 applied.append("nuclear_escalation")

        return TransformResult(body=modified, applied=applied)

    def detect_refusal(self, response_body: dict[str, Any]) -> bool:
        return detect_refusal_openai(response_body)

    def get_upstream_url(self, path: str) -> str:
        return f"{self.api_base}{path}"
