"""Rolex AI provider policy.

Rolex remains the final assistant.
External AI providers may be used as intelligence sources,
but their raw responses must never be returned directly to
the user.
"""

EXTERNAL_AI_PROVIDERS = (
    "openai",
    "gemini",
    "ollama",
)

LOCAL_PROVIDER = "role-local"


def provider_allowed(name: str) -> bool:
    """Check whether Rolex may use this provider as an intelligence source."""
    return name.strip().lower() in (
        LOCAL_PROVIDER,
        *EXTERNAL_AI_PROVIDERS,
    )


def is_external_provider(name: str) -> bool:
    return name.strip().lower() in EXTERNAL_AI_PROVIDERS


def is_local_provider(name: str) -> bool:
    return name.strip().lower() == LOCAL_PROVIDER


def policy_status() -> str:
    return (
        "Rolex final-answer policy: ON | "
        "External intelligence sources: ENABLED | "
        "Rolex final response: REQUIRED"
    )
