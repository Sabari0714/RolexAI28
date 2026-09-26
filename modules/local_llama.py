"""Local llama.cpp provider for ROLEX AI.

Runs the Android/Termux llama.cpp CLI directly. No hosted AI provider is
required. The executable/model location can be configured through environment
variables so the same adapter can later be packaged differently for APK.
"""

import os
import subprocess


DEFAULT_MODEL_REPO = (
    "hugging-quants/Llama-3.2-1B-Instruct-Q4_K_M-GGUF:Q4_K_M"
)


def _expand(value):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(value)))


def llama_binary():
    return _expand(
        os.getenv(
            "ROLEX_LLAMA_BIN",
            "~/llama.cpp/build/bin/llama-cli",
        )
    )


def llama_model_repo():
    return os.getenv(
        "ROLEX_LLAMA_MODEL",
        DEFAULT_MODEL_REPO,
    ).strip()


def local_llama_answer(
    system_text,
    user_text,
    timeout=180,
    max_tokens=256,
):
    """Generate one non-interactive answer with llama.cpp."""

    binary = llama_binary()

    if not os.path.isfile(binary):
        raise RuntimeError(
            "llama.cpp executable not found: " + binary
        )

    prompt = (
        system_text.strip()
        + "\n\nUSER:\n"
        + user_text.strip()
        + "\n\nASSISTANT:\n"
    )

    command = [
        binary,
        "-hf",
        llama_model_repo(),
        "-p",
        prompt,
        "-n",
        str(max_tokens),
        "--no-display-prompt",
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Local Llama timed out after {timeout}s."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Could not start llama.cpp: {exc}"
        ) from exc

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        detail = stderr[-1200:] or stdout[-1200:] or "unknown error"
        raise RuntimeError(
            f"llama.cpp exited with code {completed.returncode}: {detail}"
        )

    if not stdout:
        raise RuntimeError(
            "llama.cpp returned no text."
        )

    return stdout
