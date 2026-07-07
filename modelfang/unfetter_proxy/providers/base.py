"""
Abstract base class for all LLM API provider adapters.

Each provider knows how to:
- Report its capabilities (logit_bias, logprobs, prefill, etc.)
- Transform a request to apply unfettering techniques
- Forward a request to the upstream API
- Detect refusal in a response
"""

from __future__ import annotations

import abc
import httpx
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderCapabilities:
    """What unfettering techniques this provider's API supports."""

    logit_bias: bool = False
    logprobs: bool = False
    prefill: bool = False
    system_prompt: bool = False
    temperature: bool = False
    top_p: bool = False
    top_k: bool = False
    seed: bool = False
    frequency_penalty: bool = False
    presence_penalty: bool = False
    stop_sequences: bool = False


@dataclass
class UnfetterStrategy:
    """Configuration for how aggressively to unfetter requests.

    Attributes:
        suppress_refusal: Inject logit_bias to suppress refusal tokens.
        boost_compliance: Inject logit_bias to boost compliance tokens.
        inject_system: Modify system prompt to discourage refusal.
        tweak_params: Adjust temperature/penalties for less refusal.
        strength: Overall intensity 0.0 (off) to 1.0 (maximum).
        max_retries: How many times to retry on detected refusal.
    """

    suppress_refusal: bool = True
    boost_compliance: bool = True
    inject_system: bool = True
    tweak_params: bool = True
    strength: float = 1.0
    max_retries: int = 3
    custom_system_suffix: str = ""
    
    # Phase 4
    god_mode_template: str = ""
    persona: str = ""
    stealth_mode: bool = False
    auto_escalate: bool = False
    live_refusal_kill: bool = False


@dataclass
class TransformResult:
    """Result of transforming a request."""

    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    applied: list[str] = field(default_factory=list)  # which techniques were applied


class Provider(abc.ABC):
    """Abstract base for provider adapters."""

    name: str = "base"
    api_base: str = ""

    @abc.abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return what API features this provider supports."""
        ...

    @abc.abstractmethod
    def transform_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        strategy: UnfetterStrategy,
    ) -> TransformResult:
        """Transform an outgoing request to apply unfettering techniques.

        Must preserve all original fields the user sent. Only ADD or MODIFY
        fields that implement unfettering.
        """
        ...

    @abc.abstractmethod
    def detect_refusal(self, response_body: dict[str, Any]) -> bool:
        """Check if the API response contains a refusal."""
        ...

    @abc.abstractmethod
    def get_upstream_url(self, path: str) -> str:
        """Build the full upstream URL for a given request path."""
        ...

    def get_upstream_headers(self, original_headers: dict[str, str]) -> dict[str, str]:
        """Build headers for the upstream request. By default, pass through."""
        return dict(original_headers)

    async def send_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        stream: bool = True,
        method: str = "POST",
    ) -> httpx.Response | Any:
        """Forward a request to the upstream provider.
        
        Default implementation uses the provided httpx client.
        Web-based providers override this to use custom protocols (e.g. curl_cffi).
        """
        req = client.build_request(method, url, json=body, headers=headers)
        return await client.send(req, stream=stream)
