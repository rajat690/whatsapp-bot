"""Free-text classification: named scheme vs category vs profile story vs clarify.

Order (product spec):
1. Named scheme — only when the message looks like a scheme-name query
2. Category keyword (scholarship, pension, …) — not inside a multi-person life story
3. Profile / “what can I get?” story → who-first (or a single-role shortcut)
4. Else → who-is-this-for clarify, or main menu
"""

from __future__ import annotations

import re
from typing import Any

from . import category_intent, nlu

FARMER_EXAMPLE = (
    "i am 50 yr old farmer i have 2 kids in family 2 girls 8th class wife is "
    "ahouse wife i am a dlaily wage labouror, i have a small farm, what scheme "
    "and subsidy can i recieve"
)

_SCHEME_NAME_PREFIX = re.compile(
    r"(tell me about|what is|what's|whats|do you know about|"
    r"info(?:rmation)? (?:on|about|regarding)|"
    r"details (?:on|about|of|regarding)|explain|describe|"
    r"के बारे में|बताओ|बताइए|बताएं|बताएँ|सांगा)",
    re.I,
)
_SHORT_NAMED = re.compile(
    r"^\s*(?:please\s+)?(?:the\s+)?"
    r"([a-z][a-z0-9\s\-']{1,48})\s+"
    r"(yojana|yojane|yojna|scheme|योजना|ಯೋಜನೆ)\s*$",
    re.I,
)
_KNOWN_SHORT_NAMES = re.compile(
    r"\b(ujjwala|pmuy|pmay|stree shakti|ayushman|pm-?jay|pm-?kisan|"
    r"pm kisan|mudra|ujjvala)\b",
    re.I,
)

_FAMILY_MARKERS = (
    "wife",
    "spouse",
    "husband",
    "kids",
    "kid",
    "children",
    "child",
    "daughter",
    "son",
    "girls",
    "boys",
    "family",
    "पत्नी",
    "बीवी",
    "बायको",
    "मुले",
    "बच्चे",
    "पत्नी",
    "ಮಕ್ಕಳ",
    "ಹೆಂಡತಿ",
)
_SELF_MARKERS = (" i am ", " i'm ", " i m ", "myself", "i have", "my wife", "my kids")

_WHAT_CAN_I_GET = re.compile(
    r"(what (?:scheme|schemes|subsidy|subsidies)|"
    r"which (?:scheme|schemes)|"
    r"what can i (?:get|receive|recieve|avail)|"
    r"schemes? (?:can|do) i|"
    r"any scheme|"
    r"help me (?:get|find|receive)|"
    r"government (?:help|scheme|subsidy)|"
    r"योजना\s*(?:चाहिए|मिल|कौन)|"
    r"अनुदान)",
    re.I,
)

_VAGUE = re.compile(
    r"(help me get (?:a )?subsidy|help me (?:with )?schemes?|"
    r"what (?:schemes?|subsid(?:y|ies)) can i (?:get|receive|recieve)|"
    r"any (?:scheme|subsidy)|which scheme|"
    r"i want (?:a )?subsidy|subsidy please|"
    r"government subsidy|"
    r"कोई योजना|योजना चाहिए|अनुदान चाहिए)",
    re.I,
)

_WIDOW = re.compile(r"\b(widow|widowed|widower|विधवा|विधुर)\b", re.I)
_OLD_AGE_PENSION = re.compile(
    r"(old age pension|senior citizen pension|old-age pension|वृद्धावस्था पेंशन)",
    re.I,
)
_DISABILITY = re.compile(
    r"\b(disabilit(?:y|ies)|disabled|handicap(?:ped)?|divyang(?:jan)?|"
    r"pwd|विकलांग|दिव्यांग|अपंग)\b"
    r"|(\d{1,3}\s*%?\s*handicap)",
    re.I,
)
_PREGNANT = re.compile(
    r"\b(pregnant|pregnan|lactating|breastfeed|expecting|"
    r"mother of (?:an? )?infant|newborn|"
    r"गर्भवती|स्तनपान)\b",
    re.I,
)
_LABOUR = re.compile(
    r"\b(bocw|mbocwwb|construction(?: worker)?|daily wage|dlaily wage|"
    r"labourer|laborer|labouror|laboror|unorganis(?:ed|ed) worker|"
    r"मजदूर|निर्माण श्रमिक)\b",
    re.I,
)
_HOUSING = re.compile(
    r"\b(pmay|pukka|pucca|kutcha|kaccha|kacha|"
    r"need (?:a )?house|housing scheme|own house|"
    r"आवास|घर चाहिए)\b",
    re.I,
)
_RATION = re.compile(
    r"\b(ration card|food subsidy|ration|राशन|शिधापत्रिका|antyodaya|aay)\b",
    re.I,
)
_FARMER = re.compile(r"\b(farmer|farming|agriculture|agricultur|kisan|किसान|कृषि|शेती)\b", re.I)

_CLASS_RE = re.compile(r"\b(\d{1,2})(?:th|st|nd|rd)?\s*class\b", re.I)


def _norm(text: str) -> str:
    return nlu._norm(text or "")


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or "", flags=re.UNICODE))


def mentions_multiple_people(text: str) -> bool:
    """True when the speaker plus another household member (spouse/kids) appear."""
    n = f" {_norm(text)} "
    family_hits = sum(1 for m in _FAMILY_MARKERS if nlu._contains_phrase(n, m) or m in n)
    self_hit = any(m in n for m in _SELF_MARKERS) or n.strip().startswith("i am")
    has_kids = any(
        p in n
        for p in (" kid", " kids", " child", " children", " daughter", " son", " girls", " boys", "बच्चे", "मुले")
    )
    has_spouse = any(p in n for p in (" wife", " spouse", " husband", "पत्नी", "बीवी", "बायको", "ಹೆಂಡತಿ"))
    if has_kids and has_spouse:
        return True
    if self_hit and (has_kids or has_spouse) and family_hits >= 1:
        return True
    if has_kids and has_spouse:
        return True
    # "2 kids in family" + "wife" without a clean self marker
    if has_kids and has_spouse:
        return True
    return False


def extract_signals(text: str) -> dict[str, Any]:
    n = _norm(text)
    years = nlu.detect_age_years(text)
    age = nlu.detect_age(text)
    occ = nlu._map_alias(text, nlu.OCCUPATION_ALIASES)
    kids = nlu.detect_count(text, prefer=False, kind="children")
    girl = bool(re.search(r"\bgirls?\b|बालिका|girl child", n, re.I))
    class_m = _CLASS_RE.search(text or "")
    social = nlu._map_alias(text, nlu.CATEGORY_ALIASES)
    gender = nlu.detect_gender(text)
    return {
        "age": str(years) if years is not None else None,
        "age_group": age,
        "occupation": occ,
        "social_category": social,
        "gender": gender,
        "farmer": bool(_FARMER.search(text or "")),
        "labour": bool(_LABOUR.search(text or "") or (occ == "Labourer")),
        "children": kids,
        "girl_child": girl,
        "school_class": class_m.group(1) if class_m else None,
        "spouse": bool(re.search(r"\b(wife|spouse|husband|पत्नी|बीवी)\b", n, re.I)),
        "raw": (text or "").strip(),
    }


def asks_for_schemes(text: str) -> bool:
    """True when the user is asking which schemes they can get."""
    return bool(_WHAT_CAN_I_GET.search(text or ""))


def is_profile_story(text: str) -> bool:
    """Multi-slot life paragraph / ‘what can I get?’ story — not a scheme name."""
    raw = (text or "").strip()
    if not raw:
        return False
    if looks_like_scheme_name_query(raw) and word_count(raw) <= 10:
        return False
    n = _norm(raw)
    signals = 0
    if nlu.detect_age(raw):
        signals += 1
    if nlu._map_alias(raw, nlu.OCCUPATION_ALIASES) or _FARMER.search(raw):
        signals += 1
    if nlu.detect_count(raw, prefer=False, kind="children") is not None:
        signals += 1
    if re.search(r"\b(wife|spouse|husband|पत्नी|kids|children|child|family)\b", n):
        signals += 1
    if nlu.detect_income(raw):
        signals += 1
    if nlu.detect_housing(raw, prefer=False):
        signals += 1
    if _WHAT_CAN_I_GET.search(raw):
        signals += 1
    words = word_count(raw)
    if mentions_multiple_people(raw) and signals >= 2:
        return True
    if signals >= 3:
        return True
    if signals >= 2 and words >= 18:
        return True
    if signals >= 2 and _WHAT_CAN_I_GET.search(raw):
        return True
    if words >= 22 and (n.startswith("i am") or " i am " in f" {n} ") and _WHAT_CAN_I_GET.search(raw):
        return True
    return False


def looks_like_scheme_name_query(text: str) -> bool:
    """True only for a named-scheme ask, not a life story or vague subsidy."""
    raw = (text or "").strip()
    if not raw:
        return False
    if nlu.is_plain_menu_choice(raw):
        return False
    words = word_count(raw)
    if words >= 18 and mentions_multiple_people(raw):
        return False
    if is_long_life_paragraph(raw):
        return False
    if (
        category_intent.looks_like_unknown_category(raw)
        and not _SCHEME_NAME_PREFIX.search(raw)
        and not _KNOWN_SHORT_NAMES.search(raw)
        and not _SHORT_NAMED.match(raw)
    ):
        return False
    if _SHORT_NAMED.match(raw):
        return True
    if _KNOWN_SHORT_NAMES.search(raw) and words <= 12:
        # "I need a PMAY house" is a housing need, not a library-name query.
        if re.search(r"\b(need|kutcha|kaccha|kacha|house|housing|आवास)\b", raw, re.I) and not _SCHEME_NAME_PREFIX.search(raw):
            return False
        return True
    if _SCHEME_NAME_PREFIX.search(raw) and words <= 16:
        # "tell me about ujjwala" yes; "tell me about schemes for my family" no
        rest = _SCHEME_NAME_PREFIX.sub(" ", raw)
        rest_n = _norm(rest)
        if any(p in rest_n for p in ("for my", "for me", "family", "wife", "kids", "children", "subsidy")):
            return False
        if word_count(rest) <= 10:
            return True
    # Bare "X yojana/scheme" — not "which schemes" / disability / widow needs.
    if nlu.looks_like_scheme_ask(raw) and words <= 8 and not _VAGUE.search(raw):
        if (
            _WHAT_CAN_I_GET.search(raw)
            or _DISABILITY.search(raw)
            or _WIDOW.search(raw)
            or _PREGNANT.search(raw)
            or _LABOUR.search(raw)
            or _HOUSING.search(raw)
            or _RATION.search(raw)
        ):
            return False
        return True
    return False


def is_long_life_paragraph(text: str) -> bool:
    raw = text or ""
    if word_count(raw) < 16:
        return False
    n = _norm(raw)
    people = mentions_multiple_people(raw)
    role = bool(_FARMER.search(raw) or _LABOUR.search(raw) or nlu._map_alias(raw, nlu.OCCUPATION_ALIASES))
    age = bool(nlu.detect_age(raw))
    return people or (role and age) or (role and _WHAT_CAN_I_GET.search(raw) and word_count(raw) >= 20)


def skip_category_keyword(text: str) -> bool:
    """Category keywords inside a multi-person / multi-slot story yield to who-first."""
    if mentions_multiple_people(text) or is_profile_story(text):
        return True
    return False


def block_named_lookup(text: str) -> bool:
    """Do not treat this turn as a library identity search / miss."""
    if is_profile_story(text) or is_long_life_paragraph(text) or mentions_multiple_people(text):
        return True
    if is_vague_subsidy(text) and not looks_like_scheme_name_query(text):
        return True
    if detect_role_shortcut(text) and not looks_like_scheme_name_query(text):
        return True
    return False


def detect_role_shortcut(text: str) -> str | None:
    """Unambiguous single-role → category pack. Multi-person stories return None."""
    raw = (text or "").strip()
    if not raw:
        return None
    if mentions_multiple_people(raw):
        return None
    if looks_like_scheme_name_query(raw):
        return None
    # Widow / old-age pension
    if _WIDOW.search(raw) or _OLD_AGE_PENSION.search(raw):
        return "pension"
    if _DISABILITY.search(raw):
        return "disability"
    if _PREGNANT.search(raw):
        return "women_child"
    if _HOUSING.search(raw):
        if _KNOWN_SHORT_NAMES.search(raw) and word_count(raw) <= 3:
            return None
        return "housing"
    if _RATION.search(raw) and not is_profile_story(raw):
        return "food_ration"
    if _LABOUR.search(raw) and not _FARMER.search(raw):
        return "labour_bocw"
    if _FARMER.search(raw) and word_count(raw) <= 12 and not _WHAT_CAN_I_GET.search(raw):
        # Short "I am a farmer" can stay on the category keyword path.
        return None
    return None


def is_vague_subsidy(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    if looks_like_scheme_name_query(raw):
        return False
    if is_profile_story(raw) or mentions_multiple_people(raw):
        return False
    if category_intent.detect_category_intent(raw) and category_intent.is_bare_category_query(raw):
        return False
    if detect_role_shortcut(raw):
        return False
    if nlu.is_plain_menu_choice(raw):
        return False
    n = _norm(raw)
    if word_count(raw) > 22:
        return False
    if _VAGUE.search(raw) or _WHAT_CAN_I_GET.search(raw):
        # No who / what topic beyond generic scheme/subsidy
        if detect_role_shortcut(raw):
            return False
        if category_intent.detect_category_intent(raw):
            return False
        if any(p in n for p in ("wife", "child", "kids", "widow", "farmer", "house", "ration")):
            return False
        return True
    return False


def pack_for_me(signals: dict[str, Any] | None) -> str | None:
    """When the user picks ‘schemes for me’, map a single clear role onto a pack."""
    signals = signals or {}
    packs: list[str] = []
    if signals.get("farmer"):
        packs.append("agriculture")
    if signals.get("labour"):
        packs.append("labour_bocw")
    occ = signals.get("occupation")
    if occ == "Farmer" and "agriculture" not in packs:
        packs.append("agriculture")
    if occ == "Labourer" and "labour_bocw" not in packs:
        packs.append("labour_bocw")
    unique = list(dict.fromkeys(packs))
    if len(unique) == 1:
        return unique[0]
    return None


def pack_for_children(signals: dict[str, Any] | None) -> str:
    signals = signals or {}
    if signals.get("girl_child") and not signals.get("school_class"):
        return "women_child"
    return "education"


def ack_bits(signals: dict[str, Any] | None, language: str | None) -> str:
    signals = signals or {}
    bits: list[str] = []
    if signals.get("age"):
        bits.append(str(signals["age"]))
    else:
        age = signals.get("age_group")
        if age:
            bits.append(str(age))
    if signals.get("social_category"):
        bits.append(str(signals["social_category"]))
    if signals.get("farmer") or signals.get("occupation") == "Farmer":
        bits.append("farmer" if (language or "English") == "English" else "किसान")
    if signals.get("labour") or signals.get("occupation") == "Labourer":
        bits.append("daily-wage / labour")
    if signals.get("children"):
        bits.append("children")
    if signals.get("spouse"):
        bits.append("spouse")
    if not bits:
        return ""
    return ", ".join(bits)


def classify_free_text(text: str) -> str:
    """Return named_scheme | category | shortcut | who_first | vague | other."""
    raw = (text or "").strip()
    if looks_like_scheme_name_query(raw):
        return "named_scheme"
    if not skip_category_keyword(raw) and category_intent.detect_category_intent(raw):
        return "category"
    if detect_role_shortcut(raw):
        return "shortcut"
    if is_profile_story(raw) or mentions_multiple_people(raw):
        return "who_first"
    if is_vague_subsidy(raw):
        return "vague"
    return "other"
