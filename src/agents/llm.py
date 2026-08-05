"""Local Ollama LLM configuration, tuned for an 8GB RAM machine.

A small model (wizardlm2:7b), a short context window (4096 tokens), and a
capped response length keep this usable on modest CPU-only hardware. No
API key is needed since the model runs entirely on localhost.
"""

from typing import Optional

import requests
from crewai import LLM

MODEL = "ollama/wizardlm2:7b"
OLLAMA_MODEL_NAME = "wizardlm2:7b"  # as shown by `ollama list`
BASE_URL = "http://localhost:11434"
NUM_CTX = 4096
MAX_RESPONSE_TOKENS = 800
REQUEST_TIMEOUT = 5


def build_llm() -> LLM:
    return LLM(
        model=MODEL,
        base_url=BASE_URL,
        temperature=0.2,
        max_tokens=MAX_RESPONSE_TOKENS,
        extra_body={"options": {"num_ctx": NUM_CTX}},
    )


def check_ollama_ready() -> Optional[str]:
    """Return None if Ollama is reachable and the model is installed.

    Otherwise, return a plain-English, actionable error message.
    """
    try:
        response = requests.get(f"{BASE_URL}/api/tags", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        return (
            f"Could not reach Ollama at {BASE_URL}.\n"
            "  Start it with: ollama serve\n"
            "  (or open the Ollama desktop app), then try again."
        )

    installed = {m.get("name") for m in response.json().get("models", [])}
    if OLLAMA_MODEL_NAME not in installed:
        return (
            f"Ollama is running, but the model '{OLLAMA_MODEL_NAME}' is not installed.\n"
            f"  Pull it with: ollama pull {OLLAMA_MODEL_NAME}\n"
            "  then try again."
        )

    return None
