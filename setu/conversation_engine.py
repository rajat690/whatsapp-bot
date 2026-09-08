"""Conversational logic engine: interrupts, ≤4 collect, known_profile, park/resume.

Turn loop (discovery / collect):
1. Hard interrupts always win (before LLM collect).
2. Extract every slot present in the message; merge into slots + known_profile.
3. Heard-you summary when ≥2 new facts; then exactly one next ask.
4. Rules own gates (consent, ≤4, match, proceed/edit). LLM owns wording only.
5. Closed-choice slots → WhatsApp buttons (≤3) or list (4–10) + numbered text.
6. Path switches mid-journey snapshot into parked and can resume.
7. Never re-ask a filled slot unless the user chooses Edit.
8. known_profile survives Individual / Family / Category; wipe only on restart.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import i18n, interactive, nlu, profile_intent

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

JOURNEY_FILES = {
    "journey_1": "journey1.json",
    "journey_2": "journey2.json",
}

MAX_POST_CONSENT_QUESTIONS = 4

# Post-consent asks (state is asked before consent and does not count).
# Gender is first-class. If it is already known, the original fourth ask
# (social category / members 60+) stays; otherwise gender takes that slot
# so women-only / male-only hard gates can fire.
ASK_PRIORITY: dict[str, tuple[str, ...]] = {
    "journey_1": (
        "age_group",
        "gender",
        "occupation",
        "household_income",
    ),
    "journey_2": (
        "household_size",
        "gender",
        "children_under_18",
        "household_income",
    ),
}

ASK_PRIORITY_GENDER_KNOWN: dict[str, tuple[str, ...]] = {
    "journey_1": (
        "age_group",
        "occupation",
        "household_income",
        "social_category",
    ),
    "journey_2": (
        "household_size",
        "children_under_18",
        "members_60_plus",
        "household_income",
    ),
}

PRE_CONSENT_SLOTS = frozenset({"state"})

INTERRUPTIBLE_PHASES = frozenset(
    {
        "collect_profile",
        "confirm_profile",
        "consent",
        "consent_declined",
        "help_crm",
        "scheme_list",
        "scheme_detail",
        "named_scheme",
        "named_scheme_list",
        "named_scheme_ask",
        "who_first",
        "who_clarify",
        "cat_language",
        "cat_state_scope",
        "cat_state_plus",
        "cat_hub",
        "cat_who",
        "cat_collect",
        "cat_results",
        "cat_detail",
    }
)

# End-menu / feedback own their End Chat → rating flow.
_SKIP_HARD_INTERRUPT_PHASES = frozenset({"end_menu", "feedback", "referral"})

COLLECT_PHASES = frozenset({"collect_profile", "confirm_profile", "consent"})

IDLE_PHASES = frozenset(
    {
        "welcome_language",
        "main_menu",
        "end_menu",
        "named_scheme_ask",
        "feedback",
    }
)

_WIFE_SCHEMES = re.compile(
    r"(schemes? for (?:my )?(?:wife|spouse)|"
    r"(?:wife|spouse).{0,24}schemes?|"
    r"पत्नी के लिए|बायकोसाठी|ಪತ್ನಿ(?:ಗಾಗಿ)?)",
    re.I,
)

_RESUME_RE = re.compile(
    r"^\s*(resume(?:\s+family(?:\s+profile)?)?|resume profile|"
    r"वापस परिवार|कुटुंब सुरू|कुटुंब पुन्हा)\s*$",
    re.I,
)


@dataclass(frozen=True)
class Interrupt:
    kind: str
    payload: Any = None


def load_journey(journey_id: str | None = None) -> dict[str, Any]:
    filename = JOURNEY_FILES.get(journey_id or "journey_1", "journey1.json")
    with (DATA_DIR / filename).open(encoding="utf-8") as f:
        return json.load(f)


def journey_key(session_or_id: Any) -> str:
    if isinstance(session_or_id, dict):
        jid = session_or_id.get("journey_id") or ""
    else:
        jid = session_or_id or ""
    if jid in ("journey_2", "journey_2_family"):
        return "journey_2"
    return "journey_1"


def ensure_fields(session: dict[str, Any]) -> dict[str, Any]:
    session.setdefault("known_profile", {})
    session.setdefault("parked", None)
    session.setdefault("prompted_slots", [])
    session.setdefault("collect_slot_id", None)
    session.setdefault("slots", {})
    return session


def merge_known_profile(session: dict[str, Any], extracted: dict[str, str] | None) -> None:
    ensure_fields(session)
    profile = session.setdefault("known_profile", {})
    for key, value in (extracted or {}).items():
        if value not in (None, "", "null", "unknown"):
            profile[str(key)] = str(value)


def seed_slots_from_known(session: dict[str, Any]) -> dict[str, str]:
    """Copy known_profile into empty slot keys (never wipes known_profile)."""
    ensure_fields(session)
    slots = session.setdefault("slots", {})
    for key, value in (session.get("known_profile") or {}).items():
        if value and not slots.get(key):
            slots[key] = value
    return slots


def ask_priority_for(
    journey_id: str | None,
    filled: dict[str, str] | None = None,
    prompted: list[str] | None = None,
) -> tuple[str, ...]:
    """≤4 post-consent asks. Gender replaces the last original ask when unknown.

    If gender was volunteered / seeded (filled but never prompted), keep the
    original fourth ask (social category / members 60+). Once we have asked
    gender, do not swap social category back in — that would exceed the cap.
    """
    key = journey_key(journey_id)
    filled = filled or {}
    prompted = prompted or []
    if filled.get("gender") and "gender" not in prompted:
        return ASK_PRIORITY_GENDER_KNOWN.get(key, ASK_PRIORITY_GENDER_KNOWN["journey_1"])
    return ASK_PRIORITY.get(key, ASK_PRIORITY["journey_1"])


def collect_slot_ids(
    journey_id: str | None,
    filled: dict[str, str] | None = None,
    prompted: list[str] | None = None,
) -> list[str]:
    priority = list(ask_priority_for(journey_id, filled, prompted))
    ordered = ["state"]
    for sid in priority[:MAX_POST_CONSENT_QUESTIONS]:
        if sid not in ordered:
            ordered.append(sid)
    return ordered


def collect_slot_defs(
    journey: dict[str, Any],
    journey_id: str | None = None,
    filled: dict[str, str] | None = None,
    prompted: list[str] | None = None,
) -> list[dict[str, Any]]:
    jid = journey_id or journey.get("id")
    if jid == "journey_2_family":
        jid = "journey_2"
    elif jid == "journey_1_individual":
        jid = "journey_1"
    by_id = {s["id"]: s for s in journey.get("slots") or []}
    return [by_id[sid] for sid in collect_slot_ids(jid, filled, prompted) if sid in by_id]


def has_enough_match_profile(slots: dict[str, str] | None) -> bool:
    """One-shot free text already has age + occupation + community."""
    filled = slots or {}
    has_age = bool(filled.get("age") or filled.get("age_group"))
    has_occ = bool(filled.get("occupation") or filled.get("primary_occupation"))
    has_community = bool(filled.get("social_category"))
    return has_age and has_occ and has_community


def missing_collect_slots(
    journey: dict[str, Any],
    slots: dict[str, str] | None,
    journey_id: str | None = None,
    prompted: list[str] | None = None,
) -> list[dict[str, Any]]:
    filled = slots or {}
    missing = []
    for slot in collect_slot_defs(journey, journey_id, filled, prompted):
        if not filled.get(slot["id"]):
            missing.append(slot)
    # Age + occupation + community is enough to rank; skip leftover budget asks
    # (typically household income) on a one-shot profile dump.
    key = journey_key(journey_id or journey.get("id"))
    if key == "journey_1" and has_enough_match_profile(filled):
        return [m for m in missing if m["id"] == "state"]
    return missing


def current_collect_slot(session: dict[str, Any], journey: dict[str, Any] | None = None) -> dict[str, Any] | None:
    journey = journey or load_journey(session.get("journey_id"))
    missing = missing_collect_slots(
        journey,
        session.get("slots") or {},
        session.get("journey_id"),
        session.get("prompted_slots") or [],
    )
    return missing[0] if missing else None


def slot_option_pairs(
    slot: dict[str, Any] | None,
    language: str | None = None,
) -> list[tuple[str, str]]:
    if not slot:
        return []
    opts = slot.get("options") or []
    sid = str(slot.get("id") or "")
    return [(str(o), i18n.option_label(sid, str(o), language)) for o in opts]


def current_slot_options(session: dict[str, Any]) -> list[tuple[str, str]]:
    if (session.get("phase") or "") != "collect_profile":
        return []
    if not session.get("journey_id"):
        return []
    try:
        journey = load_journey(session.get("journey_id"))
    except OSError:
        return []
    return slot_option_pairs(current_collect_slot(session, journey), session.get("language"))


def set_current_slot(session: dict[str, Any], slot: dict[str, Any] | None) -> None:
    ensure_fields(session)
    if not slot:
        session["collect_slot_id"] = None
        return
    session["collect_slot_id"] = slot["id"]
    prompted = session.setdefault("prompted_slots", [])
    sid = slot["id"]
    if sid not in PRE_CONSENT_SLOTS and sid not in prompted:
        prompted.append(sid)


def resolve_option_answer(
    slot: dict[str, Any] | None,
    text: str,
    language: str | None = None,
) -> str | None:
    pairs = slot_option_pairs(slot, language)
    if not pairs:
        return None
    return interactive.pick_by_number_or_id(text, pairs)


def infer_implied_slots(
    text: str,
    extracted: dict[str, str],
    session: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Fill household_size from family composition in a rich message; not from a bare count."""
    extra: dict[str, str] = {}
    slots = {**((session or {}).get("slots") or {}), **extracted}
    n = nlu._norm(text)
    words = profile_intent.word_count(text)
    kids = slots.get("children_under_18") or nlu.detect_count(text, prefer=False, kind="children")
    has_spouse = bool(
        re.search(r"\b(wife|spouse|husband|पत्नी|बीवी|बायको|ಹೆಂಡತಿ)\b", n, re.I)
    )
    rich = (
        has_spouse
        or "family" in n
        or words >= 12
        or bool(kids and nlu.detect_age(text))
        or bool(kids and nlu._map_alias(text, nlu.OCCUPATION_ALIASES))
    )
    if kids is not None and not slots.get("children_under_18"):
        extra["children_under_18"] = str(kids)
        kids = extra["children_under_18"]
    if rich and kids is not None and not slots.get("household_size"):
        try:
            size = 1 + int(str(kids).strip())
        except (TypeError, ValueError):
            size = 1
        if has_spouse:
            size += 1
        extra["household_size"] = str(size)
    if re.search(r"\b(farmer|farming|kisan|किसान|कृषि|शेती)\b", n) and extracted.get(
        "occupation"
    ) == "Labourer":
        extra["occupation"] = "Farmer"
        extra["primary_occupation"] = "Farmer"
    elif extracted.get("occupation") == "Farmer":
        extra.setdefault("primary_occupation", "Farmer")
    if extracted.get("occupation") and extracted["occupation"] in nlu.FAMILY_OCCUPATIONS:
        extra.setdefault("primary_occupation", extracted["occupation"])
    return extra


def extract_turn(session: dict[str, Any], journey: dict[str, Any], text: str) -> dict[str, str]:
    """All present slots from this message (option tap, NLU, implied composition)."""
    current = current_collect_slot(session, journey)
    picked = resolve_option_answer(current, text, session.get("language"))
    resolved = picked or text
    prefer = current["id"] if current else None
    extracted = nlu.extract_slots(resolved, journey.get("slots") or [], prefer_slot=prefer)
    if picked and current:
        extracted[current["id"]] = picked
    extracted.update(infer_implied_slots(text, extracted, session))
    return {k: v for k, v in extracted.items() if v}


def apply_facts(
    session: dict[str, Any],
    extracted: dict[str, str],
    *,
    prefer: str | None = None,
) -> dict[str, str]:
    """Write extracted slots. Preferred (current question) may overwrite; others fill gaps."""
    applied: dict[str, str] = {}
    slots = session.setdefault("slots", {})
    for key, value in (extracted or {}).items():
        if not value:
            continue
        if key == prefer or not slots.get(key):
            slots[key] = value
            applied[key] = value
    merge_known_profile(session, slots)
    return applied


def facts_from_signals(text: str, signals: dict[str, Any] | None) -> dict[str, str]:
    signals = signals or {}
    out: dict[str, str] = {}
    if signals.get("age"):
        out["age"] = str(signals["age"])
    if signals.get("age_group"):
        out["age_group"] = str(signals["age_group"])
    if signals.get("social_category"):
        out["social_category"] = str(signals["social_category"])
    if signals.get("gender"):
        out["gender"] = str(signals["gender"])
    occ = signals.get("occupation")
    if occ:
        out["occupation"] = str(occ)
        if occ in nlu.FAMILY_OCCUPATIONS:
            out["primary_occupation"] = str(occ)
    if signals.get("farmer") and not out.get("occupation"):
        out["occupation"] = "Farmer"
        out["primary_occupation"] = "Farmer"
    if signals.get("children") is not None:
        out["children_under_18"] = str(signals["children"])
    out.update(infer_implied_slots(text, out, None))
    # Opportunistic NLU on the original story (both journeys' slot ids).
    try:
        combined_slots = load_journey("journey_1")["slots"] + load_journey("journey_2")["slots"]
    except OSError:
        combined_slots = []
    out.update(nlu.extract_slots(text, combined_slots, prefer_slot=None))
    out.update(infer_implied_slots(text, out, None))
    return {k: v for k, v in out.items() if v}


def heard_you_bits(extracted: dict[str, str], language: str | None = None) -> str:
    lang = i18n.normalize_language(language)
    order = (
        "state",
        "age",
        "age_group",
        "gender",
        "occupation",
        "primary_occupation",
        "household_size",
        "children_under_18",
        "members_60_plus",
        "household_income",
        "social_category",
        "marital_status",
        "disability",
        "family_disability",
        "pregnant_or_breastfeeding",
        "housing",
        "ration_card",
        "has_insurance",
    )
    bits: list[str] = []
    seen: set[str] = set()
    for key in order:
        val = extracted.get(key)
        if not val or key in seen:
            continue
        if key == "age_group" and extracted.get("age"):
            continue
        if key == "primary_occupation" and extracted.get("occupation") == val:
            continue
        label = i18n.profile_label(key, lang, key.replace("_", " "))
        shown = i18n.option_label(key, val, lang)
        bits.append(f"{label} {shown}")
        seen.add(key)
    return ", ".join(bits)


def is_in_collect(session: dict[str, Any]) -> bool:
    return (session.get("phase") or "") in COLLECT_PHASES


def park_current(session: dict[str, Any]) -> None:
    ensure_fields(session)
    jid = session.get("journey_id")
    phase = session.get("phase") or ""
    if jid not in ("journey_1", "journey_2"):
        return
    if phase not in ("collect_profile", "confirm_profile", "consent"):
        return
    session["parked"] = {
        "journey_id": jid,
        "phase": phase,
        "slots": dict(session.get("slots") or {}),
        "prompted_slots": list(session.get("prompted_slots") or []),
        "consent": session.get("consent"),
        "collect_slot_id": session.get("collect_slot_id"),
        "consent_resume": session.get("consent_resume"),
        "pending_after_consent": session.get("pending_after_consent"),
    }


def restore_parked(session: dict[str, Any]) -> bool:
    parked = session.get("parked")
    if not isinstance(parked, dict) or not parked.get("journey_id"):
        return False
    session["path"] = None
    session["journey_id"] = parked.get("journey_id")
    session["phase"] = parked.get("phase") or "collect_profile"
    session["slots"] = dict(parked.get("slots") or {})
    session["prompted_slots"] = list(parked.get("prompted_slots") or [])
    session["collect_slot_id"] = parked.get("collect_slot_id")
    if parked.get("consent"):
        session["consent"] = parked.get("consent")
    session["consent_resume"] = parked.get("consent_resume")
    session["pending_after_consent"] = parked.get("pending_after_consent")
    session["category_id"] = None
    session["parked"] = None
    seed_slots_from_known(session)
    return True


def clear_ephemeral_path(session: dict[str, Any]) -> None:
    """Leave the current path without wiping language / consent / known_profile."""
    session["path"] = None
    session["journey_id"] = None
    session["slots"] = {}
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
    session["category_id"] = None
    session["state_scope"] = None
    session["hub_screen"] = 1
    session["pension_slice"] = False
    session["cat_q_index"] = 0
    session["collect_slot_id"] = None
    session["prompted_slots"] = []
    session["pending_after_consent"] = None
    session["consent_resume"] = None
    session["named_next_options"] = []


def is_resume_request(text: str) -> bool:
    return bool(_RESUME_RE.match((text or "").strip()))


def _slot_answer_not_interrupt(session: dict[str, Any], text: str) -> bool:
    if (session.get("phase") or "") != "collect_profile":
        return False
    slot = current_collect_slot(session)
    if not slot:
        return False
    if resolve_option_answer(slot, text, session.get("language")):
        return True
    if slot.get("id") == "gender" and nlu.detect_gender(text, prefer=True):
        return True
    return False


def is_hard_stop(text: str) -> bool:
    """End Chat / farewells — exact-ish, not a random substring like 'independent'."""
    raw = (text or "").strip()
    if not raw:
        return False
    if nlu.is_farewell(raw):
        return True
    from . import i18n

    n = nlu.farewell_key(raw)
    for lang in i18n.SUPPORTED:
        if n == nlu.farewell_key(i18n.t("end_opt_end", lang)):
            return True
    return False


def detect_hard_interrupt(session: dict[str, Any], text: str) -> Interrupt | None:
    """End Chat / Main Menu / help — always win, including named-scheme list/detail."""
    raw = (text or "").strip()
    if not raw:
        return None
    phase = session.get("phase") or ""
    if phase in _SKIP_HARD_INTERRUPT_PHASES:
        return None
    n = nlu._norm(raw)

    from . import consent as consent_mod

    # Farewells beat slot/list/number parsing (ola must not become a scheme lookup).
    if is_hard_stop(raw):
        if phase == "consent" and consent_mod.detect(raw) in ("Accept", "Decline"):
            return None
        return Interrupt("stop")

    if phase == "consent" and consent_mod.detect(raw) in ("Accept", "Decline"):
        return None
    if phase == "confirm_profile" and nlu.detect_confirm(raw):
        return None
    if _slot_answer_not_interrupt(session, raw):
        return None

    if n in ("main menu", "menu", "start over") or nlu.detect_end_choice(raw) == "Main Menu":
        if n not in ("1", "2", "3", "4"):
            return Interrupt("main_menu")

    if nlu.is_plain_menu_choice(raw) and nlu.detect_menu(raw) == "I need help":
        if n not in ("1", "2", "3", "4"):
            return Interrupt("help")

    return None


def detect_interrupt(session: dict[str, Any], text: str) -> Interrupt | None:
    """Hard interrupts that must win before LLM collect. None = continue the slot."""
    raw = (text or "").strip()
    if not raw:
        return None
    phase = session.get("phase") or ""
    n = nlu._norm(raw)

    if is_resume_request(raw) and session.get("parked"):
        return Interrupt("resume")

    hard = detect_hard_interrupt(session, raw)
    if hard:
        return hard

    from . import consent as consent_mod

    if phase == "consent" and consent_mod.detect(raw) in ("Accept", "Decline"):
        return None
    if phase == "confirm_profile" and nlu.detect_confirm(raw):
        return None
    if _slot_answer_not_interrupt(session, raw):
        return None
    if interactive.matches_current_options(session, raw):
        return None

    if _WIFE_SCHEMES.search(raw) and profile_intent.word_count(raw) <= 16:
        return Interrupt("wife")

    if profile_intent.looks_like_scheme_name_query(raw):
        return Interrupt("named_scheme")

    kind = profile_intent.classify_free_text(raw)
    if kind == "category" and not profile_intent.skip_category_keyword(raw):
        return Interrupt("category")
    if kind == "shortcut":
        return Interrupt("shortcut")

    if nlu.is_plain_menu_choice(raw):
        choice = nlu.detect_menu(raw)
        if choice in ("Individual Schemes", "Family Schemes", "Browse by category"):
            # Bare 1/2/3 during collect belong to slot options (handled above) or
            # would steal numbered answers — only honor explicit phrases here.
            if n in ("1", "1)", "2", "2)", "3", "3)"):
                return None
            return Interrupt("menu_choice", choice)

    return None
