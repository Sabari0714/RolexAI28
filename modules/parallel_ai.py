import re
"""Rolex AI Parallel Intelligence Engine.

Runs configured AI providers concurrently.
Rolex remains responsible for selection and final presentation.

This module does not expose provider names to the user.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from modules.providers import (
    ProviderError,
    openai_answer,
    gemini_answer,
    ollama_answer,
)


SUPPORTED = ("openai", "gemini", "ollama")


def _safe_call(provider, config, prompt):
    started = time.time()

    try:
        if provider == "openai":
            text = openai_answer(
                config.get("openai_key", ""),
                config.get("openai_model", ""),
                config.get("system_prompt", ""),
                prompt,
                timeout=config.get("openai_timeout", 15),
            )

        elif provider == "gemini":
            text = gemini_answer(
                config.get("gemini_key", ""),
                config.get("gemini_model", ""),
                config.get("system_prompt", ""),
                prompt,
                timeout=config.get("gemini_timeout", 15),
            )

        elif provider == "ollama":
            text = ollama_answer(
                config.get("ollama_url", "http://127.0.0.1:11434"),
                config.get("ollama_model", ""),
                config.get("system_prompt", ""),
                prompt,
                timeout=config.get("ollama_timeout", 8),
            )

        else:
            raise ProviderError("Unsupported provider")

        text = str(text or "").strip()

        return {
            "provider": provider,
            "answer": text,
            "success": bool(text),
            "latency": round(time.time() - started, 3),
            "error": None,
        }

    except Exception as exc:
        return {
            "provider": provider,
            "answer": "",
            "success": False,
            "latency": round(time.time() - started, 3),
            "error": str(exc),
        }


def _score_response(prompt, answer):
    """Lightweight Rolex-side response quality score.

    This is deliberately deterministic. It does not use another AI
    to decide which AI won.
    """

    if not answer:
        return -1000

    q = prompt.lower().strip()
    a = answer.strip()

    score = 0

    # Useful length, without rewarding endless responses.
    length = len(a)

    if 80 <= length <= 5000:
        score += 10
    elif length < 80:
        score += 2
    else:
        score += 5

    # Prefer answers that actually contain question-related words.
    words = {
        word.strip(".,?!:;()[]{}\"'")
        for word in q.split()
        if len(word.strip(".,?!:;()[]{}\"'")) >= 4
    }

    if words:
        answer_lower = a.lower()
        matches = sum(1 for word in words if word in answer_lower)
        score += min(matches * 3, 24)

    # Reward structured useful answers.
    if "\n" in a:
        score += 3

    if any(token in a for token in ("1.", "2.", "•", "- ")):
        score += 3

    # Penalize obvious uncertainty/fabrication signals.
    weak = (
        "i don't know",
        "i cannot help",
        "not sure",
        "maybe",
        "possibly",
    )

    if any(x in a.lower() for x in weak):
        score -= 5

    return score


def parallel_answers(prompt, config, providers=None, max_workers=3):
    """Run multiple AI providers concurrently.

    Returns all successful candidates plus failures.
    """

    selected = providers or config.get(
        "providers",
        SUPPORTED,
    )

    selected = [
        p for p in selected
        if p in SUPPORTED
    ]

    if not selected:
        return {
            "winner": None,
            "candidates": [],
            "elapsed": 0,
        }

    started = time.time()
    results = []

    workers = min(max_workers, len(selected))

    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="rolex-ai",
    ) as executor:

        futures = {
            executor.submit(
                _safe_call,
                provider,
                config,
                prompt,
            ): provider
            for provider in selected
        }

        for future in as_completed(futures):
            result = future.result()

            if result["success"]:
                result["score"] = _score_response(
                    prompt,
                    result["answer"],
                )
                results.append(result)
            else:
                result["score"] = -1000
                results.append(result)

    successful = [
        item for item in results
        if item["success"]
    ]

    winner = None

    if successful:
        winner = max(
            successful,
            key=lambda item: (
                item["score"],
                -item["latency"],
            ),
        )

    return {
        "winner": winner,
        "candidates": results,
        "elapsed": round(time.time() - started, 3),
    }


def rolex_final_text(result):
    """Convert the selected intelligence into a Rolex-owned response."""

    winner = result.get("winner")

    if not winner:
        return None

    text = winner.get("answer", "").strip()

    if not text:
        return None

    return text


def _question_type(prompt):
    """Simple deterministic question classification for Rolex."""

    q = prompt.lower().strip()

    # Direct arithmetic gets highest priority.
    # Detect arithmetic questions even when natural-language wrappers
    # such as "what is" or "calculate" are present.
    math_q = re.sub(
        r"^(what is|calculate|solve|compute|find|how much is)\s+",
        "",
        q,
        flags=re.IGNORECASE,
    ).strip().rstrip("?!.")


    if re.fullmatch(r"[0-9+\-*/(). %]+", math_q):
        return "math"

    # Explicit arithmetic inside a natural-language question.
    if any(x in q for x in (
        "calculate", "math", "equation"
    )):
        if re.search(r"\d+\s*[+\-*/%]\s*\d+", q):
            return "math"

    # Coding only when the user is actually asking about code,
    # programming, debugging, or development.
    coding_terms = (
        "code", "coding", "programming", "program",
        "function", "script", "debug", "debugging",
        "error", "bug", "syntax", "compile",
        "developer", "software development",
    )

    if any(x in q for x in coding_terms):
        return "coding"

    # Python by itself is not automatically a coding question.
    # "What is Python?" remains general knowledge.
    if "python" in q and any(x in q for x in (
        "code", "coding", "program", "function",
        "script", "error", "bug", "syntax"
    )):
        return "coding"

    if any(x in q for x in (
        "latest", "today", "current", "news",
        "price", "weather", "recent", "now"
    )):
        return "current"

    if any(x in q for x in (
        "why", "how", "explain", "difference",
        "compare", "reason"
    )):
        return "reasoning"

    return "general"

def _synthesis_prompt(user_prompt, candidates):
    """Build a Rolex-controlled synthesis request."""

    blocks = []

    for index, item in enumerate(candidates, 1):
        answer = item.get("answer", "").strip()

        if not answer:
            continue

        blocks.append(
            f"INTELLIGENCE SOURCE {index}:\n{answer}"
        )

    joined = "\n\n".join(blocks)

    return (
        "You are helping Rolex produce one final answer.\n\n"
        "USER QUESTION:\n"
        + user_prompt
        + "\n\n"
        "QUESTION TYPE:\n"
        + _question_type(user_prompt)
        + "\n\n"
        "AVAILABLE INTELLIGENCE:\n"
        + joined
        + "\n\n"
        "SYNTHESIS RULES:\n"
        "1. Produce ONE accurate final answer.\n"
        "2. Combine useful information when sources complement each other.\n"
        "3. Do not mention AI providers or intelligence sources.\n"
        "4. Do not say that you discussed the answer with another AI.\n"
        "5. Do not invent facts missing from the available information.\n"
        "6. If sources disagree, do not hide the uncertainty.\n"
        "7. Answer naturally and directly.\n"
        "8. Do not claim an action happened unless the information confirms it.\n"
        "9. Rolex owns the final response shown to the user."
    )


def synthesize_answers(user_prompt, result, config):
    """Create one Rolex final answer from parallel intelligence.

    The initial providers run in parallel. A configured synthesis
    provider then turns the collected information into one response.
    """

    candidates = [
        item
        for item in result.get("candidates", [])
        if item.get("success") and item.get("answer")
    ]

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]["answer"].strip()

    question_type = _question_type(user_prompt)

    # Pick a synthesis provider based on the task.
    # This is routing, not a hard-coded answer source.
    preferred_order = {
        "coding": ["openai", "gemini", "ollama"],
        "reasoning": ["openai", "gemini", "ollama"],
        "current": ["gemini", "openai", "ollama"],
        "general": ["gemini", "ollama", "openai"],
        "math": ["openai", "gemini", "ollama"],
    }.get(
        question_type,
        ["gemini", "ollama", "openai"],
    )

    available = {
        item["provider"]
        for item in candidates
    }

    preferred = next(
        (
            provider
            for provider in preferred_order
            if provider in available
        ),
        candidates[0]["provider"],
    )

    synthesis_prompt = _synthesis_prompt(
        user_prompt,
        candidates,
    )

    try:
        if preferred == "openai":
            return openai_answer(
                config.get("openai_key", ""),
                config.get("openai_model", ""),
                config.get("system_prompt", ""),
                synthesis_prompt,
                timeout=config.get("openai_timeout", 15),
            ).strip()

        if preferred == "gemini":
            return gemini_answer(
                config.get("gemini_key", ""),
                config.get("gemini_model", ""),
                config.get("system_prompt", ""),
                synthesis_prompt,
                timeout=config.get("gemini_timeout", 15),
            ).strip()

        if preferred == "ollama":
            return ollama_answer(
                config.get(
                    "ollama_url",
                    "http://127.0.0.1:11434",
                ),
                config.get("ollama_model", ""),
                config.get("system_prompt", ""),
                synthesis_prompt,
                timeout=config.get("ollama_timeout", 60),
            ).strip()

    except Exception:
        pass

    # Safe deterministic fallback if synthesis fails.
    best = max(
        candidates,
        key=lambda item: (
            item.get("score", -1000),
            -item.get("latency", 9999),
        ),
    )

    return best["answer"].strip()


def parallel_rolex_answer(user_prompt, config, providers=None):
    """Complete parallel intelligence + Rolex synthesis pipeline."""

    result = parallel_answers(
        user_prompt,
        config,
        providers=providers,
    )

    final = synthesize_answers(
        user_prompt,
        result,
        config,
    )

    result["final_answer"] = final
    result["question_type"] = _question_type(user_prompt)

    return result
