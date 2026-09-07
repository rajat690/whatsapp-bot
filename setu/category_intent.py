"""Free-text category intent → schemes_by_category_v1 pack ids.

Named scheme lookup (PR #6 `setu/lookup.py`) wins when both a scheme name and a
category word could match, except for a bare category keyword such as
"scholarship" — that is a pack, not a library card.
"""

from __future__ import annotations

import re
from typing import Any

from . import nlu

# (phrase, pack id, language hint or None). Longer phrases win.
# Do not list named schemes (Ujjwala, Stree Shakti, PMAY, Ayushman, Mudra, PM-Kisan).
_PHRASES: tuple[tuple[str, str, str | None], ...] = (
    # scholarship (more specific than education)
    ("pre-matric scholarship", "scholarship", "English"),
    ("post-matric scholarship", "scholarship", "English"),
    ("pre matric", "scholarship", "English"),
    ("post matric", "scholarship", "English"),
    ("scholarships", "scholarship", "English"),
    ("scholarship", "scholarship", "English"),
    ("scholorship", "scholarship", "English"),
    ("scholarhip", "scholarship", "English"),
    ("shishyavrutti", "scholarship", "English"),
    ("fellowship", "scholarship", "English"),
    ("छात्रवृत्ति", "scholarship", "Hindi"),
    ("छात्रवृति", "scholarship", "Hindi"),
    ("शिष्यवृत्ती", "scholarship", "Marathi"),
    ("ವಿದ್ಯಾರ್ಥಿವೇತನ", "scholarship", "Kannada"),
    # pension
    ("old age pension", "pension", "English"),
    ("widow pension", "pension", "English"),
    ("pensions", "pension", "English"),
    ("pension", "pension", "English"),
    ("पेंशन", "pension", "Hindi"),
    ("पेन्शन", "pension", "Hindi"),
    ("निवृत्तिवेतन", "pension", "Hindi"),
    ("वृद्धापकाश", "pension", "Hindi"),
    ("पेंशन योजना", "pension", "Hindi"),
    # education
    ("education schemes", "education", "English"),
    ("educational", "education", "English"),
    ("education", "education", "English"),
    ("shiksha", "education", "English"),
    ("शिक्षा", "education", "Hindi"),
    ("शिक्षण", "education", "Marathi"),
    ("ಶಿಕ್ಷಣ", "education", "Kannada"),
    # housing
    ("housing schemes", "housing", "English"),
    ("housing", "housing", "English"),
    ("आवास", "housing", "Hindi"),
    ("गृहनिर्माण", "housing", "Marathi"),
    # health — not Ayushman / PM-JAY (named lookup)
    ("healthcare", "health", "English"),
    ("health schemes", "health", "English"),
    ("health", "health", "English"),
    ("स्वास्थ्य", "health", "Hindi"),
    ("आरोग्य", "health", "Marathi"),
    ("ಆರೋಗ್ಯ", "health", "Kannada"),
    ("arogya", "health", "English"),
    # agriculture — "kisan" alone can be PM-Kisan; keep farmer/agriculture
    ("agriculture", "agriculture", "English"),
    ("agricultural", "agriculture", "English"),
    ("farming", "agriculture", "English"),
    ("farmer", "agriculture", "English"),
    ("farmers", "agriculture", "English"),
    ("कृषि", "agriculture", "Hindi"),
    ("शेती", "agriculture", "Marathi"),
    ("ಕೃಷಿ", "agriculture", "Kannada"),
    ("किसान", "agriculture", "Hindi"),
    # disability
    ("disabilities", "disability", "English"),
    ("disability", "disability", "English"),
    ("disabled", "disability", "English"),
    ("divyangjan", "disability", "English"),
    ("divyang", "disability", "English"),
    ("दिव्यांगजन", "disability", "Hindi"),
    ("दिव्यांग", "disability", "Hindi"),
    ("विकलांग", "disability", "Hindi"),
    ("अपंगत्व", "disability", "Marathi"),
    ("अपंग", "disability", "Marathi"),
    # livelihood / MSME
    ("livelihoods", "livelihood", "English"),
    ("livelihood", "livelihood", "English"),
    ("self-employment", "livelihood", "English"),
    ("self employment", "livelihood", "English"),
    ("आजीविका", "livelihood", "Hindi"),
    ("रोजगार", "livelihood", "Hindi"),
    ("rozgar", "livelihood", "English"),
    ("msme", "livelihood", "English"),
    # women & child — not stree / shakti (named Stree Shakti)
    ("women and child", "women_child", "English"),
    ("women & child", "women_child", "English"),
    ("women schemes", "women_child", "English"),
    ("woman schemes", "women_child", "English"),
    ("women", "women_child", "English"),
    ("woman", "women_child", "English"),
    ("mahila", "women_child", "English"),
    ("महिला", "women_child", "Hindi"),
    # food & ration
    ("food and ration", "food_ration", "English"),
    ("food & ration", "food_ration", "English"),
    ("ration card", "food_ration", "English"),
    ("food schemes", "food_ration", "English"),
    ("ration", "food_ration", "English"),
    ("food", "food_ration", "English"),
    ("राशन", "food_ration", "Hindi"),
    ("खाद्य", "food_ration", "Hindi"),
    ("शिधापत्रिका", "food_ration", "Marathi"),
    # labour / BOCW
    ("construction workers", "labour_bocw", "English"),
    ("construction worker", "labour_bocw", "English"),
    ("unorganised worker", "labour_bocw", "English"),
    ("unorganized worker", "labour_bocw", "English"),
    ("labourer", "labour_bocw", "English"),
    ("laborer", "labour_bocw", "English"),
    ("labour", "labour_bocw", "English"),
    ("labor", "labour_bocw", "English"),
    ("bocw", "labour_bocw", "English"),
    ("mbocwwb", "labour_bocw", "English"),
    ("श्रमिक", "labour_bocw", "Hindi"),
    ("श्रम", "labour_bocw", "Hindi"),
    ("मजदूर", "labour_bocw", "Hindi"),
)

_SORTED_PHRASES = tuple(sorted(_PHRASES, key=lambda row: -len(row[0])))

_WRAPPERS = (
    "tell me about",
    "tell me",
    "i want to know about",
    "i want",
    "i need",
    "looking for",
    "schemes for",
    "scheme for",
    "schemes",
    "scheme",
    "yojana",
    "yojane",
    "yojna",
    "category",
    "topic",
    "please",
    "के बारे में",
    "योजनाएँ",
    "योजनाए",
    "योजना",
    "चाहिए",
    "मुझे",
)

_UNKNOWN_CATEGORY_RE = re.compile(
    r"(schemes?\s+for|for\s+\w+\s+schemes?|\b\w+\s+schemes?\b|"
    r"yojana|yojane|category|topic|"
    r"योजना|ಯೋಜನೆ|विषय)",
    re.I,
)

_IDLE_PHASES = frozenset({"welcome_language", "main_menu", "end_menu"})


def is_idle_phase(phase: str | None) -> bool:
    return (phase or "") in _IDLE_PHASES


def detect_category_intent(text: str) -> str | None:
    """Return a pack id if the user typed a category keyword, else None."""
    if not (text or "").strip():
        return None
    n = nlu._norm(text)
    if n in ("1", "1)", "2", "2)", "3", "3)"):
        return None
    hit = _best_phrase(text)
    return hit[0] if hit else None


def infer_category_language(text: str) -> str | None:
    """Language implied by the category phrase. Kannada script wins over Hindi guess."""
    if any(0x0C80 <= ord(ch) <= 0x0CFF for ch in text or ""):
        return "Kannada"
    matched = _best_phrase(text)
    if matched and matched[1]:
        return matched[1]
    detected = nlu.detect_language(text) or nlu.detect_language_switch(text)
    if detected:
        return detected
    if text and all((not ch.isalpha()) or ch.isascii() for ch in text):
        return "English"
    return None


def _best_phrase(text: str) -> tuple[str, str | None] | None:
    raw = (text or "").strip()
    n = nlu._norm(raw)
    if not n:
        return None
    for phrase, pack_id, lang in _SORTED_PHRASES:
        if _phrase_hits(raw, n, phrase):
            return pack_id, lang
    return None


def _phrase_hits(raw: str, normalized: str, phrase: str) -> bool:
    if any(ord(ch) > 127 for ch in phrase):
        return phrase in raw
    key = nlu._norm(phrase)
    if not key:
        return False
    return normalized == key or nlu._contains_phrase(normalized, key)


def _strip_wrappers(text: str) -> str:
    n = nlu._norm(text)
    for wrap in sorted(_WRAPPERS, key=len, reverse=True):
        n = re.sub(rf"(?<!\w){re.escape(nlu._norm(wrap))}(?!\w)", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def is_bare_category_query(text: str, category_id: str | None = None) -> bool:
    """True when the message is just a category word (plus scheme/yojana wrappers)."""
    cid = category_id or detect_category_intent(text)
    if not cid:
        return False
    leftover = _strip_wrappers(text)
    if not leftover:
        return True
    return _only_category_tokens(leftover, cid)


def _only_category_tokens(leftover: str, category_id: str) -> bool:
    raw = leftover
    n = nlu._norm(leftover)
    for phrase, pack_id, _lang in _SORTED_PHRASES:
        if pack_id != category_id:
            continue
        if not _phrase_hits(raw, n, phrase):
            continue
        if any(ord(ch) > 127 for ch in phrase):
            stripped = raw.replace(phrase, " ")
        else:
            stripped = re.sub(rf"(?<!\w){re.escape(nlu._norm(phrase))}(?!\w)", " ", n)
        return re.sub(r"\s+", " ", stripped).strip() == ""
    return False


def named_scheme_hits(text: str) -> list[dict[str, Any]]:
    """Optional PR #6 lookup — empty when that module is not on this branch."""
    try:
        from . import lookup
    except ImportError:
        return []
    search = getattr(lookup, "search_schemes", None)
    if not callable(search):
        return []
    try:
        return list(search(text) or [])
    except Exception:
        return []


def prefer_named_scheme(text: str) -> bool:
    """Named scheme identity beats a category pack when both could apply."""
    hits = named_scheme_hits(text)
    if not hits:
        return False
    cid = detect_category_intent(text)
    if cid and is_bare_category_query(text, cid):
        return False
    return True


def looks_like_unknown_category(text: str) -> bool:
    """Category-shaped ask we cannot map — honest miss, not Individual/Family."""
    if not (text or "").strip():
        return False
    if detect_category_intent(text):
        return False
    menu = nlu.detect_menu(text)
    if menu in ("Individual Schemes", "Family Schemes", "I need help", "Browse by category"):
        return False
    if nlu.detect_language(text) and nlu._norm(text) in nlu.LANGUAGE_MAP:
        return False
    return bool(_UNKNOWN_CATEGORY_RE.search(text or ""))
