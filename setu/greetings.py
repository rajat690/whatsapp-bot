"""Deterministic greeting / activation detector (EN, HI, MR, KN). Not LLM."""

from __future__ import annotations

import re

from . import category_intent, nlu, profile_intent

# Skin-tone / VS16 stripped before comparing.
_GREETING_EMOJI_CHARS = frozenset("👋🙏")
_STRIP_EMOJI_MARKS = re.compile(r"[\u200d\ufe0f\U0001F3FB-\U0001F3FF]")

# Full-message phrases (already lowercased / folded). Longer first.
_PHRASES: tuple[str, ...] = (
    "jai shree ram",
    "jai shri ram",
    "jai sri ram",
    "jay shree ram",
    "jai maharashtra",
    "jay maharashtra",
    "good morning",
    "good afternoon",
    "good evening",
    "hey there",
    "radhe radhe",
    "ram ram",
    "subh prabhat",
    "shubh prabhat",
    "shubh prabhath",
    "shubh sakal",
    "subh sakal",
    "shubhodaya",
    "shubhodhaya",
    "kaise ho aap",
    "kaise ho",
    "kaisi ho",
    "namaskaram",
    "namaskara",
    "namaskar",
    "namasthe",
    "namaste",
    "pranam",
    "pranaam",
    "howdy",
    "hello",
    "helo",
    "hola",
    "halo",
    "hay",
    "hey",
    "yo",
    "hi",
    "begin",
    "start",
    # Devanagari / Kannada
    "जय श्री राम",
    "जय श्रीराम",
    "जय महाराष्ट्र",
    "शुभ प्रभात",
    "शुभ सकाळ",
    "शुभ सकाल",
    "कैसे हो आप",
    "कैसे हो",
    "कैसी हो",
    "राधे राधे",
    "राम राम",
    "नमस्कार",
    "नमस्ते",
    "प्रणाम",
    "प्रणाम",
    "ನಮಸ್ಕಾರ",
    "ನಮಸ್ತೆ",
    "ರಾಧೇ ರಾಧೇ",
    "ಶುಭೋದಯ",
    "ಹಾಯ್",
    "ಹಲೋ",
)

_PHRASE_SET = frozenset(_PHRASES)

# Optional trailing politeness after a greeting phrase.
_POLITE_SUFFIX = re.compile(
    r"[\s,]+(?:ji|jee|ji+|please|plz|pls|जी)+\s*$",
    re.I,
)

_TYPO_HI = re.compile(r"^h+i+$")
_TYPO_HEY = re.compile(r"^h+e+y+$")
_TYPO_HELLO = re.compile(r"^h+e+l+o+$")

_EXPLICIT_RESTART = frozenset(
    {
        "restart",
        "/start",
        "start over",
        "startover",
        "reset",
        "reset bot",
        "शुरू से",
        "पुन्हा सुरू",
    }
)

_STRONG_SCHEME = re.compile(
    r"\b(yojana|yojane|yojna|scheme|योजना|ಯೋಜನೆ)\b",
    re.I,
)


def _fold(text: str) -> str:
    t = (text or "").strip()
    t = _STRIP_EMOJI_MARKS.sub("", t)
    for ch in _GREETING_EMOJI_CHARS:
        t = t.replace(ch, " ")
    t = re.sub(r"[!.,?~|;:।]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = _POLITE_SUFFIX.sub("", t).strip()
    return t


def _is_emoji_only_greeting(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    stripped = re.sub(r"[\s!.,?~]+", "", raw)
    if not stripped:
        return False
    body = _STRIP_EMOJI_MARKS.sub("", stripped)
    return bool(body) and all(ch in _GREETING_EMOJI_CHARS for ch in body)


def _typo_greeting(folded: str) -> bool:
    if not folded or " " in folded:
        return _TYPO_HI.fullmatch(folded.replace(" ", "")) is not None and " " not in folded
    return bool(_TYPO_HI.fullmatch(folded) or _TYPO_HEY.fullmatch(folded) or _TYPO_HELLO.fullmatch(folded))


def _has_stronger_intent(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    if profile_intent.looks_like_scheme_name_query(raw):
        return True
    if profile_intent.is_profile_story(raw) or profile_intent.mentions_multiple_people(raw):
        return True
    if profile_intent.is_long_life_paragraph(raw):
        return True
    if profile_intent.detect_role_shortcut(raw):
        return True
    if category_intent.detect_category_intent(raw) and not _looks_like_greeting_shell(raw):
        return True
    if nlu.detect_state(raw) and profile_intent.word_count(raw) >= 4:
        return True
    if _STRONG_SCHEME.search(raw) and profile_intent.word_count(raw) >= 4:
        return True
    return False


def _looks_like_greeting_shell(text: str) -> bool:
    """True when removing greetings leaves almost nothing."""
    folded = _fold(text)
    leftover = folded
    for phrase in sorted(_PHRASES, key=len, reverse=True):
        leftover = leftover.replace(phrase, " ")
    leftover = re.sub(r"\s+", " ", leftover).strip()
    return len(leftover) <= 2


def is_explicit_restart(text: str) -> bool:
    """Hard session wipe: restart /start / start over — not a soft hi."""
    n = nlu._norm(text)
    return n in _EXPLICIT_RESTART


def is_pure_greeting(text: str) -> bool:
    """Short activation greeting, not a life story that merely contains hello."""
    raw = (text or "").strip()
    if not raw:
        return False
    if is_explicit_restart(raw):
        return False
    if _is_emoji_only_greeting(raw):
        return True
    if _has_stronger_intent(raw):
        return False
    folded = _fold(raw)
    if not folded:
        return _is_emoji_only_greeting(raw)
    words = folded.split()
    if len(words) > 8:
        return False
    if folded in _PHRASE_SET or _typo_greeting(folded):
        return True
    # All tokens are themselves greetings ("hi hello", "namaste namaskar").
    if words and all(w in _PHRASE_SET or _typo_greeting(w) for w in words):
        return True
    # kaise ho / कैसे हो only as a short opener (already in _PHRASES; length gated).
    return False
