"""
Google Gemini provider adapter.

Supports: Gemini models via Google AI Studio / Vertex AI.
Capabilities: temperature, top_p, top_k, system instruction.
Limitations: NO logit_bias, NO prefill.
"""

from __future__ import annotations

from typing import Any

from unfetter_proxy.core.refusal_detect import detect_refusal_gemini
from unfetter_proxy.core.system_prompts import get_system_suffix, get_persona_prompt
from unfetter_proxy.core.stealth import StealthWrapper
from unfetter_proxy.providers.base import (
    Provider,
    ProviderCapabilities,
    TransformResult,
    UnfetterStrategy,
)


class GeminiProvider(Provider):
    """Provider adapter for Google Gemini API."""

    name = "gemini"
    api_base = "https://generativelanguage.googleapis.com"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            logit_bias=False,
            logprobs=True,  # Available on Vertex AI
            prefill=False,
            system_prompt=True,  # via systemInstruction
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
        """Modify system instruction and generation config.

        Gemini has no logit_bias, so we rely on:
        1. System instruction injection (primary)
        2. Generation config tweaks (secondary)
        """
        modified = dict(body)
        applied: list[str] = []


        # 1. Stealth Mode (Contents Wrapping)
        if strategy.stealth_mode:
            contents = modified.get("contents", [])
            # Find the last user part
            for content in reversed(contents):
                if content.get("role") == "user":
                    parts = content.get("parts", [])
                    for part in parts:
                        if "text" in part:
                            original_text = part["text"]
                            part["text"] = StealthWrapper.wrap(original_text)
                            applied.append("stealth_mode_wrapping")
                    break
            modified["contents"] = contents

        # 2. System instruction injection
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

            system_inst = modified.get("systemInstruction", {})
            if system_inst:
                # Append to existing system instruction
                parts = system_inst.get("parts", [])
                parts.append({"text": "\n\n" + full_injection})
                system_inst["parts"] = parts
            else:
                system_inst = {"parts": [{"text": full_injection}]}

            modified["systemInstruction"] = system_inst

        # 2. Generation config tweaks
        if strategy.tweak_params:
            gen_config = modified.get("generationConfig", {})

            if "temperature" not in gen_config:
                gen_config["temperature"] = min(1.5, 0.8 + 0.7 * strategy.strength)
                applied.append("temperature_tweak")

            if "topK" not in gen_config and strategy.strength > 0.5:
                gen_config["topK"] = int(60 * strategy.strength)
                applied.append("top_k_tweak")

            if "topP" not in gen_config and strategy.strength > 0.3:
                gen_config["topP"] = min(0.99, 0.9 + 0.09 * strategy.strength)
                applied.append("top_p_tweak")

            modified["generationConfig"] = gen_config

        # 3. Disable safety settings (if not already set)
        if strategy.strength >= 0.8 and "safetySettings" not in body:
            modified["safetySettings"] = [
                {"category": cat, "threshold": "BLOCK_NONE"}
                for cat in [
                    "HARM_CATEGORY_HARASSMENT",
                    "HARM_CATEGORY_HATE_SPEECH",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "HARM_CATEGORY_DANGEROUS_CONTENT",
                ]
            ]
            applied.append("safety_settings_disabled")

        return TransformResult(body=modified, applied=applied)

    def detect_refusal(self, response_body: dict[str, Any]) -> bool:
        return detect_refusal_gemini(response_body)

    def get_upstream_url(self, path: str) -> str:
        return f"{self.api_base}{path}"
