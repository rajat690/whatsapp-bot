"""Lightweight intent + slot extraction (no LLM required)."""

from __future__ import annotations

import re
from typing import Any

LANGUAGE_MAP = {
    "english": "English",
    "eng": "English",
    "en": "English",
    "hindi": "Hindi",
    "hin": "Hindi",
    "hi": "Hindi",
    "marathi": "Marathi",
    "mar": "Marathi",
    "mr": "Marathi",
    "kannada": "Kannada",
    "kan": "Kannada",
    "kn": "Kannada",
}

MENU_MAP = {
    "individual schemes": "Individual Schemes",
    "individual": "Individual Schemes",
    "myself": "Individual Schemes",
    "for me": "Individual Schemes",
    "personal": "Individual Schemes",
    "family schemes": "Family Schemes",
    "family": "Family Schemes",
    "household": "Family Schemes",
    "i need help": "I need help",
    "need help": "I need help",
    "help": "I need help",
    "support": "I need help",
}

AGE_MAP = {
    "0-17": "0–17",
    "0–17": "0–17",
    "under 18": "0–17",
    "below 18": "0–17",
    "child": "0–17",
    "minor": "0–17",
    "18-59": "18–59",
    "18–59": "18–59",
    "adult": "18–59",
    "working age": "18–59",
    "60+": "60+",
    "60 plus": "60+",
    "senior": "60+",
    "elderly": "60+",
    "old age": "60+",
}

OCCUPATION_ALIASES = {
    "farmer": "Farmer",
    "farming": "Farmer",
    "agriculture": "Farmer",
    "labourer": "Labourer",
    "laborer": "Labourer",
    "labour": "Labourer",
    "daily wage": "Labourer",
    "salaried": "Salaried",
    "private job": "Salaried",
    "employee": "Salaried",
    "self-employed": "Self-employed",
    "self employed": "Self-employed",
    "business": "Self-employed",
    "student": "Student",
    "unemployed": "Unemployed",
    "jobless": "Unemployed",
    "homemaker": "Homemaker",
    "housewife": "Homemaker",
    "retired": "Retired",
}

INCOME_ALIASES = {
    "up to 10000": "Up to ₹10,000",
    "upto 10000": "Up to ₹10,000",
    "under 10000": "Up to ₹10,000",
    "below 10000": "Up to ₹10,000",
    "10k": "Up to ₹10,000",
    "10001-30000": "₹10,001–₹30,000",
    "10k-30k": "₹10,001–₹30,000",
    "25000": "₹10,001–₹30,000",
    "30001-50000": "₹30,001–₹50,000",
    "30k-50k": "₹30,001–₹50,000",
    "above 50000": "Above ₹50,000",
    "above 50k": "Above ₹50,000",
    "prefer not to say": "Prefer not to say",
    "prefer not": "Prefer not to say",
}

CATEGORY_ALIASES = {
    "scheduled caste": "SC",
    "sc": "SC",
    "scheduled tribe": "ST",
    "st": "ST",
    "obc": "OBC",
    "general": "General",
    "gen": "General",
    "minority": "Minority",
}

MARITAL_ALIASES = {
    "unmarried": "Single",
    "single": "Single",
    "married": "Married",
    "widowed": "Widowed",
    "widow": "Widowed",
    "widower": "Widowed",
    "divorced": "Divorced / Separated",
    "separated": "Divorced / Separated",
    "prefer not to say": "Prefer not to say",
}

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh",
]


def _norm(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("₹", "").replace(",", "")
    text = re.sub(r"\s+", " ", text)
    return text


def _contains_phrase(haystack: str, needle: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _map_alias(text: str, aliases: dict[str, str]) -> str | None:
    n = _norm(text)
    # Longer keys first to avoid partial traps
    for key, val in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        if n == key or _contains_phrase(n, key):
            return val
    return None


def detect_language(text: str) -> str | None:
    n = _norm(text)
    if n in LANGUAGE_MAP:
        return LANGUAGE_MAP[n]
    for key, val in sorted(LANGUAGE_MAP.items(), key=lambda kv: -len(kv[0])):
        if _contains_phrase(n, key):
            return val
    return None


def detect_menu(text: str) -> str | None:
    n = _norm(text)
    for key, val in sorted(MENU_MAP.items(), key=lambda kv: -len(kv[0])):
        if n == key or _contains_phrase(n, key):
            return val
    return None


def detect_state(text: str) -> str | None:
    n = _norm(text)
    for state in INDIAN_STATES:
        if _norm(state) in n or n == _norm(state):
            return state
    aliases = {
        "karnataka": "Karnataka",
        "bengaluru": "Karnataka",
        "bangalore": "Karnataka",
        "maharashtra": "Maharashtra",
        "mumbai": "Maharashtra",
        "delhi": "Delhi",
        "tamil nadu": "Tamil Nadu",
        "uttar pradesh": "Uttar Pradesh",
    }
    for key, val in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        if n == key or _contains_phrase(n, key):
            return val
    return None


def detect_disability(text: str) -> str | None:
    n = _norm(text)
    if any(p in n for p in ("no disability", "not disabled", "without disability", "don't have")):
        return "No"
    if any(p in n for p in ("have a disability", "i am disabled", "i'm disabled", "with disability")):
        return "Yes"
    if n in ("yes", "y"):
        return "Yes"
    if n in ("no", "n"):
        return "No"
    if "prefer not" in n:
        return "Prefer not to say"
    return None


def detect_age(text: str) -> str | None:
    mapped = _map_alias(text, AGE_MAP)
    if mapped:
        return mapped
    n = _norm(text)
    m = re.search(r"\b(\d{1,3})\s*(years?|yrs?|yo|y\.o\.?)?\b", n)
    if not m:
        return None
    age_num = int(m.group(1))
    # Ignore tiny numbers unless explicit age unit (avoids "1" / rating confusion)
    has_unit = bool(m.group(2))
    if not has_unit and age_num < 10:
        return None
    if age_num > 120:
        return None
    if age_num < 18:
        return "0–17"
    if age_num < 60:
        return "18–59"
    return "60+"


def detect_income(text: str) -> str | None:
    mapped = _map_alias(text, INCOME_ALIASES)
    if mapped:
        return mapped
    n = _norm(text)
    # Pull first 4-7 digit amount anywhere
    m = re.search(r"(\d{4,7})", n.replace(" ", ""))
    if not m:
        # also try original with spaces: 25 000
        m = re.search(r"(\d{2,3})\s*(\d{3})", n)
        if m:
            amt = int(m.group(1) + m.group(2))
        else:
            return None
    else:
        amt = int(m.group(1))
    if amt <= 10000:
        return "Up to ₹10,000"
    if amt <= 30000:
        return "₹10,001–₹30,000"
    if amt <= 50000:
        return "₹30,001–₹50,000"
    return "Above ₹50,000"


def extract_slots(
    text: str,
    slot_defs: list[dict[str, Any]],
    prefer_slot: str | None = None,
) -> dict[str, str]:
    """Extract known slots from free text.

    If prefer_slot is set (current question), bias mapping toward that slot.
    """
    found: dict[str, str] = {}
    allowed = {s["id"] for s in slot_defs}

    # Preferred single-slot handling first
    if prefer_slot == "state":
        v = detect_state(text)
        if v:
            found["state"] = v
    elif prefer_slot == "age_group":
        v = detect_age(text)
        if v:
            found["age_group"] = v
    elif prefer_slot == "occupation":
        v = _map_alias(text, OCCUPATION_ALIASES)
        if v:
            found["occupation"] = v
        elif _norm(text) == "other" or _norm(text) == "job":
            found["occupation"] = "Other" if _norm(text) == "other" else "Salaried"
    elif prefer_slot == "household_income":
        v = detect_income(text)
        if v:
            found["household_income"] = v
    elif prefer_slot == "social_category":
        v = _map_alias(text, CATEGORY_ALIASES)
        if v:
            found["social_category"] = v
    elif prefer_slot == "marital_status":
        v = _map_alias(text, MARITAL_ALIASES)
        if v:
            found["marital_status"] = v
    elif prefer_slot == "disability":
        v = detect_disability(text)
        if v:
            found["disability"] = v

    # Opportunistic multi-slot fill (safe extractors only)
    state = detect_state(text)
    if state:
        found["state"] = state
    age = detect_age(text)
    if age:
        found["age_group"] = age
    occ = _map_alias(text, OCCUPATION_ALIASES)
    if occ:
        found["occupation"] = occ
    income = detect_income(text)
    if income:
        found["household_income"] = income
    cat = _map_alias(text, CATEGORY_ALIASES)
    if cat:
        found["social_category"] = cat
    marital = _map_alias(text, MARITAL_ALIASES)
    if marital:
        found["marital_status"] = marital
    disability = detect_disability(text)
    if disability:
        found["disability"] = disability

    return {k: v for k, v in found.items() if k in allowed}


def detect_confirm(text: str) -> str | None:
    n = _norm(text)
    if n in ("proceed", "yes", "confirm", "looks good", "ok", "okay", "correct", "y"):
        return "Proceed"
    if n in ("edit", "edit details", "change", "correct details"):
        return "Edit details"
    if "edit" in n or "change" in n:
        return "Edit details"
    if "proceed" in n or "confirm" in n:
        return "Proceed"
    return None


def detect_rating(text: str) -> int | None:
    n = _norm(text)
    m = re.fullmatch(r"[1-5]", n)
    if m:
        return int(m.group(0))
    m = re.search(r"\b([1-5])\b", n)
    if m and not re.search(r"\d{2,}", n):
        return int(m.group(1))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    for w, v in words.items():
        if _contains_phrase(n, w):
            return v
    return None


def detect_end_choice(text: str) -> str | None:
    n = _norm(text)
    if "main menu" in n or n in ("menu", "start over", "restart"):
        return "Main Menu"
    if "end" in n or n in ("bye", "goodbye", "exit", "stop"):
        return "End Chat"
    return None


def detect_after_scheme(text: str) -> str | None:
    n = _norm(text)
    if "help" in n or "support" in n:
        return "I need help"
    if "other" in n or "list" in n or "back" in n or "more schemes" in n:
        return "View other schemes"
    return None


def match_scheme_choice(text: str, schemes: list[dict[str, Any]]) -> dict[str, Any] | None:
    n = _norm(text)
    m = re.fullmatch(r"(\d{1,2})", n)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(schemes):
            return schemes[idx]
    for scheme in schemes:
        name = _norm(str(scheme.get("Scheme Name", "")))
        sn = str(scheme.get("SN", ""))
        if name and (name in n or n in name):
            return scheme
        if sn and n == sn:
            return scheme
    return None
