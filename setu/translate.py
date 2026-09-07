"""Display-only translation of English scheme-library fields.

The JSON libraries stay English. This module never invents eligibility facts —
it asks the LLM to translate existing strings, and falls back to English when
the model is unavailable or the result is unusable.
"""

from __future__ import annotations

import json
from typing import Any

from . import i18n, llm

DISPLAY_FIELDS = (
    "Benefit",
    "Category",
    "Age Criteria",
    "Income Criteria",
    "Gender / Category Criteria",
    "Other Key Eligibility Criteria",
)

_cache: dict[tuple[str, str], str] = {}


def clear_cache() -> None:
    _cache.clear()


def _accept(original: str, translated: str, language: str) -> bool:
    text = (translated or "").strip()
    if not text:
        return False
    if text == original:
        return True
    letters = sum(1 for ch in original if ch.isalpha())
    # Short acronyms / codes may stay Latin.
    if letters < 8:
        return True
    return i18n.reply_matches_language(text, language)


def translate_many(texts: list[str], language: str | None) -> list[str]:
    """Translate strings into the session language. English / no-LLM → originals."""
    lang = i18n.normalize_language(language)
    originals = [str(t or "") for t in texts]
    if lang == "English" or not originals:
        return originals
    if not llm.llm_configured():
        return originals

    needed: list[str] = []
    for text in originals:
        stripped = text.strip()
        if not stripped:
            continue
        if (lang, stripped) not in _cache:
            needed.append(stripped)
    unique = list(dict.fromkeys(needed))
    if unique:
        system = (
            "You translate government-scheme text for a WhatsApp assistant in India.\n"
            f"Target language: {lang}.\n"
            "Translate faithfully. Do not add, omit, or reinterpret eligibility, "
            "amounts, dates, or conditions.\n"
            "Keep numbers, ₹ amounts, URLs, and official acronyms "
            "(PM-KISAN, SHG, BPL, AAY, SC, ST, OBC, DBT, LPG, PM-JAY) unchanged.\n"
            "Keep official scheme names in English.\n"
            "Return JSON only: {\"translations\": {\"<exact original>\": \"<translated>\"}}.\n"
            "Every input string must appear as a key."
        )
        data = llm.chat_json(
            system,
            json.dumps({"language": lang, "texts": unique}, ensure_ascii=False),
            temperature=0.1,
        )
        mapping: dict[str, str] = {}
        if isinstance(data, dict):
            raw = data.get("translations")
            if isinstance(raw, dict):
                mapping = {str(k): str(v) for k, v in raw.items() if v is not None}
            elif isinstance(raw, list) and len(raw) == len(unique):
                mapping = {src: str(dst) for src, dst in zip(unique, raw)}
        for src in unique:
            dst = mapping.get(src) or mapping.get(src.strip())
            if dst and _accept(src, dst, lang):
                _cache[(lang, src)] = dst.strip()
            else:
                _cache[(lang, src)] = src

    out: list[str] = []
    for text in originals:
        stripped = text.strip()
        if not stripped:
            out.append(text)
            continue
        out.append(_cache.get((lang, stripped), text))
    return out


def translate_fields(fields: dict[str, str], language: str | None) -> dict[str, str]:
    keys = list(fields.keys())
    values = [fields[k] for k in keys]
    translated = translate_many(values, language)
    return dict(zip(keys, translated))


def localize_scheme(scheme: dict[str, Any], language: str | None) -> dict[str, Any]:
    """Shallow copy with display fields translated. Scheme Name stays English."""
    item = dict(scheme)
    lang = i18n.normalize_language(language)
    if lang == "English":
        return item
    payload = {
        key: str(scheme.get(key) or "")
        for key in DISPLAY_FIELDS
        if str(scheme.get(key) or "").strip()
    }
    if not payload:
        return item
    localized = translate_fields(payload, lang)
    item.update(localized)
    return item
