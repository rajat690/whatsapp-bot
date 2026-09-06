"""Deterministic scheme eligibility matching (no LLM)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

STATE_TO_FILE = {
    "karnataka": "schemes_karnataka.json",
    "maharashtra": "schemes_maharashtra.json",
}


def _load_json(name: str) -> dict[str, Any]:
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_scheme_pool(state: str | None) -> tuple[list[dict[str, Any]], str]:
    """Return schemes to search + a short scope note for the user."""
    central = _load_json("schemes_central.json").get("schemes", [])
    for s in central:
        s.setdefault("_library", "Central")

    state_l = (state or "").strip().lower()
    state_file = STATE_TO_FILE.get(state_l)
    if state_file and (DATA_DIR / state_file).exists():
        state_schemes = _load_json(state_file).get("schemes", [])
        for s in state_schemes:
            s.setdefault("_library", state)
        note = f"Matching Central + {state} schemes."
        return central + state_schemes, note

    if state:
        note = (
            f"Matching Central schemes only — no dedicated library yet for {state}. "
            "Karnataka and Maharashtra state libraries are available."
        )
    else:
        note = "Matching Central schemes (state not set)."
    return central, note


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _family_to_individual_slots(slots: dict[str, str]) -> dict[str, str]:
    """Map Journey 2 household fields onto Journey 1 scorer inputs."""
    mapped = dict(slots)
    if slots.get("primary_occupation") and not mapped.get("occupation"):
        mapped["occupation"] = slots["primary_occupation"]
    if slots.get("family_disability") and not mapped.get("disability"):
        mapped["disability"] = slots["family_disability"]
    return mapped


def _score_scheme(scheme: dict[str, Any], slots: dict[str, str]) -> tuple[int, list[str]]:
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
    elif social == "minority":
        if "minority" in category or "minority" in gender_crit or "minority" in other:
            score += 4
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
    name = (scheme.get("Scheme Name") or "").lower()
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


def format_scheme_list(schemes: list[dict[str, Any]], scope_note: str = "") -> str:
    if not schemes:
        return (
            "I couldn’t confidently match schemes from your details yet. "
            "You can edit your profile or ask for help and our team can assist."
        )
    lines = []
    if scope_note:
        lines.append(scope_note)
        lines.append("")
    lines.append(
        "Based on what you shared, these schemes may be relevant "
        "(final eligibility depends on official verification):"
    )
    lines.append("")
    for i, s in enumerate(schemes, 1):
        lib = s.get("_library") or ""
        tag = f" [{lib}]" if lib else ""
        lines.append(f"{i}. {s.get('Scheme Name')}{tag} — {s.get('Benefit')}")
    lines.append("")
    lines.append("Reply with a number or scheme name to learn more.")
    return "\n".join(lines)


def format_scheme_detail(scheme: dict[str, Any], back_prompt: str | None = None) -> str:
    source = scheme.get("Beneficiary Count — Source Note") or ""
    link = ""
    m = re.search(r"https?://\S+", source)
    if m:
        link = m.group(0).rstrip("|").strip()
    lib = scheme.get("_library")
    parts = [
        f"*{scheme.get('Scheme Name')}*" + (f" ({lib})" if lib else ""),
        f"Category: {scheme.get('Category')}",
        f"Benefit: {scheme.get('Benefit')}",
        f"Age: {scheme.get('Age Criteria')}",
        f"Income: {scheme.get('Income Criteria')}",
        f"Who: {scheme.get('Gender / Category Criteria')}",
        f"Other: {scheme.get('Other Key Eligibility Criteria')}",
    ]
    if link:
        parts.append(f"More info: {link}")
    parts.append("")
    parts.append(
        "This is guidance only — please re-verify on the official site before applying."
    )
    parts.append(
        back_prompt
        or "Reply *help* for support, or *other schemes* to go back to the list."
    )
    return "\n".join(parts)
