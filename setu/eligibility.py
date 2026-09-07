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


def load_scheme_pool(state: str | None) -> tuple[list[dict[str, Any]], str]:
    """Return schemes to search + a short scope note for the user."""
    central = _load_central()

    state_l = (state or "").strip().lower()
    state_file = STATE_TO_FILE.get(state_l)
    if state_file and (DATA_DIR / state_file).exists():
        state_schemes = _load_state_library(state)
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


def numbered_scheme_lines(schemes: list[dict[str, Any]]) -> list[str]:
    """Running 1, 2, 3… list — never bullet-only scheme rows."""
    lines: list[str] = []
    for i, s in enumerate(schemes, 1):
        lib = s.get("_library") or ""
        tag = f" [{lib}]" if lib else ""
        name = s.get("Scheme Name") or "Scheme"
        benefit = s.get("Benefit") or ""
        if benefit:
            lines.append(f"{i}. {name}{tag} — {benefit}")
        else:
            lines.append(f"{i}. {name}{tag}")
    return lines


def format_scheme_list(
    schemes: list[dict[str, Any]],
    scope_note: str = "",
    footer: str | None = None,
    intro: str | None = None,
) -> str:
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
        intro
        or (
            "Based on what you shared, these schemes may be relevant "
            "(final eligibility depends on official verification):"
        )
    )
    lines.append("")
    lines.extend(numbered_scheme_lines(schemes))
    lines.append("")
    lines.append(footer or "Reply with a number or scheme name to learn more.")
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


# --- Category path (schemes_by_category_v1) ---------------------------------
# Isolated from Journey 1 / Journey 2 scoring entry points.


def _category_slots_to_scorer(slots: dict[str, str]) -> dict[str, str]:
    """Best-effort map of category-pack answers onto Journey 1 scorer fields."""
    mapped = dict(slots)
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
        # Fallback: category-keyword hits only, no answer boosts
        for scheme in schemes:
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
