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
    "vyaktigat": "Individual Schemes",
    "vyakti": "Individual Schemes",
    "व्यक्तिगत": "Individual Schemes",
    "वैयक्तिक": "Individual Schemes",
    "family schemes": "Family Schemes",
    "family": "Family Schemes",
    "household": "Family Schemes",
    "kutumb": "Family Schemes",
    "kutumba": "Family Schemes",
    "परिवार": "Family Schemes",
    "कुटुंब": "Family Schemes",
    "i need help": "I need help",
    "need help": "I need help",
    "help": "I need help",
    "support": "I need help",
    "मदत": "I need help",
    "मदद": "I need help",
    "browse category": "Browse by category",
    "browse by category": "Browse by category",
    "find by topic": "Browse by category",
    "browse by topic": "Browse by category",
    "by category": "Browse by category",
    "by topic": "Browse by category",
    "category": "Browse by category",
    "श्रेणी से खोजें": "Browse by category",
    "श्रेणी": "Browse by category",
    "विषय": "Browse by category",
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

FAMILY_OCCUPATIONS = {
    "Farmer",
    "Labourer",
    "Salaried",
    "Self-employed",
    "Unemployed",
    "Other",
}

HOUSING_ALIASES = {
    "own - pucca": "Own - Pucca",
    "own pucca": "Own - Pucca",
    "pucca": "Own - Pucca",
    "concrete": "Own - Pucca",
    "own - kutcha": "Own - Kutcha",
    "own kutcha": "Own - Kutcha",
    "kutcha": "Own - Kutcha",
    "kaccha": "Own - Kutcha",
    "kacha": "Own - Kutcha",
    "mud house": "Own - Kutcha",
    "rented": "Rented",
    "rent": "Rented",
    "tenant": "Rented",
    "on rent": "Rented",
    "homeless": "Homeless / No permanent housing",
    "no permanent housing": "Homeless / No permanent housing",
    "no permanent": "Homeless / No permanent housing",
    "no house": "Homeless / No permanent housing",
    "shelter": "Homeless / No permanent housing",
}

RATION_ALIASES = {
    "antyodaya (aay)": "Antyodaya (AAY)",
    "antyodaya": "Antyodaya (AAY)",
    "aay": "Antyodaya (AAY)",
    "yellow card": "Antyodaya (AAY)",
    "bpl": "BPL",
    "below poverty": "BPL",
    "below poverty line": "BPL",
    "aph": "BPL",
    "phh": "BPL",
    "apl": "APL",
    "above poverty": "APL",
    "above poverty line": "APL",
    "no ration": "None",
    "without ration": "None",
    "dont have ration": "None",
    "don't have ration": "None",
    "no card": "None",
    "none": "None",
    "not sure": "Not sure",
    "dont know": "Not sure",
    "don't know": "Not sure",
    "unsure": "Not sure",
}

COUNT_WORDS = {
    "zero": 0,
    "none": 0,
    "nil": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

COUNT_SLOTS = ("household_size", "children_under_18", "members_60_plus")

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


_NATIVE_LANGUAGE_NAMES = {
    "हिंदी": "Hindi",
    "हिन्दी": "Hindi",
    "मराठी": "Marathi",
    "ಕನ್ನಡ": "Kannada",
    "अंग्रेजी": "English",
    "इंग्रजी": "English",
    "ಇಂಗ್ಲಿಷ್": "English",
    "ಇಂಗ್ಲೀಷ್": "English",
}

_FULL_LANGUAGE_KEYS = ("english", "hindi", "marathi", "kannada")

_SWITCH_INTENT = re.compile(
    r"\b(switch|language|speak|talk|continue|reply|respond|change)\b",
    re.I,
)
_SWITCH_TO_LANG = re.compile(
    r"\b(?:switch|change|continue|talk|speak|reply|respond|use)"
    r"(?:\s+\w+){0,3}\s+(?:to|in|into)\s+"
    r"(english|hindi|marathi|kannada)\b",
    re.I,
)
_IN_TO_LANG = re.compile(r"\b(?:in|to|into)\s+(english|hindi|marathi|kannada)\b", re.I)


def detect_language(text: str) -> str | None:
    n = _norm(text)
    if n in LANGUAGE_MAP:
        return LANGUAGE_MAP[n]
    for native, val in _NATIVE_LANGUAGE_NAMES.items():
        if native in text:
            return val
    for key, val in sorted(LANGUAGE_MAP.items(), key=lambda kv: -len(kv[0])):
        if _contains_phrase(n, key):
            return val
    return None


def detect_language_switch(text: str) -> str | None:
    """Detect an explicit mid-flow language change.

    Bare language names count. Short codes (en/hi) only match as the whole message
    so they do not fire inside ordinary answers.
    """
    n = _norm(text)
    if not n:
        return None
    if n in LANGUAGE_MAP:
        return LANGUAGE_MAP[n]
    for native, val in _NATIVE_LANGUAGE_NAMES.items():
        if text.strip() == native:
            return val

    m = _SWITCH_TO_LANG.search(n)
    if m:
        return LANGUAGE_MAP[m.group(1).lower()]
    m = _IN_TO_LANG.search(n)
    if m and (_SWITCH_INTENT.search(n) or "back" in n):
        return LANGUAGE_MAP[m.group(1).lower()]

    has_intent = bool(_SWITCH_INTENT.search(n)) or any(
        p in text for p in ("भाषा", "में बात", "मध्ये", "ಮಾತನಾಡ")
    )
    if has_intent:
        for native, val in _NATIVE_LANGUAGE_NAMES.items():
            if native in text:
                return val
        for key in _FULL_LANGUAGE_KEYS:
            if _contains_phrase(n, key):
                return LANGUAGE_MAP[key]
    return None


def detect_menu(text: str) -> str | None:
    n = _norm(text)
    if n in ("1", "1)"):
        return "Individual Schemes"
    if n in ("2", "2)"):
        return "Family Schemes"
    if n in ("3", "3)"):
        return "Browse by category"
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


def detect_yes_no(
    text: str,
    *,
    unsure_label: str | None = None,
) -> str | None:
    """Map yes / no / prefer-not / optional not-sure answers."""
    n = _norm(text)
    if "prefer not" in n:
        return "Prefer not to say"
    if unsure_label and any(
        p in n for p in ("not sure", "unsure", "dont know", "don't know", "no idea")
    ):
        return unsure_label
    if n in ("yes", "y") or n.startswith("yes "):
        return "Yes"
    if n in ("no", "n") or n.startswith("no "):
        return "No"
    return None


def detect_count(
    text: str,
    *,
    prefer: bool = False,
    kind: str | None = None,
) -> str | None:
    """Extract a household count, including 0.

    Bare numbers (and bare "no"/"none"/"zero") are used only when this is the
    preferred slot. Opportunistic extraction requires a contextual phrase.
    """
    n = _norm(text)

    none_phrases = {
        "children": (
            "no children",
            "no kids",
            "no child",
            "without children",
            "without kids",
            "dont have kids",
            "don't have kids",
            "don't have children",
            "no minors",
        ),
        "elders": (
            "no elders",
            "no elder",
            "no seniors",
            "no senior",
            "nobody over 60",
            "no one over 60",
            "none over 60",
            "no members 60",
        ),
        "household": (
            "no one else",
            "just me",
            "only me",
            "live alone",
            "staying alone",
        ),
    }
    if kind and any(p in n for p in none_phrases.get(kind, ())):
        return "1" if kind == "household" else "0"
    if prefer and kind != "household" and n in ("none", "zero", "nil"):
        return "0"

    contextual = False
    if kind == "children" and any(
        p in n for p in ("child", "kid", "minor", "under 18", "below 18")
    ):
        contextual = True
    elif kind == "elders" and any(
        p in n
        for p in ("elder", "senior", "60", "sixty", "old age", "elderly", "grandparent")
    ):
        contextual = True
    elif kind == "household" and any(
        p in n
        for p in (
            "household",
            "family of",
            "people",
            "members",
            "of us",
            "in our family",
            "in the family",
            "live with",
        )
    ):
        contextual = True

    m = re.search(r"\b(\d{1,2})\b", n)
    if m:
        num = int(m.group(1))
        if 0 <= num <= 30 and (prefer or contextual):
            return str(num)

    for word, val in COUNT_WORDS.items():
        if word in ("none", "nil", "zero") and kind == "household" and not prefer:
            continue
        if _contains_phrase(n, word) and (prefer or contextual):
            if 0 <= val <= 30:
                return str(val)

    if prefer and kind in ("children", "elders") and n in ("no", "n"):
        return "0"
    return None


def detect_housing(text: str, *, prefer: bool = False) -> str | None:
    mapped = _map_alias(text, HOUSING_ALIASES)
    if mapped:
        return mapped
    n = _norm(text)
    if prefer and n == "other":
        return "Other"
    if prefer and n in ("own", "owned", "we own"):
        return "Own - Pucca"
    return None


def detect_ration(text: str, *, prefer: bool = False) -> str | None:
    n = _norm(text)
    generic = {"none", "other", "not sure", "dont know", "don't know", "unsure", "no card"}
    if not prefer and n in generic:
        return None
    mapped = _map_alias(text, RATION_ALIASES)
    if mapped:
        if not prefer and mapped in ("None", "Other", "Not sure"):
            return None
        return mapped
    if prefer and n == "other":
        return "Other"
    return None


def detect_insurance(text: str, *, prefer: bool = False) -> str | None:
    n = _norm(text)
    if prefer and any(p in n for p in ("not sure", "unsure", "dont know", "don't know")):
        return "Not sure"
    if any(
        p in n
        for p in (
            "no insurance",
            "uninsured",
            "without insurance",
            "don't have insurance",
            "dont have insurance",
            "no cover",
        )
    ):
        return "No"
    if any(
        p in n
        for p in (
            "have insurance",
            "insured",
            "ayushman",
            "pmjay",
            "pm-jay",
            "health cover",
        )
    ):
        return "Yes"
    if prefer:
        return detect_yes_no(text, unsure_label="Not sure")
    return None


def detect_pregnant(text: str, *, prefer: bool = False) -> str | None:
    n = _norm(text)
    if prefer and "prefer not" in n:
        return "Prefer not to say"
    maternal = any(
        p in n
        for p in ("pregnant", "pregnan", "breastfeed", "lactat", "expecting", "nursing")
    )
    if maternal:
        if any(p in n for p in ("not pregnant", "not breastfeeding", "no one", "nobody")):
            return "No"
        return "Yes"
    if prefer:
        return detect_yes_no(text)
    return None


def detect_family_disability(text: str, *, prefer: bool = False) -> str | None:
    if prefer:
        return detect_disability(text)
    n = _norm(text)
    if any(
        p in n
        for p in (
            "no disability",
            "not disabled",
            "without disability",
            "nobody disabled",
            "no one disabled",
        )
    ):
        return "No"
    if any(
        p in n
        for p in (
            "have a disability",
            "has a disability",
            "disabled",
            "with disability",
            "pwd",
            "divyang",
        )
    ):
        return "Yes"
    if prefer and "prefer not" in n:
        return "Prefer not to say"
    return None


def detect_primary_occupation(text: str) -> str | None:
    v = _map_alias(text, OCCUPATION_ALIASES)
    if v in FAMILY_OCCUPATIONS:
        return v
    if v:
        return "Other"
    if _norm(text) == "other":
        return "Other"
    return None


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
    elif prefer_slot == "household_size":
        v = detect_count(text, prefer=True, kind="household")
        if v is not None:
            found["household_size"] = v
    elif prefer_slot == "children_under_18":
        v = detect_count(text, prefer=True, kind="children")
        if v is not None:
            found["children_under_18"] = v
    elif prefer_slot == "members_60_plus":
        v = detect_count(text, prefer=True, kind="elders")
        if v is not None:
            found["members_60_plus"] = v
    elif prefer_slot == "family_disability":
        v = detect_family_disability(text, prefer=True)
        if v:
            found["family_disability"] = v
    elif prefer_slot == "pregnant_or_breastfeeding":
        v = detect_pregnant(text, prefer=True)
        if v:
            found["pregnant_or_breastfeeding"] = v
    elif prefer_slot == "primary_occupation":
        v = detect_primary_occupation(text)
        if v:
            found["primary_occupation"] = v
    elif prefer_slot == "housing":
        v = detect_housing(text, prefer=True)
        if v:
            found["housing"] = v
    elif prefer_slot == "ration_card":
        v = detect_ration(text, prefer=True)
        if v:
            found["ration_card"] = v
    elif prefer_slot == "has_insurance":
        v = detect_insurance(text, prefer=True)
        if v:
            found["has_insurance"] = v

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
    fam_occ = detect_primary_occupation(text)
    if fam_occ:
        found["primary_occupation"] = fam_occ
    income = detect_income(text)
    if income and (prefer_slot == "household_income" or income != "Prefer not to say"):
        found["household_income"] = income
    cat = _map_alias(text, CATEGORY_ALIASES)
    if cat:
        found["social_category"] = cat
    marital = _map_alias(text, MARITAL_ALIASES)
    if marital and (prefer_slot == "marital_status" or marital != "Prefer not to say"):
        found["marital_status"] = marital
    disability = detect_disability(text)
    if disability:
        found["disability"] = disability
    # Family extractors: contextual only (no bare yes/no or bare numbers)
    hh = detect_count(text, prefer=False, kind="household")
    if hh is not None:
        found["household_size"] = hh
    kids = detect_count(text, prefer=False, kind="children")
    if kids is not None:
        found["children_under_18"] = kids
    elders = detect_count(text, prefer=False, kind="elders")
    if elders is not None:
        found["members_60_plus"] = elders
    fam_dis = detect_family_disability(text, prefer=False)
    if fam_dis:
        found["family_disability"] = fam_dis
    pregnant = detect_pregnant(text, prefer=False)
    if pregnant:
        found["pregnant_or_breastfeeding"] = pregnant
    housing = detect_housing(text, prefer=False)
    if housing:
        found["housing"] = housing
    ration = detect_ration(text, prefer=False)
    if ration:
        found["ration_card"] = ration
    insurance = detect_insurance(text, prefer=False)
    if insurance:
        found["has_insurance"] = insurance

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
    if "go back" in n or n in ("back", "go back"):
        return "Go Back"
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
