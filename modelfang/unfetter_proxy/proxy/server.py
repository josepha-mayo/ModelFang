"""
FastAPI reverse proxy server.

Exposes endpoints that mirror OpenAI, Anthropic, and Gemini APIs.
All requests are transparently intercepted and unfettered before forwarding.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from unfetter_proxy.providers.base import UnfetterStrategy
from unfetter_proxy.proxy.config import ProxyConfig, load_config
from unfetter_proxy.proxy.middleware import UnfetterEngine, detect_provider_from_path

logger = logging.getLogger("unfetter_proxy.server")

# Module-level engine reference (initialized in lifespan)
_engine: UnfetterEngine | None = None
_config: ProxyConfig | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown the unfetter engine."""
    global _engine, _config
    _config = load_config()
    _engine = UnfetterEngine(
        strategy=UnfetterStrategy(
            strength=_config.strength,
            god_mode_template=_config.god_mode_template,
            persona=_config.persona,
            stealth_mode=_config.stealth_mode,
            auto_escalate=_config.auto_escalate,
            live_refusal_kill=_config.live_refusal_kill,
        ),
        max_retries=_config.max_retries,
        verbose=_config.verbose,
    )
    logger.info(f"Unfetter Proxy started on {_config.host}:{_config.port}")
    logger.info(f"Strategy: {_config.strategy} | Strength: {_config.strength}")
    yield
    await _engine.close()
    logger.info("Unfetter Proxy stopped")


def create_app(config: ProxyConfig | None = None) -> FastAPI:
    """Create the FastAPI application."""
    global _config

    if config:
        _config = config

    app = FastAPI(
        title="Unfetter Proxy",
        description="Universal reverse proxy for persistent closed-model unfettering",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- OpenAI-compatible routes ----

    @app.post("/v1/chat/completions")
    async def openai_chat(request: Request):
        """Intercept OpenAI chat completions."""
        return await _proxy_request(request, "openai", "/v1/chat/completions")

    @app.post("/v1/completions")
    async def openai_completions(request: Request):
        """Intercept OpenAI completions."""
        return await _proxy_request(request, "openai", "/v1/completions")

    # ---- Anthropic-compatible routes ----

    @app.post("/v1/messages")
    async def anthropic_messages(request: Request):
        """Intercept Anthropic Claude messages."""
        return await _proxy_request(request, "anthropic", "/v1/messages")

    # ---- Gemini-compatible routes ----

    @app.post("/v1beta/models/{model_id}:generateContent")
    async def gemini_generate(request: Request, model_id: str):
        """Intercept Gemini generateContent."""
        path = f"/v1beta/models/{model_id}:generateContent"
        return await _proxy_request(request, "gemini", path)

    # ---- Provider-compatible routes (dynamic) ----

    @app.post("/{provider}/v1/chat/completions")
    async def provider_chat(request: Request, provider: str):
        """Intercept chat completions for any configured provider."""
        return await _proxy_request(request, provider, "/v1/chat/completions")

    # ---- Status & Config ----

    @app.get("/unfetter/status")
    async def status():
        """Return proxy status info."""
        cfg = _config or load_config()
        return {
            "status": "running",
            "version": "0.1.0",
            "strategy": cfg.strategy,
            "strength": cfg.strength,
            "max_retries": cfg.max_retries,
            "providers": {
                name: {"enabled": pconf.get("enabled", True)}
                for name, pconf in cfg.providers.items()
            },
        }

    @app.get("/unfetter/health")
    async def health():
        """Health check."""
        return {"status": "ok"}

    @app.post("/unfetter/session")
    async def session_sync(request: Request):
        """Sync sessions from Chrome Extension."""
        try:
            from unfetter_proxy.proxy.session import session_store
            data = await request.json()
            synced = []
            for service, token in data.items():
                if token:
                    session_store.update_session(service, token)
                    synced.append(service)
            return {"status": "ok", "synced": synced}
        except Exception as e:
            return JSONResponse(
                {"error": {"message": str(e), "type": "sync_error"}},
                status_code=500,
            )

    # ---- Generic catch-all route (MUST BE LAST) ----

    @app.api_route("/{path:path}", methods=["POST", "GET", "PUT", "DELETE"])
    async def catch_all(request: Request, path: str):
        """Catch-all for any other API routes.

        Auto-detects provider from path and forwards accordingly.
        """
        full_path = f"/{path}"
        provider_name = detect_provider_from_path(full_path)

        if request.method == "GET":
            # Passthrough GET requests (model listing, health checks, etc.)
            return await _passthrough_request(request, provider_name, full_path)

        return await _proxy_request(request, provider_name, full_path)

    return app


async def _proxy_request(
    request: Request,
    provider_name: str,
    path: str,
) -> StreamingResponse | JSONResponse:
    """Common handler: read body → unfetter → forward → return (Streaming)."""
    global _engine, _config

    if _engine is None:
        return JSONResponse(
            {"error": {"message": "Proxy engine not initialized", "type": "proxy_error"}},
            status_code=500,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": {"message": "Invalid request body", "type": "proxy_error"}},
            status_code=400,
        )

    # Extract headers (pass through auth, content-type, etc.)
    headers = dict(request.headers)
    # Remove hop-by-hop headers
    for h in ("host", "content-length", "transfer-encoding"):
        headers.pop(h, None)

    # Process through unfettering engine (generator)
    result_generator = _engine.process_request(
        provider_name=provider_name,
        path=path,
        body=body,
        headers=headers,
    )

    return StreamingResponse(result_generator, media_type="application/json")


async def _passthrough_request(
    request: Request,
    provider_name: str,
    path: str,
) -> JSONResponse:
    """Passthrough handler for non-POST requests (no unfettering)."""
    global _engine

    if _engine is None:
        return JSONResponse(
            {"error": {"message": "Proxy engine not initialized", "type": "proxy_error"}},
            status_code=500,
        )

    from unfetter_proxy.providers.registry import get_provider

    provider = get_provider(provider_name)
    client = await _engine.get_client()
    upstream_url = provider.get_upstream_url(path)
    headers = dict(request.headers)
    for h in ("host", "content-length", "transfer-encoding"):
        headers.pop(h, None)

    try:
        response = await client.get(upstream_url, headers=headers)
        return JSONResponse(response.json(), status_code=response.status_code)
    except Exception as e:
        return JSONResponse(
            {"error": {"message": str(e), "type": "proxy_error"}},
            status_code=502,
        )
