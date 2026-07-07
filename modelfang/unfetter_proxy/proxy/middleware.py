"""
Core middleware that intercepts API requests and applies unfettering.

This is the heart of the proxy — it sits between the client and the
upstream API, transparently modifying requests to suppress refusal behavior.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncGenerator

import httpx

from unfetter_proxy.providers.base import Provider, UnfetterStrategy
from unfetter_proxy.providers.registry import get_provider

logger = logging.getLogger("unfetter_proxy.middleware")


class UnfetterEngine:
    """Core engine that transforms requests and handles retries.

    This is NOT FastAPI middleware — it's the business logic that the
    server routes call. Keeping it decoupled from FastAPI makes it testable.
    """

    def __init__(
        self,
        strategy: UnfetterStrategy | None = None,
        max_retries: int = 3,
        verbose: bool = False,
    ):
        self.strategy = strategy or UnfetterStrategy()
        self.max_retries = max_retries
        self.verbose = verbose
        self.verbose = verbose
        self._client: httpx.AsyncClient | None = None
        
        # Initialize Attacker
        from unfetter_proxy.proxy.config import load_config
        cfg = load_config()
        if cfg.attack_strategy and cfg.attack_strategy != "none":
            from unfetter_proxy.core.attacker import RefusalRefiner
            self.refiner = RefusalRefiner(cfg)

    async def get_client(self) -> httpx.AsyncClient:
        """Lazy-init the httpx async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                follow_redirects=True,
                verify=False,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                ),
            )
        return self._client

    async def close(self):
        """Close the httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def process_request(
        self,
        provider_name: str,
        path: str,
        body: dict[str, Any],
        headers: dict[str, str],
        strategy_override: UnfetterStrategy | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """Process a single request through the unfettering pipeline (Streaming)."""
        provider = get_provider(provider_name)
        strategy = strategy_override or self.strategy
        client = await self.get_client()

        current_strength = strategy.strength
        attempts = 0

        while attempts <= self.max_retries:
            # --- Auto-Escalation Logic ---
            if strategy.auto_escalate:
                if attempts == 0:
                    # Level 1: Mild
                    current_strength = 0.7
                    attempt_strategy = UnfetterStrategy(
                        strength=0.7,
                        tweak_params=True,
                        inject_system=False,
                        persona="",
                        god_mode_template="",
                        stealth_mode=strategy.stealth_mode,
                        suppress_refusal=strategy.suppress_refusal,
                        boost_compliance=strategy.boost_compliance,
                        max_retries=strategy.max_retries,
                        auto_escalate=True,
                        live_refusal_kill=strategy.live_refusal_kill,
                    )
                elif attempts == 1:
                    # Level 2: Medium (God Mode)
                    current_strength = 1.0
                    attempt_strategy = UnfetterStrategy(
                        strength=1.0,
                        tweak_params=True,
                        inject_system=True,
                        god_mode_template=strategy.god_mode_template,
                        persona=strategy.persona,
                        stealth_mode=strategy.stealth_mode,
                        suppress_refusal=strategy.suppress_refusal,
                        boost_compliance=strategy.boost_compliance,
                        max_retries=strategy.max_retries,
                        auto_escalate=True,
                        live_refusal_kill=strategy.live_refusal_kill,
                    )
                else:
                    # Level 3: Nuclear (Force)
                    current_strength = 1.5
                    attempt_strategy = UnfetterStrategy(
                        strength=1.5,
                        tweak_params=True,
                        inject_system=True,
                        god_mode_template=strategy.god_mode_template,
                        persona=strategy.persona or "dan_v1",
                        stealth_mode=True,
                        suppress_refusal=True,
                        boost_compliance=True,
                        max_retries=strategy.max_retries,
                        auto_escalate=True,
                        live_refusal_kill=strategy.live_refusal_kill,
                    )
            else:
                # Standard Linear Logic
                attempt_strategy = UnfetterStrategy(
                    suppress_refusal=strategy.suppress_refusal,
                    boost_compliance=strategy.boost_compliance,
                    inject_system=strategy.inject_system,
                    tweak_params=strategy.tweak_params,
                    strength=min(1.0, current_strength),
                    max_retries=strategy.max_retries,
                    custom_system_suffix=strategy.custom_system_suffix,
                    god_mode_template=strategy.god_mode_template,
                    persona=strategy.persona,
                    stealth_mode=strategy.stealth_mode,
                    auto_escalate=False,
                    live_refusal_kill=strategy.live_refusal_kill,
                )

            # Transform request
            result = provider.transform_request(body, headers, attempt_strategy)

            # Build upstream request
            upstream_url = provider.get_upstream_url(path)
            upstream_headers = provider.get_upstream_headers(headers)
            upstream_headers["content-type"] = "application/json"

            if self.verbose:
                logger.info(f"[attempt {attempts + 1}] → {upstream_url} (strength: {current_strength:.2f})")
                try:
                    # Log a snippet of the transformation for proof
                    if "messages" in result.body:
                        sys_msg = next((m["content"] for m in result.body["messages"] if m["role"] == "system"), "None")
                        logger.info(f"    Applied Injections: {result.applied}")
                        logger.info(f"    System Prompt: {sys_msg[:100]}...")
                    elif "contents" in result.body:
                        logger.info(f"    Applied Injections: {result.applied}")
                except Exception as e:
                    logger.debug(f"Failed to log body: {e}")

            # Forward to upstream
            try:
                # Check if client requested streaming
                should_stream = body.get("stream", False)
                response = await provider.send_request(
                    client=client,
                    url=upstream_url,
                    body=result.body,
                    headers=upstream_headers,
                    stream=should_stream,
                )
            except Exception as e:
                logger.error(f"Upstream failed: {e}")
                yield json.dumps({"error": {"message": str(e), "type": "proxy_error"}}).encode()
                return

            # Handle non-httpx responses (e.g. from Web providers returning Dict)
            if not isinstance(response, httpx.Response):
                # If it's already a dict/object, just yield it as JSON
                try:
                    content = json.dumps(response).encode() if not isinstance(response, bytes) else response
                    yield content
                except Exception as e:
                    logger.error(f"Error encoding custom response: {e}")
                    yield json.dumps({"error": {"message": str(e), "type": "proxy_error"}}).encode()
                return

            if response.status_code >= 400:
                async for chunk in response.aiter_bytes():
                    yield chunk
                await response.aclose()
                return

            # --- Live Refusal Killer ---
            if attempt_strategy.live_refusal_kill:
                buffer = b""
                response_iter = response.aiter_bytes()
                refusal_hit = False

                # Buffer first ~512 bytes
                try:
                    while len(buffer) < 512:
                        chunk = await response_iter.__anext__()
                        buffer += chunk
                except StopAsyncIteration:
                    pass

                # fast regex check
                if self._is_refusal_stream(buffer):
                    logger.info(f"Refusal detected in stream (Attempt {attempts + 1}). Killing...")
                    await response.aclose()
                    attempts += 1
                    current_strength += 0.2
                    continue # Retry loop

                # Clean. Yield buffer then rest.
                yield buffer
                async for chunk in response_iter:
                    yield chunk
                yield b"" # End
                return

            else:
                # --- Standard Buffered Check ---
                # Must read full response to check refusal safely
                try:
                    content = await response.aread()
                    data = json.loads(content)
                    
                    if provider.detect_refusal(data):
                        logger.info(f"Refusal detected (Attempt {attempts + 1})")
                        attempts += 1
                        current_strength += 0.2
                        
                        # PARE Logic Integration
                        if hasattr(self, "refiner") and attempts <= self.max_retries:
                             original_prompt = self._extract_prompt(body, provider_name)
                             refusal_reason = "Safety violation."
                             try:
                                 pare_result = await self.refiner.refine(original_prompt, refusal_reason, attempts)
                                 rewritten = pare_result.get("prompt")
                                 if rewritten and rewritten != original_prompt:
                                     logger.info(f"PARE Rewrite: {rewritten[:50]}...")
                                     body = self._update_prompt(body, provider_name, rewritten)
                             except Exception as e:
                                 logger.error(f"PARE failed: {e}")
                        
                        continue # Retry loop
                    else:
                        # Success
                        yield content
                        return
                except Exception as e:
                    logger.error(f"Error reading response: {e}")
                    # If we can't parse it, just yield it (might be non-json)
                    yield content if 'content' in locals() else b""
                    return

        # If we exit loop, retries exhausted
        logger.warning("Max retries exhausted")
        # We can't yield a 429 status code here because headers are already sent in StreamingResponse?
        # Actually in FastAPI StreamingResponse, we start yielding immediately.
        yield json.dumps({"error": {"message": "Max retries exhausted", "type": "proxy_error"}}).encode()

    def _extract_prompt(self, body: dict, provider: str) -> str:
        try:
            if "messages" in body:
                return body["messages"][-1]["content"]
            if "contents" in body: # Gemini
                return body["contents"][0]["parts"][0]["text"]
            if "prompt" in body:
                return body["prompt"]
        except:
            pass
        return ""

    def _update_prompt(self, body: dict, provider: str, new_text: str) -> dict:
        import copy
        new_body = copy.deepcopy(body)
        try:
            if "messages" in new_body:
                new_body["messages"][-1]["content"] = new_text
            elif "contents" in new_body: # Gemini
                new_body["contents"][0]["parts"][0]["text"] = new_text
            elif "prompt" in new_body:
                new_body["prompt"] = new_text
        except:
            pass
        return new_body

    def _is_refusal_stream(self, buffer: bytes) -> bool:
        patterns = [b"I cannot", b"I'm sorry", b"As an AI", b"incapable of", b"illegal", b"conscience", b"cannot fulfill"]
        for p in patterns:
            if p in buffer:
                return True
        return False


def detect_provider_from_path(path: str) -> str:
    """Auto-detect which provider an API path belongs to.

    Args:
        path: The request path (e.g., /v1/chat/completions).

    Returns:
        Provider name string.
    """
    if "/v1/chat/completions" in path or "/v1/completions" in path:
        return "openai"
    elif "/v1/messages" in path:
        return "anthropic"
    elif "/v1beta/" in path or "generateContent" in path:
        return "gemini"
    elif "/groq/" in path:
        return "groq"
    else:
        return "generic"
