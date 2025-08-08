# llm_client.py
import os
import requests

# Optional: you can make these configurable in your .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NOVITA_API_KEY = os.getenv("NOVITA_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

def ask(model_name: str, prompt: str) -> str:
    """Send prompt to the right API based on model_name and return text output."""
    if model_name.startswith(("gpt-", "o", "ft:")):  # OpenAI models
        return _ask_openai(model_name, prompt)
    elif model_name.startswith("claude"):
        return _ask_anthropic(model_name, prompt)
    elif model_name.startswith("groq/"):
        return _ask_groq(model_name.replace("groq/", ""), prompt)
    elif model_name.startswith("novita/"):
        return _ask_novita(model_name.replace("novita/", ""), prompt)
    elif model_name.startswith("mistral/"):
        return _ask_mistral(model_name.replace("mistral/", ""), prompt)
    else:
        raise ValueError(f"Unknown provider for model: {model_name}")

# --------------------
# Provider functions
# --------------------

def _ask_openai(model: str, prompt: str) -> str:
    import openai
    openai.api_key = OPENAI_API_KEY
    resp = openai.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content.strip()

def _ask_anthropic(model: str, prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text.strip()

def _ask_groq(model: str, prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def _ask_novita(model: str, prompt: str) -> str:
    url = "https://api.novita.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {NOVITA_API_KEY}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def _ask_mistral(model: str, prompt: str) -> str:
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()