"""
Ollama Local Fallback Module

Used as a fallback when any external API fails due to:
  - Rate Limit (429)
  - Timeout
  - Server Error (500, 503)

Local model: qwen3 (8b) via Ollama
"""

import ollama
from typing import List, Dict

OLLAMA_MODEL = "qwen3"


def call_ollama(messages: List[Dict], model: str = OLLAMA_MODEL) -> str:
    """Call local Ollama model when external API is unavailable."""
    print(f"[FALLBACK] Switching to local Ollama model: {model}")
    try:
        response = ollama.chat(
            model=model,
            messages=messages,
            options={"temperature": 0.1, "num_predict": 2048},
        )
        content = response["message"]["content"]
        print(f"[FALLBACK] Ollama responded successfully ({len(content)} chars)")
        return content
    except Exception as e:
        print(f"[FALLBACK ERROR] Ollama call failed: {e}")
        raise RuntimeError(f"Local Ollama fallback also failed: {e}") from e


def should_fallback_openrouter(exception: Exception) -> bool:
    """Return True if the OpenRouter error warrants switching to local model."""
    try:
        import openai
        if isinstance(exception, openai.RateLimitError):
            print("[FALLBACK] Reason: OpenRouter rate limit (429)")
            return True
        if isinstance(exception, openai.APITimeoutError):
            print("[FALLBACK] Reason: OpenRouter timeout")
            return True
        if isinstance(exception, openai.APIStatusError) and exception.status_code in (429, 500, 503):
            print(f"[FALLBACK] Reason: OpenRouter HTTP {exception.status_code}")
            return True
        if isinstance(exception, openai.APIConnectionError):
            print("[FALLBACK] Reason: OpenRouter connection error")
            return True
    except ImportError:
        pass

    keywords = ["rate limit", "too many requests", "429", "timeout", "timed out",
                "service unavailable", "503", "internal server error", "500",
                "connection error", "connection refused"]
    if any(kw in str(exception).lower() for kw in keywords):
        print(f"[FALLBACK] Reason: keyword match – {str(exception)[:100]}")
        return True

    return False


def should_fallback_gemini(exception: Exception) -> bool:
    """Return True if the Gemini error warrants switching to local model."""
    try:
        from google.api_core import exceptions as gexc
        if isinstance(exception, (
            gexc.ResourceExhausted,
            gexc.ServiceUnavailable,
            gexc.DeadlineExceeded,
            gexc.InternalServerError,
        )):
            print(f"[FALLBACK] Reason: Gemini {type(exception).__name__}")
            return True
    except ImportError:
        pass

    keywords = ["quota", "resource exhausted", "rate limit", "too many requests", "429",
                "service unavailable", "503", "deadline exceeded", "timeout",
                "internal server error", "500"]
    if any(kw in str(exception).lower() for kw in keywords):
        print(f"[FALLBACK] Reason: Gemini keyword match – {str(exception)[:100]}")
        return True

    return False
