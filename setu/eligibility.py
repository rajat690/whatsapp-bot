"""Deterministic scheme eligibility matching. Library JSON stays English.

Hard gates (age / income / gender / category / occupation windows) exclude a scheme
before any keyword boost. Soft scores never override a hard fail. Exact `slots["age"]`
from free text is preferred over the coarse age_group bucket.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import i18n, translate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

STATE_TO_FILE = {
    "karnataka": "schemes_karnataka.json",
    "maharashtra": "schemes_maharashtra.json",
}

_STATE_ALIASES = {
    "karnataka": "karnataka",
    "maharashtra": "maharashtra",
    "maharastra": "maharashtra",
}

_STATE_DISPLAY = {
    "karnataka": "Karnataka",
    "maharashtra": "Maharashtra",
}


def _load_json(name: str) -> dict[str, Any]:
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _load_library(filename: str, library: str) -> list[dict[str, Any]]:
    schemes = _load_json(filename).get("schemes", [])
    for s in schemes:
        s.setdefault("_library", library)
    return schemes


def _load_central() -> list[dict[str, Any]]:
    return _load_library("schemes_central.json", "Central")


def _load_state_library(state: str) -> list[dict[str, Any]]:
    state_l = (state or "").strip().lower()
    state_file = STATE_TO_FILE.get(state_l)
    if not state_file or not (DATA_DIR / state_file).exists():
        return []
    return _load_library(state_file, state)


def _canon_state_key(state: str | None) -> str:
    raw = (state or "").strip()
    return _STATE_ALIASES.get(raw.lower(), raw.lower())


def load_scheme_pool(state: str | None) -> tuple[list[dict[str, Any]], str]:
    """Return schemes to search + a short scope note for the user."""
    central = _load_central()

    key = _canon_state_key(state)
    state_file = STATE_TO_FILE.get(key)
    if state_file and (DATA_DIR / state_file).exists():
        display = _STATE_DISPLAY.get(key) or (state or "").strip() or key
        state_schemes = _load_state_library(display)
        note = f"Matching Central + {display} schemes."
        return central + state_schemes, note

    if state:
        note = (
            f"Matching Central schemes only — no dedicated library yet for {state}. "
            "Karnataka and Maharashtra state libraries are available."
        )
    else:
        note = "Matching Central schemes (state not set)."
    return central, note


def load_scheme_pool_by_scope(
    scope: str | None,
    state: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Category-path library selection. Does not change Journey 1/2 matching."""
    scope_l = (scope or "").strip().lower()
    state_name = (state or "").strip()

    if scope_l == "central":
        return _load_central(), "Matching Central schemes only."

    if scope_l == "karnataka":
        schemes = _load_state_library("Karnataka")
        return schemes, "Matching Karnataka schemes."

    if scope_l == "maharashtra":
        schemes = _load_state_library("Maharashtra")
        return schemes, "Matching Maharashtra schemes."

    if scope_l == "state_central":
        return load_scheme_pool(state_name or None)

    return load_scheme_pool(state_name or None)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_optional_int(value: Any) -> int | None:
    if value in (None, "", "null", "unknown"):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# Hard eligibility: numeric / categorical windows parsed from scheme text.
# Soft keyword boosts must never override these gates.


def parse_age_window(age_crit: str | None) -> dict[str, Any] | None:
    """Parse Age Criteria into an entry window {min, max} (inclusive).

    'Entry 18–40; pension from 60' is an 18–40 entry gate, not a 60+ scheme.
    Returns None when the text has no usable numeric/adult/child window.
    """
    raw = (age_crit or "").strip()
    if not raw:
        return None
    t = raw.lower().replace("—", "-").replace("–", "-").replace(" to ", "-")
    if re.search(
        r"no (?:fixed |official |general |rigid )?age|not age[- ]based|"
        r"no age restriction|not applicable|not individual",
        t,
    ):
        return None
    # Pension commencement is not the entry window.
    t = re.sub(r"pension from(?: age)?\s*\d+", " ", t)
    t = re.sub(r"renewable up to\s*\d+", " ", t)

    entry = re.search(r"entry(?: age)?(?:[:\s]+| of )(\d{1,3})\s*-\s*(\d{1,3})", t)
    if entry:
        lo, hi = int(entry.group(1)), int(entry.group(2))
        if 0 <= lo <= hi <= 120:
            return {"min": lo, "max": hi}

    at_entry = re.search(r"(\d{1,3})\s*-\s*(\d{1,3})\s*(?:years?)?\s*at entry", t)
    if at_entry:
        lo, hi = int(at_entry.group(1)), int(at_entry.group(2))
        if 0 <= lo <= hi <= 120:
            return {"min": lo, "max": hi}

    ranges = re.findall(r"(\d{1,3})\s*-\s*(\d{1,3})", t)
    if ranges:
        lo, hi = int(ranges[0][0]), int(ranges[0][1])
        if 0 <= lo <= hi <= 120:
            return {"min": lo, "max": hi}

    under = re.search(r"(?:below|under)\s+(\d{1,3})", t)
    if under:
        hi = int(under.group(1)) - 1
        if 0 <= hi <= 120:
            return {"min": 0, "max": hi}

    upto = re.search(r"(?:up to|upto|max(?:imum)?)\s+(\d{1,3})", t)
    if upto:
        hi = int(upto.group(1))
        if 0 <= hi <= 120:
            return {"min": 0, "max": hi}

    plus = re.search(
        r"(?:aged|age)\s+(\d{1,3})\s*\+|(\d{1,3})\s*\+|"
        r"(\d{1,3})\s+years?\s+and above|persons aged\s+(\d{1,3})",
        t,
    )
    if plus:
        n = int(next(g for g in plus.groups() if g))
        if 0 <= n <= 120:
            return {"min": n, "max": None}

    above = re.search(r"(?:above|over|older than)\s+(\d{1,3})", t)
    if above:
        n = int(above.group(1))
        if 0 <= n <= 120:
            return {"min": n, "max": None}

    if re.search(r"\b(child|children|girl child|adolescent)\b", t) and not re.search(
        r"\b(adult|18\+|working[- ]age)\b", t
    ):
        return {"min": 0, "max": 17, "child_only": True}

    if re.search(r"\b(senior|old age|elderly)\b", t) and not re.search(
        r"\b(18|entry|working)\b", t
    ):
        return {"min": 60, "max": None, "senior_only": True}

    if re.search(r"\b(adult|18\+|typically 18)\b", t):
        return {"min": 18, "max": None}

    return None


def _user_age_span(slots: dict[str, str]) -> tuple[int | None, int | None, int | None]:
    """(exact, lo, hi) for the user. Overlapping spans are not hard-failed."""
    exact = _as_optional_int(slots.get("age"))
    if exact is not None and 0 <= exact <= 120:
        return exact, exact, exact

    band = (slots.get("age_band") or "").strip()
    group = (slots.get("age_group") or "").strip()
    if band == "under_40":
        return None, 18, 39
    if band == "40_59":
        return None, 40, 59
    if band in ("60_79",):
        return None, 60, 79
    if band in ("80_plus",):
        return None, 80, 120
    if group.startswith("0") or group == "0–17":
        return None, 0, 17
    if "60+" in group:
        return None, 60, 120
    if group in ("18–59", "18-59") or group.startswith("18"):
        return None, 18, 59
    return None, None, None


def _age_hard_incompatible(scheme: dict[str, Any], slots: dict[str, str]) -> bool:
    window = parse_age_window(scheme.get("Age Criteria"))
    if not window:
        return False
    exact, ulo, uhi = _user_age_span(slots)
    smin = window.get("min")
    smax = window.get("max")
    if exact is not None:
        if smin is not None and exact < smin:
            return True
        if smax is not None and exact > smax:
            return True
        return False
    if ulo is None or uhi is None:
        return False
    # Entire user bucket sits outside the scheme window.
    if smin is not None and uhi < smin:
        return True
    if smax is not None and ulo > smax:
        return True
    return False


def _user_monthly_floor(slots: dict[str, str]) -> int | None:
    """Lowest monthly income consistent with the collected band."""
    hh = slots.get("household_income") or ""
    if "Above" in hh or "above ₹50" in hh.lower() or "above 50" in hh.lower():
        return 50001
    if "30,001" in hh or "30001" in hh or "₹30,001" in hh:
        return 30001
    if "10,001" in hh or "10001" in hh or "₹10,001" in hh:
        return 10001
    return None


def _scheme_monthly_ceiling(income_crit: str | None) -> int | None:
    t = (income_crit or "").lower().replace(",", "")
    if not t or "no income" in t or "no uniform" in t or "no formal" in t:
        return None
    m = re.search(
        r"monthly income\s*(?:≤|<=|=<|less than or equal to|upto|up to)?\s*₹?\s*(\d+)",
        t,
    )
    if m:
        return int(m.group(1))
    m = re.search(r"≤\s*₹\s*(\d+)", t)
    if m and "monthly" in t:
        return int(m.group(1))
    return None


def _scheme_annual_ceiling(income_crit: str | None) -> int | None:
    t = (income_crit or "").lower().replace(",", "")
    if not t or "no income" in t:
        return None
    if not re.search(r"annual|year|lakh|parental", t):
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*lakh", t)
    if m:
        return int(float(m.group(1)) * 100000)
    m = re.search(r"₹\s*(\d{5,7})", t)
    if m:
        return int(m.group(1))
    return None


def _income_hard_incompatible(scheme: dict[str, Any], slots: dict[str, str]) -> bool:
    floor = _user_monthly_floor(slots)
    if floor is None:
        return False
    monthly = _scheme_monthly_ceiling(scheme.get("Income Criteria"))
    if monthly is not None and floor > monthly:
        return True
    annual = _scheme_annual_ceiling(scheme.get("Income Criteria"))
    if annual is not None and floor * 12 > annual:
        return True
    return False


def _scheme_required_gender(scheme: dict[str, Any]) -> str | None:
    gender_crit = (scheme.get("Gender / Category Criteria") or "").lower()
    age_crit = (scheme.get("Age Criteria") or "").lower()
    category = (scheme.get("Category") or "").lower()
    if "no gender restriction" in gender_crit:
        return None
    blob = f"{gender_crit} {age_crit} {category}"
    if re.search(
        r"girl child|women only|only (?:for )?women|woman of the household|"
        r"adult woman|women \(pregnant|pregnant and lactating women|"
        r"woman applicant",
        blob,
    ):
        return "female"
    if re.search(r"\bmen only\b|only (?:for )?men\b|male only", blob):
        return "male"
    return None


def _gender_hard_incompatible(scheme: dict[str, Any], slots: dict[str, str]) -> bool:
    required = _scheme_required_gender(scheme)
    if not required:
        return False
    gender = (slots.get("gender") or "").strip().lower()
    if not gender:
        return False
    if required == "female" and gender == "male":
        return True
    if required == "male" and gender == "female":
        return True
    return False


def _scheme_minority_only(scheme: dict[str, Any]) -> bool:
    category = (scheme.get("Category") or "").lower()
    gender_crit = (scheme.get("Gender / Category Criteria") or "").lower()
    other = (scheme.get("Other Key Eligibility Criteria") or "").lower()
    age_crit = (scheme.get("Age Criteria") or "").lower()
    blob = f"{category} {gender_crit} {other} {age_crit}"
    if re.search(r"only (?:for )?minorit", blob):
        return True
    if "minority" in category and re.search(
        r"scholarship|minority students|minority communit", blob
    ):
        return True
    return False


def _category_hard_incompatible(scheme: dict[str, Any], slots: dict[str, str]) -> bool:
    social = (slots.get("social_category") or "").strip().lower()
    if _scheme_minority_only(scheme) and social and social not in ("minority", "muslim"):
        return True
    return False


def _scheme_student_only(scheme: dict[str, Any]) -> bool:
    category = (scheme.get("Category") or "").lower()
    age_crit = (scheme.get("Age Criteria") or "").lower()
    name = (scheme.get("Scheme Name") or "").lower()
    if "scholarship" in category or "scholarship" in name:
        return True
    if re.search(r"\bstudents?\b", age_crit) and "education" in category:
        return True
    return False


def _scheme_farmer_only(scheme: dict[str, Any]) -> bool:
    name = (scheme.get("Scheme Name") or "").lower()
    gender_crit = (scheme.get("Gender / Category Criteria") or "").lower()
    age_crit = (scheme.get("Age Criteria") or "").lower()
    if "pm-kisan" in name or "kisan maandhan" in name or "pm-kmy" in name:
        return True
    if "landholding" in gender_crit and "farmer" in gender_crit:
        return True
    if re.search(r"farmer/cultivator|landholding farmer|landholder.*farmer|farmer.*landholder", f"{gender_crit} {age_crit}"):
        return True
    return False


def _occupation_hard_incompatible(scheme: dict[str, Any], slots: dict[str, str]) -> bool:
    occ = (slots.get("occupation") or slots.get("primary_occupation") or "").strip().lower()
    if not occ:
        return False
    if _scheme_student_only(scheme) and occ not in ("student",):
        # Household may still claim a child scholarship.
        if _as_int(slots.get("children_under_18")) > 0:
            return False
        if (slots.get("who") or "") in ("girl_child",) or slots.get("health_who") == "child":
            return False
        return True
    if _scheme_farmer_only(scheme) and occ not in ("farmer",):
        return True
    return False


def is_hard_ineligible(scheme: dict[str, Any], slots: dict[str, str] | None) -> bool:
    """True when a known user fact is outside a clear scheme window."""
    filled = slots or {}
    return (
        _age_hard_incompatible(scheme, filled)
        or _income_hard_incompatible(scheme, filled)
        or _gender_hard_incompatible(scheme, filled)
        or _category_hard_incompatible(scheme, filled)
        or _occupation_hard_incompatible(scheme, filled)
    )


def _family_to_individual_slots(slots: dict[str, str]) -> dict[str, str]:
    """Map Journey 2 household fields onto Journey 1 scorer inputs."""
    mapped = dict(slots)
    if slots.get("primary_occupation") and not mapped.get("occupation"):
        mapped["occupation"] = slots["primary_occupation"]
    if slots.get("family_disability") and not mapped.get("disability"):
        mapped["disability"] = slots["family_disability"]
    return mapped


def _score_scheme(scheme: dict[str, Any], slots: dict[str, str]) -> tuple[int, list[str]]:
    if is_hard_ineligible(scheme, slots):
        return 0, []

    score = 0
    reasons: list[str] = []

    age = slots.get("age_group", "")
    age_crit = (scheme.get("Age Criteria") or "").lower()
    gender_crit = (scheme.get("Gender / Category Criteria") or "").lower()
    other = (scheme.get("Other Key Eligibility Criteria") or "").lower()
    income_crit = (scheme.get("Income Criteria") or "").lower()
    category = (scheme.get("Category") or "").lower()
    social = (slots.get("social_category") or "").lower()
    marital = (slots.get("marital_status") or "").lower()
    disability = (slots.get("disability") or "").lower()
    occupation = (slots.get("occupation") or "").lower()
    income = (slots.get("household_income") or "").lower()
    library = (scheme.get("_library") or "").lower()
    name = (scheme.get("Scheme Name") or "").lower()

    # Prefer state schemes slightly when state matches library
    state = (slots.get("state") or "").lower()
    if state and library == state:
        score += 1

    # Age heuristics
    if age == "60+" or "60+" in age:
        if any(x in age_crit for x in ("60", "65", "old age", "senior")):
            score += 4
            reasons.append("age")
        if "pension" in category or "old age" in category:
            score += 2
    elif age.startswith("0"):
        if any(x in age_crit for x in ("child", "birth", "11", "school", "adolescent", "girl")):
            score += 3
            reasons.append("age")
        if any(x in category for x in ("child", "girl", "adolescent", "nutrition")):
            score += 2
    else:  # 18-59
        if any(x in age_crit for x in ("adult", "working", "no age", "no fixed", "scheme-specific", "course", "21")):
            score += 1
        if age_crit.strip() in ("60+", "65+") or ("60" in age_crit and "18" not in age_crit and "21" not in age_crit):
            # Hard old-age-only schemes
            if "60" in age_crit and "to" not in age_crit and "–" not in age_crit and "-" not in age_crit.replace("60-", ""):
                score -= 2

    # Social category
    if social == "sc":
        if "sc" in gender_crit or "sc" in other or "sc welfare" in category or "scheduled caste" in other:
            score += 4
            reasons.append("SC")
    elif social == "st":
        if "st" in gender_crit or "tribal" in category or "scheduled tribe" in other or "st welfare" in category:
            score += 4
            reasons.append("ST")
    elif social == "obc":
        if "backward" in category or "obc" in gender_crit or "backward" in other or "obc" in other:
            score += 4
            reasons.append("OBC")
    elif social in ("minority", "muslim"):
        minority_hit = any(
            x in category or x in gender_crit or x in other or x in name
            for x in ("minority", "muslim", "christian", "sikh", "buddhist", "jain", "parsi")
        )
        if minority_hit:
            score += 5
            reasons.append("Minority")

    # Gender / marital / disability
    if marital == "widowed" and "widow" in gender_crit:
        score += 5
        reasons.append("widow")
    if disability == "yes" and ("disabilit" in gender_crit or "disabilit" in other or "disabilit" in category):
        score += 5
        reasons.append("disability")

    # Occupation
    if occupation == "farmer" and (
        "agricultur" in category or "farmer" in gender_crit or "farmer" in other or "crop" in category or "kisan" in (scheme.get("Scheme Name") or "").lower()
    ):
        score += 4
        reasons.append("farmer")
    if occupation == "student" and "education" in category:
        score += 3
        reasons.append("student")
    if occupation == "unemployed" and ("unemployment" in category or "yuva" in (scheme.get("Scheme Name") or "").lower()):
        score += 4
        reasons.append("unemployed")
    if occupation == "labourer" and ("labour" in category or "bocw" in other or "construction" in category or "worker" in category):
        score += 4
        reasons.append("labour")
    if occupation == "retired" and "pension" in category:
        score += 3
        reasons.append("retired")

    # Income / BPL-ish
    hh = slots.get("household_income") or ""
    if "Up to ₹10,000" in hh or "up to" in income:
        if any(x in income_crit for x in ("bpl", "aay", "income ceiling", "income limit", "poverty", "2.50", "1 lakh", "≤")):
            score += 2
            reasons.append("low-income")
    if "Above ₹50,000" in hh:
        if "bpl" in income_crit or "aay" in income_crit:
            score -= 2

    # Broad useful central/state flagships
    if any(x in name for x in ("pm-kisan", "pmjay", "ayushman", "ujjwala", "jan dhan", "arogya", "gruha jyothi", "anna bhagya", "ladki bahin", "shakti")):
        score += 1

    return score, reasons


def _blob(scheme: dict[str, Any]) -> str:
    return " ".join(
        str(scheme.get(k) or "").lower()
        for k in (
            "Scheme Name",
            "Category",
            "Age Criteria",
            "Income Criteria",
            "Gender / Category Criteria",
            "Other Key Eligibility Criteria",
            "Benefit",
        )
    )


def _score_family_scheme(scheme: dict[str, Any], slots: dict[str, str]) -> tuple[int, list[str]]:
    """Journey 1 score plus household signals (children, elders, maternal, etc.)."""
    score, reasons = _score_scheme(scheme, _family_to_individual_slots(slots))
    text = _blob(scheme)
    name = (scheme.get("Scheme Name") or "").lower()
    category = (scheme.get("Category") or "").lower()

    n_children = _as_int(slots.get("children_under_18"))
    n_elders = _as_int(slots.get("members_60_plus"))
    n_hh = _as_int(slots.get("household_size"))

    if n_children > 0 and any(
        x in text
        for x in (
            "child",
            "children",
            "girl",
            "adolescent",
            "anganwadi",
            "icds",
            "mid-day",
            "mid day",
            "nutrition",
            "school",
            "sukanya",
            "ladki",
            "bhagyalakshmi",
            "poshan",
            "immunis",
        )
    ):
        score += 4
        reasons.append("children")

    if n_elders > 0 and any(
        x in text
        for x in ("old age", "senior", "elderly", "pension", "60+", "65+", "igndps", "ignoaps")
    ):
        score += 4
        reasons.append("elders")

    pregnant = (slots.get("pregnant_or_breastfeeding") or "").lower()
    if pregnant == "yes" and any(
        x in text
        for x in (
            "maternal",
            "maternity",
            "pregnant",
            "pregnan",
            "lactat",
            "pmmvy",
            "janani",
            "breastfeed",
            "jssk",
            "newborn",
        )
    ):
        score += 5
        reasons.append("maternal")

    ration = slots.get("ration_card") or ""
    if ration in ("Antyodaya (AAY)", "BPL") and any(
        x in text
        for x in (
            "bpl",
            "aay",
            "antyodaya",
            "nfsa",
            "pds",
            "food",
            "ration",
            "foodgrain",
            "anna",
            "poverty",
        )
    ):
        score += 4
        reasons.append("ration/BPL")

    housing = slots.get("housing") or ""
    if housing in ("Own - Kutcha", "Rented", "Homeless / No permanent housing") and any(
        x in text for x in ("housing", "pmay", "awas", "shelter", "gruh", "vasati")
    ):
        score += 4
        reasons.append("housing")
        if housing.startswith("Homeless"):
            score += 1

    if (slots.get("has_insurance") or "").lower() == "no" and (
        any(x in category for x in ("health", "insurance"))
        or any(x in name for x in ("ayushman", "pmjay", "pm-jay", "arogya", "pm-jay"))
        or "health insurance" in text
    ):
        score += 4
        reasons.append("uninsured")

    if n_hh >= 5 and any(x in category for x in ("food", "nutrition", "pds")):
        score += 1

    return score, reasons


def _is_family_profile(slots: dict[str, str], journey_id: str | None) -> bool:
    if journey_id == "journey_2":
        return True
    return any(
        key in slots
        for key in ("household_size", "children_under_18", "members_60_plus", "ration_card")
    )


def match_schemes(
    slots: dict[str, str],
    limit: int = 8,
    journey_id: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    state = slots.get("state")
    schemes, scope_note = load_scheme_pool(state)
    family = _is_family_profile(slots, journey_id)

    scored: list[tuple[int, dict[str, Any], list[str]]] = []
    for scheme in schemes:
        if is_hard_ineligible(scheme, slots):
            continue
        if family:
            score, reasons = _score_family_scheme(scheme, slots)
        else:
            score, reasons = _score_scheme(scheme, slots)
        if score > 0:
            scored.append((score, scheme, reasons))

    scored.sort(key=lambda x: (-x[0], str(x[1].get("_library") or ""), int(re.sub(r"\D", "", str(x[1].get("SN") or "0")) or 0)))

    if not scored:
        # Fallback: a few well-known central + state flagships if present
        preferred = []
        family_keys = (
            "pm-kisan",
            "ayushman",
            "pmjay",
            "arogya",
            "ladki bahin",
            "anna bhagya",
            "pmay",
            "pmmvy",
            "ujjwala",
        )
        individual_keys = ("pm-kisan", "ayushman", "pmjay", "arogya", "ladki bahin", "anna bhagya")
        keys = family_keys if family else individual_keys
        for s in schemes:
            if is_hard_ineligible(s, slots):
                continue
            n = (s.get("Scheme Name") or "").lower()
            if any(k in n for k in keys):
                preferred.append(s)
        return preferred[:limit], scope_note

    results = []
    for score, scheme, reasons in scored[:limit]:
        item = dict(scheme)
        item["_match_score"] = score
        item["_match_reasons"] = reasons
        results.append(item)
    return results, scope_note


_BULLET_SCHEME_ROW = re.compile(r"(?m)^[ \t]*[•●▪‣*]\s+\S.*$")
_HYPHEN_SCHEME_ROW = re.compile(r"(?m)^[ \t]*[-–—]\s+[A-Za-z\u0900-\u0D7F].+$")
_NUMBERED_SCHEME_ROW = re.compile(r"(?m)^\d+\.\s+\S")


def numbered_scheme_lines(
    schemes: list[dict[str, Any]],
    language: str | None = None,
) -> list[str]:
    """Running 1, 2, 3… list — name + [Central|State] only, never a description."""
    lang = i18n.normalize_language(language)
    lines: list[str] = []
    for i, s in enumerate(schemes, 1):
        lib = i18n.library_label(s.get("_library"), lang)
        tag = f" [{lib}]" if lib else ""
        name = s.get("Scheme Name") or "Scheme"
        lines.append(f"{i}. {name}{tag}")
    return lines


def has_bullet_scheme_list(text: str | None) -> bool:
    """True when free-text dumped schemes as bullets (the live duplicate-list bug)."""
    blob = text or ""
    if len(_BULLET_SCHEME_ROW.findall(blob)) >= 1:
        return True
    return len(_HYPHEN_SCHEME_ROW.findall(blob)) >= 2


def llm_lists_schemes(text: str | None) -> bool:
    """Reject LLM prose that names schemes as bullets or a parallel numbered dump."""
    blob = text or ""
    if has_bullet_scheme_list(blob):
        return True
    return len(_NUMBERED_SCHEME_ROW.findall(blob)) >= 2


def drop_scheme_dump_prefix(text: str | None) -> str:
    """Strip unnumbered bullet/hyphen scheme dumps; keep the numbered formatter block."""
    blob = text or ""
    if not has_bullet_scheme_list(blob):
        return blob
    cleaned = _BULLET_SCHEME_ROW.sub("", blob)
    cleaned = _HYPHEN_SCHEME_ROW.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    numbered = _NUMBERED_SCHEME_ROW.search(cleaned)
    if numbered:
        before = cleaned[: numbered.start()]
        # Drop leftover LLM lead-in that only existed to introduce the bullet dump.
        if re.search(r"(useful schemes|आपके लिए कुछ उपयोगी|उपयोगी योजनाएँ हैं)", before, re.I):
            # Keep a trailing scope note / intro paragraph if present after the dump.
            parts = [p.strip() for p in before.split("\n\n") if p.strip()]
            keep: list[str] = []
            for part in parts:
                if llm_lists_schemes(part) or has_bullet_scheme_list(part):
                    continue
                if re.search(r"(useful schemes|आपके लिए कुछ उपयोगी|उपयोगी योजनाएँ हैं)", part, re.I):
                    continue
                keep.append(part)
            before = "\n\n".join(keep)
        cleaned = (before.rstrip() + "\n\n" + cleaned[numbered.start() :]).strip()
    return cleaned


def format_scheme_list(
    schemes: list[dict[str, Any]],
    scope_note: str = "",
    footer: str | None = None,
    intro: str | None = None,
    language: str | None = None,
) -> str:
    lang = i18n.normalize_language(language)
    if not schemes:
        return i18n.t("scheme_list_empty", lang)
    lines = []
    note = i18n.localize_scope_note(scope_note, lang) if scope_note else ""
    if note:
        lines.append(note)
        lines.append("")
    lines.append(intro or i18n.t("scheme_list_intro", lang))
    lines.append("")
    lines.extend(numbered_scheme_lines(schemes, lang))
    lines.append("")
    lines.append(footer or i18n.t("scheme_list_footer", lang))
    return "\n".join(lines)


def format_scheme_detail(
    scheme: dict[str, Any],
    back_prompt: str | None = None,
    language: str | None = None,
) -> str:
    lang = i18n.normalize_language(language)
    display = translate.localize_scheme(scheme, lang)
    source = scheme.get("Beneficiary Count — Source Note") or ""
    link = ""
    m = re.search(r"https?://\S+", source)
    if m:
        link = m.group(0).rstrip("|").strip()
    lib = i18n.library_label(scheme.get("_library"), lang)
    parts = [
        f"*{scheme.get('Scheme Name')}*" + (f" ({lib})" if lib else ""),
        f"{i18n.t('scheme_field_category', lang)}: {display.get('Category')}",
        f"{i18n.t('scheme_field_benefit', lang)}: {display.get('Benefit')}",
        f"{i18n.t('scheme_field_age', lang)}: {display.get('Age Criteria')}",
        f"{i18n.t('scheme_field_income', lang)}: {display.get('Income Criteria')}",
        f"{i18n.t('scheme_field_who', lang)}: {display.get('Gender / Category Criteria')}",
        f"{i18n.t('scheme_field_other', lang)}: {display.get('Other Key Eligibility Criteria')}",
    ]
    if link:
        parts.append(f"{i18n.t('scheme_field_more_info', lang)}: {link}")
    parts.append("")
    parts.append(i18n.t("scheme_guidance", lang))
    # What-next / back prompt is a separate WhatsApp message (see interactive.finalize).
    return "\n".join(parts)


# --- Category path (schemes_by_category_v1) ---------------------------------
# Isolated from Journey 1 / Journey 2 scoring entry points.


def _category_slots_to_scorer(slots: dict[str, str]) -> dict[str, str]:
    """Best-effort map of category-pack answers onto Journey 1 scorer fields."""
    mapped = dict(slots)
    if slots.get("age") and not mapped.get("age"):
        mapped["age"] = slots["age"]
    if slots.get("gender") and not mapped.get("gender"):
        mapped["gender"] = slots["gender"]
    caste = slots.get("caste") or slots.get("social_category")
    if caste:
        mapped["social_category"] = caste

    profile = slots.get("profile") or ""
    if profile == "sc_st" and not mapped.get("social_category"):
        mapped["social_category"] = "SC"
    elif profile == "minority":
        mapped["social_category"] = mapped.get("social_category") or "Minority"
    elif profile == "general_obc" and not mapped.get("social_category"):
        mapped["social_category"] = "OBC"

    income = slots.get("income_annual") or slots.get("housing_income") or ""
    income_map = {
        "lt_1l": "Up to ₹10,000",
        "1_2_5l": "₹10,001–₹30,000",
        "2_5_8l": "₹30,001–₹50,000",
        "above_8l": "Above ₹50,000",
        "ews": "Up to ₹10,000",
        "lig": "₹10,001–₹30,000",
        "mig": "₹30,001–₹50,000",
        "above": "Above ₹50,000",
    }
    if income in income_map:
        mapped["household_income"] = income_map[income]

    ration = slots.get("ration_level") or slots.get("ration_card") or ""
    if ration in ("AAY", "AAY_BPL"):
        mapped["ration_card"] = "Antyodaya (AAY)"
        mapped["household_income"] = mapped.get("household_income") or "Up to ₹10,000"
    elif ration == "BPL":
        mapped["ration_card"] = "BPL"
        mapped["household_income"] = mapped.get("household_income") or "Up to ₹10,000"
    elif ration == "APL":
        mapped["ration_card"] = "APL"
    elif ration in ("None", "no_card"):
        mapped["ration_card"] = "None"

    if slots.get("pension_type") == "widow":
        mapped["marital_status"] = "Widowed"
    if slots.get("pension_type") == "old_age" or slots.get("age_band") in ("60_79", "80_plus"):
        mapped["age_group"] = "60+"
    elif slots.get("age_band") == "under_40":
        mapped["age_group"] = "18–59"
    elif slots.get("age_band") == "40_59":
        mapped["age_group"] = "18–59"
    elif slots.get("who") == "girl_child" or slots.get("health_who") == "child":
        mapped["age_group"] = "0–17"

    if (
        slots.get("pension_type") == "disability"
        or slots.get("disability_pct")
        or (slots.get("disability") or "").lower() == "yes"
    ):
        mapped["disability"] = "Yes"

    housing_status = slots.get("housing_status") or ""
    housing_map = {
        "houseless": "Homeless / No permanent housing",
        "kutcha": "Own - Kutcha",
        "upgrade": "Own - Kutcha",
        "has_site": "Own - Kutcha",
    }
    if housing_status in housing_map:
        mapped["housing"] = housing_map[housing_status]

    if slots.get("work_status") == "unemployed":
        mapped["occupation"] = "Unemployed"
    elif slots.get("focus") == "job_mgnrega" or slots.get("work_status") == "wage":
        mapped["occupation"] = "Labourer"
    elif slots.get("work_status") in ("self_employed", "start_grow"):
        mapped["occupation"] = "Self-employed"
    elif slots.get("role") or slots.get("land"):
        mapped["occupation"] = "Farmer"
        if slots.get("role") == "agri_labour":
            mapped["occupation"] = "Labourer"
    elif slots.get("edu_level") or slots.get("schol_level"):
        mapped["occupation"] = "Student"

    if slots.get("who") in ("pregnant_lactating", "mother_infant") or slots.get("health_who") == "pregnant":
        mapped["pregnant_or_breastfeeding"] = "Yes"
    if slots.get("household_shape") == "with_children":
        mapped["children_under_18"] = "1"
    if slots.get("household_shape") == "with_senior" or mapped.get("age_group") == "60+":
        mapped["members_60_plus"] = "1"
    if slots.get("insurance_status") == "none":
        mapped["has_insurance"] = "No"
    elif slots.get("insurance_status") in ("pmjay_state", "private"):
        mapped["has_insurance"] = "Yes"

    board_state = slots.get("board_state")
    if board_state in ("Karnataka", "Maharashtra") and not mapped.get("state"):
        mapped["state"] = board_state
    return mapped


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    hits = 0
    for kw in keywords:
        if not kw:
            continue
        # Whole-token match for letters/digits so "ration" ≠ "registration".
        if re.fullmatch(r"[a-z0-9]+(?:[ /-][a-z0-9]+)*", kw):
            if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text):
                hits += 1
        elif kw in text:
            hits += 1
    return hits


def _score_category_scheme(
    scheme: dict[str, Any],
    category_id: str,
    slots: dict[str, str],
    *,
    pension_slice: bool = False,
) -> tuple[int, list[str]]:
    from . import category_catalog as cat

    text = _blob(scheme)
    reasons: list[str] = []
    score = 0

    spec = cat.CATEGORY_KEYWORDS.get(category_id) or {}
    any_kws = spec.get("any") or ()
    hits = _keyword_hits(text, any_kws)
    if hits:
        score += 6 + min(hits, 4)
        reasons.append(category_id)
    elif pension_slice and category_id == "disability":
        pension_hits = _keyword_hits(text, (cat.CATEGORY_KEYWORDS.get("pension") or {}).get("any") or ())
        dis_hits = _keyword_hits(text, any_kws)
        if pension_hits and (dis_hits or any(x in text for x in ("disability", "widow", "old age", "igndps"))):
            score += 5
            reasons.append("disability-pension")
        elif pension_hits and (slots.get("dis_need") == "pension"):
            score += 4
            reasons.append("pension-slice")
        else:
            return 0, reasons
    else:
        return 0, reasons

    show_kws = spec.get("boost_show") or ()
    if show_kws:
        show_hits = _keyword_hits(text, show_kws)
        if show_hits:
            score += min(show_hits, 3)
            reasons.append("show-list")

    for key, value in slots.items():
        if not value or key in ("state", "state_scope"):
            continue
        extra = cat.ANSWER_KEYWORDS.get(f"{key}:{value}")
        if extra:
            n = _keyword_hits(text, extra)
            if n:
                score += 2 + min(n, 3)
                reasons.append(f"{key}:{value}")

    scorer_slots = _category_slots_to_scorer(slots)
    if is_hard_ineligible(scheme, scorer_slots):
        return 0, []
    base, base_reasons = _score_scheme(scheme, scorer_slots)
    if _is_family_profile(scorer_slots, None):
        fam, fam_reasons = _score_family_scheme(scheme, scorer_slots)
        base = max(base, fam)
        base_reasons = base_reasons + fam_reasons
    if base > 0:
        score += min(base, 8)
        reasons.extend(base_reasons)

    # Labour board-state: prefer matching library when known
    if category_id == "labour_bocw":
        board_state = (slots.get("board_state") or slots.get("state") or "").lower()
        library = (scheme.get("_library") or "").lower()
        if board_state in ("karnataka", "maharashtra") and library == board_state:
            score += 3
            reasons.append("board-state")

    return score, reasons


def match_category_schemes(
    slots: dict[str, str],
    category_id: str,
    *,
    scope: str | None = None,
    limit: int = 8,
    pension_slice: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """Deterministic category-path matcher. Does not alter Journey 1/2 match_schemes()."""
    schemes, scope_note = load_scheme_pool_by_scope(scope, slots.get("state"))
    scored: list[tuple[int, dict[str, Any], list[str]]] = []
    for scheme in schemes:
        if is_hard_ineligible(scheme, _category_slots_to_scorer(slots)):
            continue
        score, reasons = _score_category_scheme(
            scheme, category_id, slots, pension_slice=pension_slice
        )
        if score > 0:
            scored.append((score, scheme, reasons))

    scored.sort(
        key=lambda x: (
            -x[0],
            str(x[1].get("_library") or ""),
            int(re.sub(r"\D", "", str(x[1].get("SN") or "0")) or 0),
        )
    )

    if not scored:
        # Fallback: category-keyword hits only, no answer boosts — still hard-gated.
        for scheme in schemes:
            if is_hard_ineligible(scheme, _category_slots_to_scorer(slots)):
                continue
            score, reasons = _score_category_scheme(
                scheme, category_id, {}, pension_slice=pension_slice
            )
            if score > 0:
                scored.append((score, scheme, reasons))
        scored.sort(key=lambda x: -x[0])

    results = []
    for score, scheme, reasons in scored[:limit]:
        item = dict(scheme)
        item["_match_score"] = score
        item["_match_reasons"] = reasons
        results.append(item)
    return results, scope_note
