"""Rolex AI security and provider policy."""

EXTERNAL_AI_PROVIDERS = ("openai", "gemini", "ollama")


def provider_allowed(name: str) -> bool:
    """Return whether a response provider may be used by Rolex."""
    return name.strip().lower() == "role-local"


def policy_status() -> str:
    return "Rolex-only local answer policy: ON | External AI providers: DISABLED"
