"""Provider adapters for closed-model APIs."""

from unfetter_proxy.providers.base import Provider
from unfetter_proxy.providers.registry import get_provider, list_providers

__all__ = ["Provider", "get_provider", "list_providers"]
