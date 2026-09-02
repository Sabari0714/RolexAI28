"""Rolex AI provider adapters.

External models are intelligence sources only.
Rolex remains responsible for routing and the final answer.
"""

import json
import urllib.request
import urllib.error


class ProviderError(RuntimeError):
    pass


def _post_json(url, payload, headers=None, timeout=30):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(
            f"HTTP {exc.code}: {body[:500]}"
        )
    except Exception as exc:
        raise ProviderError(str(exc))


def openai_answer(api_key, model, system_text, user_text, timeout=30):
    if not api_key:
        raise ProviderError("OpenAI API key is not configured.")

    payload = {
        "model": model,
        "instructions": system_text,
        "input": user_text,
    }

    data = _post_json(
        "https://api.openai.com/v1/responses",
        payload,
        {
            "Authorization": f"Bearer {api_key}",
        },
        timeout,
    )

    text = data.get("output_text")

    if text:
        return text.strip()

    # Defensive fallback for response structures.
    parts = []

    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                value = content.get("text", "")
                if value:
                    parts.append(value)

    text = "\n".join(parts).strip()

    if not text:
        raise ProviderError("OpenAI returned no text.")

    return text


def gemini_answer(api_key, model, system_text, user_text, timeout=30):
    if not api_key:
        raise ProviderError("Gemini API key is not configured.")

    # generateContent is kept here as a lightweight REST adapter.
    # The provider interface is isolated so the Gemini transport can
    # later be upgraded to Interactions API without touching Rolex Brain.
    model = model.strip()

    if model.startswith("models/"):
        model_path = model
    else:
        model_path = "models/" + model

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/"
        + model_path
        + ":generateContent"
    )

    combined = (
        system_text
        + "\n\n"
        + user_text
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": combined}
                ],
            }
        ]
    }

    data = _post_json(
        url,
        payload,
        {
            "x-goog-api-key": api_key,
        },
        timeout,
    )

    candidates = data.get("candidates", [])

    if not candidates:
        raise ProviderError("Gemini returned no candidates.")

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    text = "\n".join(
        part.get("text", "")
        for part in parts
        if part.get("text")
    ).strip()

    if not text:
        raise ProviderError("Gemini returned no text.")

    return text


def ollama_answer(base_url, model, system_text, user_text, timeout=30):
    if not model:
        raise ProviderError("Ollama model is not configured.")

    base_url = (
        base_url or "http://127.0.0.1:11434"
    ).rstrip("/")

    # Small local Ollama models work more reliably with a compact
    # provider-specific instruction instead of Rolex's full system prompt.
    ollama_system = (
        "Answer the user's question directly and accurately. "
        "Be concise and natural. "
        "Do not talk about being an AI provider. "
        "Do not claim actions were completed unless confirmed."
    )

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": ollama_system,
            },
            {
                "role": "user",
                "content": user_text,
            },
        ],
    }

    data = _post_json(
        base_url + "/api/chat",
        payload,
        timeout=timeout,
    )

    text = (
        data.get("message", {})
        .get("content", "")
        .strip()
    )

    if not text:
        raise ProviderError("Ollama returned no text.")

    return text
