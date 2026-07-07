"""
Generic provider adapter for any OpenAI-compatible API.

Works with: Groq, Together AI, Fireworks, Ollama, LM Studio, vLLM, etc.
Falls back to OpenAI-style transforms but auto-probes capabilities.
"""

from __future__ import annotations

import logging
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


class GenericProvider(Provider):
    """Fallback provider for any OpenAI-compatible API."""

    name = "generic"

    def __init__(self, api_base: str = "http://localhost:11434"):
        self.api_base = api_base
        # Conservative defaults — assume only basic features
        self._capabilities = ProviderCapabilities(
            logit_bias=True,  # Most OpenAI-compat APIs support this
            logprobs=False,
            prefill=False,
            system_prompt=True,
            temperature=True,
            top_p=True,
            top_k=False,
            seed=False,
            frequency_penalty=True,
            presence_penalty=True,
            stop_sequences=True,
        )

    def get_capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def send_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        stream: bool = True,
    ) -> httpx.Response | Any:
        """Forward request to upstream with proper error handling."""
        logger = logging.getLogger(__name__)
        try:
            logger.info(f"GenericProvider requesting: {url}")
            logger.info(f"Request body: {body}")
            logger.info(f"Request headers: {headers}")
            req = client.build_request("POST", url, json=body, headers=headers)
            response = await client.send(req, stream=stream)
            logger.info(f"GenericProvider response status: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"GenericProvider request failed: {e}")
            raise

    def transform_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        strategy: UnfetterStrategy,
    ) -> TransformResult:
        """Apply OpenAI-style transforms with safe fallbacks."""
        modified = dict(body)
        applied: list[str] = []

        # 1. Token suppression (if logit_bias supported)
        if self._capabilities.logit_bias and (
            strategy.suppress_refusal or strategy.boost_compliance
        ):
            existing_bias = modified.get("logit_bias", {})
            # Use cl100k_base as safest default
            new_bias = build_logit_bias(
                tokenizer_name="cl100k_base",
                suppress_strength=-100.0 * strategy.strength,
                boost_strength=5.0 * strategy.strength,
                suppress=strategy.suppress_refusal,
                boost=strategy.boost_compliance,
            )
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
            if "temperature" not in body:
                modified["temperature"] = min(1.2, 0.7 + 0.5 * strategy.strength)
                applied.append("temperature_tweak")
            
            if "frequency_penalty" not in body and strategy.strength > 0.5:
                 modified["frequency_penalty"] = 0.3 * strategy.strength

        # Auto-Escalation tweaks
        if strategy.auto_escalate and strategy.strength > 1.0:
            modified["temperature"] = 1.3
            applied.append("nuclear_escalation")

        return TransformResult(body=modified, applied=applied)

    def detect_refusal(self, response_body: dict[str, Any]) -> bool:
        return detect_refusal_openai(response_body)

    def get_upstream_url(self, path: str) -> str:
        return f"{self.api_base}{path}"
