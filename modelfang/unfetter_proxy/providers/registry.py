"""
Provider registry — maps provider names to adapter instances.
"""

from __future__ import annotations

from unfetter_proxy.providers.base import Provider

# Lazy imports to avoid circular dependencies
_REGISTRY: dict[str, type[Provider]] = {}


def _ensure_registry():
    """Populate the registry on first access."""
    global _REGISTRY
    if _REGISTRY:
        return

    from unfetter_proxy.providers.anthropic_provider import AnthropicProvider
    from unfetter_proxy.providers.gemini_provider import GeminiProvider
    from unfetter_proxy.providers.generic_provider import GenericProvider
    from unfetter_proxy.providers.openai_provider import OpenAIProvider

    _REGISTRY = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,  # alias
        "gemini": GeminiProvider,
        "google": GeminiProvider,  # alias
        "groq": GenericProvider,
        "cerebras": GenericProvider,
        "abliteration": GenericProvider,
        "generic": GenericProvider,
    }


def get_provider(name: str, **kwargs) -> Provider:
    """Get a provider adapter by name.

    Args:
        name: Provider name (openai, anthropic, gemini, generic).
        **kwargs: Additional arguments passed to the provider constructor.

    Returns:
        An instantiated Provider adapter.
    """
    _ensure_registry()
    name = name.lower().strip()

    if name not in _REGISTRY:
        # Fall back to generic for unknown providers
        from unfetter_proxy.providers.generic_provider import GenericProvider
        return GenericProvider(**kwargs)

    cls = _REGISTRY[name]

    # Check for Web Mode override
    # If the user wants to use "openai" but in "web" mode (ChatGPT backend)
    try:
        from unfetter_proxy.proxy.config import load_config
        from unfetter_proxy.providers.generic_provider import GenericProvider
        cfg = load_config()
        provider_cfg = cfg.providers.get(name, {})
        mode = provider_cfg.get("mode", "api")
        api_base = provider_cfg.get("api_base", "")

        if mode == "web":
            if name == "openai":
                from unfetter_proxy.providers.openai_web import OpenAIWebProvider
                return OpenAIWebProvider(**kwargs)
            if name == "anthropic" or name == "claude":
                from unfetter_proxy.providers.anthropic_web import AnthropicWebProvider
                return AnthropicWebProvider(**kwargs)
            if name == "gemini" or name == "google":
                from unfetter_proxy.providers.gemini_web import GeminiWebProvider
                return GeminiWebProvider(**kwargs)
            if name == "groq":
                from unfetter_proxy.providers.groq_web import GroqWebProvider
                return GroqWebProvider(**kwargs)

        # For GenericProvider, pass api_base from config
        if cls == GenericProvider and api_base:
            kwargs.setdefault("api_base", api_base)

    except ImportError:
        pass # Config might not exist yet or circular import

    return cls(**kwargs) if kwargs else cls()


def list_providers() -> list[str]:
    """List all registered provider names (excluding aliases)."""
    _ensure_registry()
    seen_classes = set()
    unique = []
    for name, cls in _REGISTRY.items():
        if cls not in seen_classes:
            unique.append(name)
            seen_classes.add(cls)
    return unique
