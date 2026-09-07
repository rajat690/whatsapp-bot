"""Deterministic named-scheme lookup against Central + state libraries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import i18n, translate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_STOP = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "for",
    "to",
    "in",
    "on",
    "about",
    "tell",
    "me",
    "please",
    "what",
    "is",
    "whats",
    "information",
    "info",
    "details",
    "regarding",
    "know",
    "want",
    "need",
    "scheme",
    "schemes",
    "yojana",
    "yojane",
    "yojna",
    "govt",
    "government",
    "india",
    "ask",
    "another",
}

_WEAK = {
    "pradhan",
    "mantri",
    "pradhanmantri",
    "pm",
    "national",
    "state",
    "central",
    "mukhyamantri",
}

_GENERIC_QUERIES = {
    "english",
    "hindi",
    "marathi",
    "kannada",
    "help",
    "hi",
    "hello",
    "hey",
    "yes",
    "no",
    "ok",
    "okay",
    "proceed",
    "edit",
    "support",
    "menu",
    "individual",
    "family",
    "bye",
    "tata",
    "ciao",
    "ola",
    "goodbye",
    "end",
    "stop",
    "exit",
    "quit",
    "later",
    "हिंदी",
    "हिन्दी",
    "मराठी",
    "ಕನ್ನಡ",
}

# Hindi / common aliases → English search keys already present in names.
_ALIASES: dict[str, str] = {
    "pmuy": "ujjwala",
    "pm ujjwala": "ujjwala",
    "ujjwala yojana": "ujjwala",
    "ujjvala": "ujjwala",
    "ujjwal": "ujjwala",
    "ujala yojana": "ujjwala",
    "उज्ज्वला": "ujjwala",
    "उज्जवला": "ujjwala",
    "उज्वला": "ujjwala",
    "प्रधानमंत्री उज्ज्वला": "ujjwala",
    "प्रधान मंत्री उज्ज्वला": "ujjwala",
    "stree sakti": "stree shakti",
    "stri shakti": "stree shakti",
    "stree shakti scheme": "stree shakti",
    "stree sakti scheme": "stree shakti",
    "स्त्री शक्ति": "stree shakti",
    "स्त्रीशक्ति": "stree shakti",
    "स्ट्री शक्ति": "stree shakti",
    "pm kisan": "pm-kisan",
    "pmkisan": "pm-kisan",
    "पीएम किसान": "pm-kisan",
    "ayushman bharat": "ayushman",
    "pmjay": "ayushman",
    "pm-jay": "ayushman",
    "आयुष्मान": "ayushman",
}

_PREFIX_RE = re.compile(
    r"^(?:please\s+)?"
    r"(?:tell me about|tell me|what is|what's|whats|what are|"
    r"do you know about|info(?:rmation)? (?:on|about|regarding)|"
    r"details (?:on|about|of|regarding)|explain|describe|"
    r"i (?:want|need|would like) (?:to know |info |information )?(?:about |on )?)\s+",
    re.I,
)
_HINDI_PREFIX_RE = re.compile(
    r"^(?:कृपया\s+)?(?:मुझे\s+)?(?:बताओ|बताइए|बताएं|बताएँ|सांगा)\s+"
)
_HINDI_ABOUT_RE = re.compile(
    r"\s*(?:के बारे में|बाबत|विषय में).*$"
)
_PUNCT_RE = re.compile(r"[^\w\s\u0900-\u097F\u0C80-\u0CFF/-]+", re.UNICODE)
_ACRONYM_RE = re.compile(r"\(([A-Za-z0-9][A-Za-z0-9/_-]{1,15})\)")

_CACHE: list[dict[str, Any]] | None = None


def _load_json(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def load_all_schemes() -> list[dict[str, Any]]:
    """Central + Karnataka + Maharashtra scheme records (cached)."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    schemes: list[dict[str, Any]] = []
    index = _load_json("schemes_index.json")
    for lib in index.get("libraries", []):
        filename = lib.get("file")
        if not filename or not (DATA_DIR / filename).exists():
            continue
        data = _load_json(filename)
        label = lib.get("state_scope") or "Central"
        for raw in data.get("schemes", []):
            item = dict(raw)
            item.setdefault("_library", label)
            schemes.append(item)
    _CACHE = schemes
    return schemes


def _norm(text: str) -> str:
    text = (text or "").lower().strip()
    text = text.replace("–", "-").replace("—", "-")
    text = _PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_scheme_query(text: str) -> str:
    """Strip 'tell me about' / Hindi wrappers; keep the scheme-name core."""
    raw = (text or "").strip()
    if not raw:
        return ""
    raw = _PREFIX_RE.sub("", raw).strip()
    raw = _HINDI_PREFIX_RE.sub("", raw).strip()
    raw = _HINDI_ABOUT_RE.sub("", raw).strip()
    raw = re.sub(r"[?.!]+$", "", raw).strip()
    return raw


def apply_aliases(query: str) -> str:
    n = _norm(query)
    if not n:
        return query
    for key, val in sorted(_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if n == key or key in n:
            return val
    return query


def _tokens(text: str) -> list[str]:
    return [t for t in _norm(text).replace("-", " ").split() if t]


def _distinctive(tokens: list[str]) -> list[str]:
    out = []
    for t in tokens:
        if t in _STOP or t in _WEAK:
            continue
        if len(t) >= 4 or (t.isalnum() and 3 <= len(t) <= 8 and t.isalpha() and t.isupper()):
            out.append(t)
        elif len(t) >= 4:
            out.append(t)
        elif t.isalnum() and 3 <= len(t) <= 8 and not t.isdigit():
            # short acronyms: pmay, pmuy, kcc
            out.append(t)
    return out


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 2:
        return 99
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def _close(a: str, b: str) -> bool:
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    # Require a real stem — "u" from "(SBM-U)" must not match "ujjwala".
    if len(shorter) >= 4 and shorter in longer:
        return True
    if min(len(a), len(b)) < 4:
        return False
    limit = 1 if min(len(a), len(b)) < 7 else 2
    return _levenshtein(a, b) <= limit


def _token_hit(query_tok: str, name_tokens: list[str]) -> bool:
    return any(_close(query_tok, nt) for nt in name_tokens)


def _acronyms(name: str) -> set[str]:
    found = set()
    for m in _ACRONYM_RE.finditer(name or ""):
        found.add(_norm(m.group(1)).replace("-", "").replace(" ", "").replace("/", ""))
    return {a for a in found if a}


def _score(query: str, scheme: dict[str, Any]) -> int:
    name = str(scheme.get("Scheme Name") or "")
    if not name:
        return 0
    q_norm = _norm(apply_aliases(query))
    n_norm = _norm(name)
    if not q_norm:
        return 0

    q_compact = q_norm.replace(" ", "").replace("-", "")
    n_compact = n_norm.replace(" ", "").replace("-", "")
    acr = _acronyms(name)
    if q_compact and q_compact in acr:
        return 94

    q_tokens = [t for t in _tokens(q_norm) if t not in _STOP]
    n_tokens = _tokens(n_norm)
    q_core = " ".join(t for t in q_tokens if t not in _WEAK)
    n_core = " ".join(t for t in n_tokens if t not in _STOP and t not in _WEAK)
    distinctive = _distinctive(q_tokens)

    if q_core and n_core and q_core == n_core:
        return 98
    if q_norm == n_norm:
        return 100
    if q_core and n_core and q_core in n_core:
        return 92
    if q_core and n_core and n_core in q_core:
        extra = [t for t in distinctive if not _token_hit(t, n_tokens)]
        if not extra:
            return 90
    if q_compact and len(q_compact) >= 5 and q_compact in n_compact:
        return 88
    if not distinctive:
        return 0

    matched = sum(1 for t in distinctive if _token_hit(t, n_tokens))
    if matched == 0:
        return 0
    ratio = matched / len(distinctive)
    if ratio < 1.0 and len(distinctive) > 1:
        return int(42 * ratio)
    return int(72 + 22 * ratio)


def search_schemes(text: str, limit: int = 6) -> list[dict[str, Any]]:
    """Return library schemes matching a named-scheme query (best first)."""
    query = extract_scheme_query(text)
    if not query:
        return []
    if _norm(query) in _GENERIC_QUERIES:
        return []
    aliased = apply_aliases(query)
    if _norm(aliased) in _GENERIC_QUERIES:
        return []
    distinctive = _distinctive([t for t in _tokens(aliased) if t not in _STOP])
    if not distinctive:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for scheme in load_all_schemes():
        score = _score(aliased, scheme)
        if score >= 55:
            item = dict(scheme)
            item["_lookup_score"] = score
            scored.append((score, item))
    scored.sort(
        key=lambda x: (
            -x[0],
            len(str(x[1].get("Scheme Name") or "")),
            str(x[1].get("_library") or ""),
        )
    )
    if not scored:
        return []
    best = scored[0][0]
    # Keep near-ties; drop clearly weaker names (stree shakti vs generic shakti).
    kept = [s for score, s in scored if score >= best - 12][:limit]
    if best >= 88 and len(kept) > 1 and scored[1][0] < 80:
        return [scored[0][1]]
    return kept


def extract_apply_link(scheme: dict[str, Any]) -> str:
    source = scheme.get("Beneficiary Count — Source Note") or ""
    m = re.search(r"https?://\S+", source)
    if not m:
        return ""
    return m.group(0).rstrip("|).,").strip()


def _useful(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.lower() in {"n/a", "na", "none", "-", "not specified", "nil"}:
        return ""
    return text


def format_named_scheme_detail(
    scheme: dict[str, Any],
    next_prompt: str | None = None,
    language: str | None = None,
) -> str:
    """Numbered library card — name, about, eligibility, link. No invented facts."""
    lang = i18n.normalize_language(language)
    display = translate.localize_scheme(scheme, lang)
    name = _useful(scheme.get("Scheme Name")) or "Scheme"
    lib = i18n.library_label(scheme.get("_library"), lang)
    about = _useful(display.get("Benefit"))
    eligibility_bits = [
        _useful(display.get("Age Criteria")),
        _useful(display.get("Income Criteria")),
        _useful(display.get("Gender / Category Criteria")),
        _useful(display.get("Other Key Eligibility Criteria")),
    ]
    eligibility_bits = [b for b in eligibility_bits if b]
    link = extract_apply_link(scheme)

    lines = [
        f"1. {i18n.t('named_field_name', lang)}: *{name}*"
        + (f" ({lib})" if lib else "")
    ]
    if about:
        lines.append(f"2. {i18n.t('named_field_about', lang)}: {about}")
    if eligibility_bits:
        n = 3 if about else 2
        lines.append(
            f"{n}. {i18n.t('named_field_eligibility', lang)}: " + "; ".join(eligibility_bits)
        )
    if link:
        n = 1 + sum(1 for x in (about, eligibility_bits) if x)
        lines.append(f"{n + 1}. {i18n.t('named_field_apply', lang)}: {link}")
    lines.append("")
    lines.append(i18n.t("named_library_note", lang))
    if next_prompt:
        lines.append("")
        lines.append(next_prompt)
    return "\n".join(lines)


def format_named_scheme_list(
    schemes: list[dict[str, Any]],
    intro: str,
    footer: str,
    language: str | None = None,
) -> str:
    from . import eligibility

    lang = i18n.normalize_language(language)
    lines = [intro, ""]
    lines.extend(eligibility.numbered_scheme_lines(schemes, lang))
    if footer:
        lines.append("")
        lines.append(footer)
    return "\n".join(lines)
