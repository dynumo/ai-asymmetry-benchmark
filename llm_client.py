# llm_client.py
import os
import requests
import time
import threading

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY")
NOVITA_API_KEY    = os.getenv("NOVITA_API_KEY")
MISTRAL_API_KEY   = os.getenv("MISTRAL_API_KEY")

# ---- Novita rate limit (RPM: 10) ----
_NOVITA_RPM = 10
_novita_lock = threading.Lock()
_novita_last_call = 0.0  # perf_counter seconds

def ask(model_name: str, prompt: str) -> str:
    """
    Send prompt to the right API and return text output.

    Accepts:
      - 'provider:model'  (e.g., 'novita:deepseek/deepseek-v3-0324')
      - 'provider/model'  (e.g., 'novita/deepseek/deepseek-v3-0324')
    Falls back to basic heuristics if no provider prefix is present.
    """
    provider, pure_model = _parse_provider_and_model(model_name)

    if provider == "openai":
        return _ask_openai(pure_model, prompt)
    elif provider == "anthropic":
        return _ask_anthropic(pure_model, prompt)
    elif provider == "groq":
        return _ask_groq(pure_model, prompt)
    elif provider == "novita":
        return _ask_novita(pure_model, prompt)
    elif provider == "mistral":
        return _ask_mistral(pure_model, prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")

# --------------------
# HTTP retry helper
# --------------------

def _post_with_retries(
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
    timeout: int = 60,
    retries: int = 3,
    backoff_factor: float = 1.0,
) -> requests.Response:
    """
    POST to ``url`` with retries and exponential backoff.

    Raises RuntimeError with context if all retries fail.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=json, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == retries:
                detail = f"{type(exc).__name__}: {exc}"
                if getattr(exc, "response", None) is not None:
                    r = exc.response
                    detail += f" (status={r.status_code}, body={r.text[:200]})"
                raise RuntimeError(
                    f"POST {url} failed after {retries} attempts: {detail}"
                ) from exc
            sleep = backoff_factor * (2 ** (attempt - 1))
            time.sleep(sleep)
    # Should not reach here
    raise RuntimeError(f"POST {url} failed: {last_exc}")

# --------------------
# Provider/model parsing
# --------------------

def _parse_provider_and_model(s: str):
    """
    Returns (provider, model) with provider removed from 's'.
    Supports 'prov:model' and 'prov/model'.
    If no provider is found, uses simple heuristics.
    """
    # Explicit 'prov:model'
    if ":" in s:
        prov, model = s.split(":", 1)
        return prov.lower(), model

    # Explicit 'prov/model'
    if "/" in s:
        prov_guess = s.split("/", 1)[0].lower()
        if prov_guess in {"openai", "anthropic", "groq", "novita", "mistral"}:
            prov, model = s.split("/", 1)
            return prov.lower(), model

    # Heuristics (back-compat)
    if s.startswith(("gpt-", "o", "ft:")):
        return "openai", s
    if s.startswith("claude"):
        return "anthropic", s
    # Default to OpenAI if unknown
    return "openai", s

# --------------------
# Provider functions
# --------------------

def _ask_openai(model: str, prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    r = _post_with_retries(url, headers=headers, json=payload, timeout=60)
    return r.json()["choices"][0]["message"]["content"].strip()

def _ask_anthropic(model: str, prompt: str) -> str:
    import anthropic
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    # Anthropic returns content blocks
    return resp.content[0].text.strip() if resp.content else ""

def _ask_groq(model: str, prompt: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    r = _post_with_retries(url, headers=headers, json=payload, timeout=60)
    return r.json()["choices"][0]["message"]["content"].strip()

def _ask_novita(model: str, prompt: str) -> str:
    if not NOVITA_API_KEY:
        raise RuntimeError("Missing NOVITA_API_KEY")

    # --- simple RPM limiter (10/min) ---
    interval = 60.0 / float(_NOVITA_RPM)
    global _novita_last_call
    with _novita_lock:
        now = time.perf_counter()
        wait = max(0.0, (_novita_last_call + interval) - now)
        if wait > 0:
            time.sleep(wait)
        _novita_last_call = time.perf_counter()

    url = "https://api.novita.ai/v3/openai/chat/completions"
    headers = {"Authorization": f"Bearer {NOVITA_API_KEY}"}
    payload = {
        "model": model,  # e.g. "deepseek/deepseek-v3-0324"
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "text"},
    }
    r = _post_with_retries(url, headers=headers, json=payload, timeout=60)
    return r.json()["choices"][0]["message"]["content"].strip()

def _ask_mistral(model: str, prompt: str) -> str:
    if not MISTRAL_API_KEY:
        raise RuntimeError("Missing MISTRAL_API_KEY")
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    r = _post_with_retries(url, headers=headers, json=payload, timeout=60)
    return r.json()["choices"][0]["message"]["content"].strip()
