"""Optional OpenAI-compatible LLM client for conversational turns."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


def llm_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))


def _settings() -> tuple[str, str, str]:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or ""
    base = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = (
        os.environ.get("OPENAI_MODEL")
        or os.environ.get("LLM_MODEL")
        or "gpt-4o-mini"
    )
    return api_key, base, model


def chat_json(system: str, user: str, temperature: float = 0.4) -> dict[str, Any] | None:
    """Call chat completions and parse a JSON object from the reply."""
    api_key, base, model = _settings()
    if not api_key:
        return None

    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        if not resp.ok:
            # Some providers reject response_format — retry without it
            if resp.status_code in (400, 422):
                payload.pop("response_format", None)
                resp = requests.post(url, headers=headers, json=payload, timeout=40)
            if not resp.ok:
                print(f"LLM error {resp.status_code}: {resp.text[:500]}", flush=True)
                return None
        content = resp.json()["choices"][0]["message"]["content"]
        return _extract_json(content)
    except Exception as exc:
        print(f"LLM request failed: {exc}", flush=True)
        return None


def chat_text(system: str, user: str, temperature: float = 0.6) -> str | None:
    api_key, base, model = _settings()
    if not api_key:
        return None
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        if not resp.ok:
            print(f"LLM error {resp.status_code}: {resp.text[:500]}", flush=True)
            return None
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        print(f"LLM request failed: {exc}", flush=True)
        return None


def _extract_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
