"""Conversation-first Journey 1 + Journey 2 orchestrator with deterministic checkpoints."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import (
    category_intent,
    category_path,
    consent,
    eligibility,
    i18n,
    interactive,
    llm,
    lookup,
    nlu,
    profile_intent,
)
from .session import get_session, reset_session

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

JOURNEY_FILES = {
    "journey_1": "journey1.json",
    "journey_2": "journey2.json",
}

PROFILE_LABELS = {
    "journey_1": {
        "state": "State",
        "age_group": "Age group",
        "occupation": "Occupation",
        "household_income": "Household income",
        "social_category": "Social category",
        "marital_status": "Marital status",
        "disability": "Disability",
    },
    "journey_2": {
        "state": "State",
        "household_size": "Household size",
        "children_under_18": "Children under 18",
        "members_60_plus": "Members aged 60+",
        "family_disability": "Family member with disability",
        "pregnant_or_breastfeeding": "Pregnant or breastfeeding",
        "primary_occupation": "Primary occupation",
        "household_income": "Household income",
        "housing": "Housing",
        "ration_card": "Ration card",
        "has_insurance": "Health insurance",
        "social_category": "Social category",
    },
}

SYSTEM_PERSONA = """You are SETU, a warm WhatsApp assistant that helps people in India discover government schemes.
Style: short, natural chat messages (1-4 sentences). Sound like a helpful person, not a form or call-centre script.
No markdown tables. Light WhatsApp formatting (*bold*) sparingly.
Never invent scheme eligibility — the app will run a deterministic matcher.
If the user names a scheme, the app looks it up in the library. Never invent schemes or skip to End Chat after a named-scheme ask.
Languages: English, Hindi, Marathi, and Kannada are all fully supported. Never say you can only speak, help, or reply in one of them.
Always reply in the session language. Never revert to an earlier language.
If the user asks to shift/switch/change to English, Hindi, Marathi, or Kannada, continue in that language. Do not refuse.
During profile collection: acknowledge what the user just said in plain words, then ask EXACTLY ONE outstanding fact.
Never list, number, or combine remaining questions. Never paste option menus for several fields.
"""


def _lang(session: dict[str, Any] | None = None, language: str | None = None) -> str:
    if language:
        return i18n.normalize_language(language)
    if session:
        return i18n.normalize_language(session.get("language"))
    return "English"


def _apply_language_switch(session: dict[str, Any], text: str) -> str | None:
    """Persist a mid-flow language change. Returns the requested language or None."""
    new_lang = nlu.detect_language_switch(text)
    if not new_lang:
        return None
    session["language"] = new_lang
    return new_lang


def _safe_user_reply(reply: str | None) -> str | None:
    """Drop LLM text that invents a single-language-only limitation."""
    text = (reply or "").strip()
    if not text or i18n.claims_single_language_lock(text):
        return None
    return text


def _continue_after_language_switch(session: dict[str, Any]) -> str:
    """Acknowledge a language change and re-show the current step."""
    lang = _lang(session)
    ack = i18n.t("language_switch_ack", lang)
    phase = session.get("phase")
    if phase == "main_menu":
        body = _main_menu(lang)
    elif phase == "collect_profile":
        journey = load_journey(session.get("journey_id"))
        missing = _missing_slots(journey, session.get("slots") or {})
        if missing:
            body = _ask_slot(missing[0], lang)
        else:
            session["phase"] = "confirm_profile"
            body = _profile_summary(session["slots"], session.get("journey_id"), lang)
    elif phase == "confirm_profile":
        body = _profile_summary(session.get("slots") or {}, session.get("journey_id"), lang)
    elif phase == "scheme_list":
        body = eligibility.format_scheme_list(session.get("matched_schemes") or [])
    elif phase == "scheme_detail":
        scheme_sn = session.get("selected_scheme_sn")
        schemes = session.get("matched_schemes") or []
        scheme = next((s for s in schemes if str(s.get("SN")) == str(scheme_sn)), None)
        if scheme:
            body = eligibility.format_scheme_detail(
                scheme,
                back_prompt=_after_detail_prompt(session.get("journey_id"), lang),
            )
        else:
            body = _main_menu(lang)
    elif phase == "help_crm":
        body = i18n.t("help_intro", lang)
    elif phase == "end_menu":
        body = i18n.t("end_menu", lang)
    elif phase == "feedback":
        body = i18n.t("feedback_prompt", lang)
    elif phase == "consent":
        body = consent.prompt(session)
    elif phase in ("who_first", "who_clarify"):
        body = _who_prompt_body(session)
    elif phase == "consent_declined":
        body = consent.declined_message(session)
    else:
        body = _main_menu(lang)
    return ack + "\n\n" + body


def load_journey(journey_id: str | None = None) -> dict[str, Any]:
    filename = JOURNEY_FILES.get(journey_id or "journey_1", "journey1.json")
    with (DATA_DIR / filename).open(encoding="utf-8") as f:
        return json.load(f)


def _missing_slots(journey: dict[str, Any], slots: dict[str, str]) -> list[dict[str, Any]]:
    missing = []
    for slot in journey["slots"]:
        if slot.get("required") and not slots.get(slot["id"]):
            missing.append(slot)
    return missing


def _profile_summary(
    slots: dict[str, str],
    journey_id: str | None = None,
    language: str | None = None,
) -> str:
    labels = PROFILE_LABELS.get(journey_id or "journey_1", PROFILE_LABELS["journey_1"])
    lang = _lang(language=language)
    lines = [i18n.t("profile_header", lang)]
    for key, fallback in labels.items():
        lines.append(f"• {i18n.profile_label(key, lang, fallback)}: {slots.get(key, '—')}")
    lines.append("")
    lines.append(i18n.t("profile_confirm", lang))
    return "\n".join(lines)


def _after_detail_prompt(journey_id: str | None, language: str | None = None) -> str:
    lang = _lang(language=language)
    if journey_id == "journey_2":
        return i18n.t("after_detail_j2", lang)
    return i18n.t("after_detail_j1", lang)


_NAMED_DISCOVERY_PHASES = frozenset(
    {
        "welcome_language",
        "main_menu",
        "help_crm",
        "end_menu",
        "named_scheme",
        "named_scheme_list",
        "named_scheme_ask",
    }
)


def _category_available() -> bool:
    try:
        from . import category_path  # noqa: F401
    except ImportError:
        return False
    return True


def _start_category_path(session: dict[str, Any]) -> str | None:
    try:
        from . import category_path
    except ImportError:
        return None
    start = getattr(category_path, "start", None)
    if not callable(start):
        return None
    return start(session)


def _infer_language(session: dict[str, Any], text: str) -> str:
    if session.get("language"):
        return i18n.normalize_language(session.get("language"))
    lang = nlu.detect_language(text)
    if not lang:
        if any(0x0900 <= ord(ch) <= 0x097F for ch in text):
            lang = "Hindi"
        elif any(0x0C80 <= ord(ch) <= 0x0CFF for ch in text):
            lang = "Kannada"
        else:
            lang = "English"
    session["language"] = lang
    return lang


def _named_next_options(language: str | None) -> list[tuple[str, str]]:
    lang = _lang(language=language)
    options = [
        ("another", i18n.t("named_next_another", lang)),
        ("Individual Schemes", i18n.t("named_next_individual", lang)),
        ("Family Schemes", i18n.t("named_next_family", lang)),
    ]
    if _category_available():
        options.append(("Browse by category", i18n.t("named_next_category", lang)))
    options.append(("Main Menu", i18n.t("named_next_menu", lang)))
    return options


def _named_next_prompt(session: dict[str, Any]) -> str:
    lang = _lang(session)
    options = _named_next_options(lang)
    session["named_next_options"] = [key for key, _label in options]
    lines = [i18n.t("named_next_intro", lang)]
    for i, (_key, label) in enumerate(options, 1):
        lines.append(f"{i}. {label}")
    return "\n".join(lines)


def _present_named_schemes(session: dict[str, Any], hits: list[dict[str, Any]]) -> str:
    lang = _lang(session)
    session["journey_id"] = None
    session["matched_schemes"] = hits
    next_prompt = _named_next_prompt(session)
    if len(hits) == 1:
        session["phase"] = "named_scheme"
        session["selected_scheme_sn"] = hits[0].get("SN")
        return lookup.format_named_scheme_detail(hits[0], next_prompt)
    session["phase"] = "named_scheme_list"
    session["selected_scheme_sn"] = None
    return lookup.format_named_scheme_list(
        hits,
        i18n.t("named_list_intro", lang),
        i18n.t("named_list_footer", lang),
    )


def _named_scheme_miss(session: dict[str, Any], text: str) -> str:
    lang = _lang(session)
    query = lookup.extract_scheme_query(text) or text.strip()
    session["phase"] = "named_scheme_ask"
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
    session["journey_id"] = None
    return i18n.t("named_miss", lang, query=query) + "\n\n" + _named_next_prompt(session)


def _apply_named_next(session: dict[str, Any], action: str) -> str | None:
    if action == "another":
        session["phase"] = "named_scheme_ask"
        return i18n.t("named_ask_another", session.get("language"))
    if action == "Individual Schemes":
        journey = _start_journey(session, "journey_1")
        return (
            i18n.t("individual_intro", session.get("language"))
            + "\n\n"
            + _ask_slot(journey["slots"][0], session.get("language"))
        )
    if action == "Family Schemes":
        journey = _start_journey(session, "journey_2")
        return (
            i18n.t("family_intro", session.get("language"))
            + "\n\n"
            + _ask_slot(journey["slots"][0], session.get("language"))
        )
    if action == "Browse by category":
        started = _start_category_path(session)
        if started:
            return started
        session["phase"] = "main_menu"
        return _main_menu(session.get("language"))
    if action == "Main Menu":
        session["phase"] = "main_menu"
        session["journey_id"] = None
        session["slots"] = {}
        session["matched_schemes"] = []
        session["selected_scheme_sn"] = None
        session["path"] = None
        return _main_menu(session.get("language"))
    return None


def _detect_named_next(session: dict[str, Any], text: str) -> str | None:
    n = text.lower().strip()
    options = session.get("named_next_options") or [k for k, _ in _named_next_options(session.get("language"))]
    if re.fullmatch(r"\d{1,2}", n):
        idx = int(n) - 1
        if 0 <= idx < len(options):
            return options[idx]
    if nlu.detect_end_choice(text) == "Main Menu" or n in ("main menu", "menu"):
        return "Main Menu"
    if any(
        p in n
        for p in (
            "another scheme",
            "other scheme",
            "another yojana",
            "दूसरी योजना",
            "दुसरी योजना",
        )
    ):
        return "another"
    if nlu.is_plain_menu_choice(text):
        choice = nlu.detect_menu(text)
        if choice in ("Individual Schemes", "Family Schemes", "Browse by category"):
            return choice
        if choice == "I need help":
            return None
    if nlu.detect_menu(text) == "Browse by category":
        return "Browse by category"
    return None


def _handle_named_scheme_intent(session: dict[str, Any], text: str) -> str | None:
    """Library lookup for named schemes — never invent facts or jump to End Chat."""
    phase = session.get("phase") or ""
    if session.get("path") == "category" or session.get("journey_id") == "schemes_by_category_v1":
        return None
    if phase not in ("named_scheme", "named_scheme_list", "named_scheme_ask"):
        if profile_intent.block_named_lookup(text):
            return None

    if phase == "named_scheme":
        action = _detect_named_next(session, text)
        if action:
            applied = _apply_named_next(session, action)
            if applied:
                return applied
        hits = lookup.search_schemes(text)
        if hits:
            _infer_language(session, text)
            return _present_named_schemes(session, hits)
        idle = _idle_from_named(session, text)
        if idle:
            return idle
        if nlu.looks_like_scheme_ask(text) and profile_intent.looks_like_scheme_name_query(text):
            return _named_scheme_miss(session, text)
        return i18n.t("named_unclear", session.get("language")) + "\n\n" + _named_next_prompt(session)

    if phase == "named_scheme_list":
        schemes = session.get("matched_schemes") or []
        chosen = nlu.match_scheme_choice(text, schemes)
        if chosen:
            session["phase"] = "named_scheme"
            session["selected_scheme_sn"] = chosen.get("SN")
            return lookup.format_named_scheme_detail(chosen, _named_next_prompt(session))
        action = _detect_named_next(session, text)
        # Numbers belong to the scheme list while it is on screen.
        if action and not re.fullmatch(r"\d{1,2}", text.lower().strip()):
            applied = _apply_named_next(session, action)
            if applied:
                return applied
        hits = lookup.search_schemes(text)
        if hits:
            return _present_named_schemes(session, hits)
        idle = _idle_from_named(session, text)
        if idle:
            return idle
        if nlu.looks_like_scheme_ask(text) and profile_intent.looks_like_scheme_name_query(text):
            return _named_scheme_miss(session, text)
        return (
            i18n.t("named_unclear", session.get("language"))
            + "\n\n"
            + lookup.format_named_scheme_list(
                schemes,
                i18n.t("named_list_intro", session.get("language")),
                i18n.t("named_list_footer", session.get("language")),
            )
        )

    if phase == "named_scheme_ask":
        action = _detect_named_next(session, text)
        if action and action != "another":
            applied = _apply_named_next(session, action)
            if applied:
                return applied
        hits = lookup.search_schemes(text)
        if hits:
            return _present_named_schemes(session, hits)
        if nlu.is_plain_menu_choice(text):
            return None
        idle = _idle_from_named(session, text)
        if idle:
            return idle
        return _named_scheme_miss(session, text)

    ask = nlu.looks_like_scheme_ask(text)
    discovery = phase in _NAMED_DISCOVERY_PHASES
    if not discovery and not ask:
        return None
    if nlu.is_plain_menu_choice(text) and not ask:
        return None
    # Bare language picks must stay on the welcome/menu path.
    if nlu.detect_language(text) and nlu._norm(text) in nlu.LANGUAGE_MAP and not ask:
        return None
    # Category keywords (scholarship, pension, BOCW) are packs, not library cards.
    # A real named scheme still wins via prefer_named_scheme (Ujjwala, Stree Shakti).
    if category_intent.is_idle_phase(phase) and not category_intent.prefer_named_scheme(text):
        if category_intent.detect_category_intent(text):
            return None
        if category_intent.looks_like_unknown_category(text) and not re.search(
            r"tell me about|what is|what's|whats|के बारे में", text or "", re.I
        ):
            return None

    hits = lookup.search_schemes(text)
    if hits:
        best = int(hits[0].get("_lookup_score") or 0)
        # Discovery turns only auto-route a confident library identity.
        if ask or best >= 80 or not discovery:
            if profile_intent.block_named_lookup(text):
                return None
            _infer_language(session, text)
            return _present_named_schemes(session, hits)
    if ask and profile_intent.looks_like_scheme_name_query(text):
        _infer_language(session, text)
        return _named_scheme_miss(session, text)
    return None


def _start_journey(session: dict[str, Any], journey_id: str) -> dict[str, Any]:
    session["path"] = None
    session["journey_id"] = journey_id
    session["phase"] = "collect_profile"
    session["slots"] = {}
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
    session["named_next_options"] = []
    return load_journey(journey_id)


def _ask_slot(slot: dict[str, Any], language: str | None = None) -> str:
    """Fallback question used only when the LLM is unavailable or its reply is unusable."""
    lang = _lang(language=language)
    return i18n.slot_prompt(slot["id"], lang, slot.get("prompt_hint"))


def _one_slot_reply(
    session: dict[str, Any],
    missing_after: list[dict[str, Any]],
    llm_reply: str | None = None,
    switched_to: str | None = None,
) -> str:
    """Prefer the LLM's natural collect reply; templates are fallback only."""
    lang = _lang(session)
    reply = (llm_reply or "").strip()
    if i18n.usable_collect_reply(reply, lang, missing_after):
        return reply
    parts: list[str] = []
    if switched_to:
        parts.append(i18n.t("language_switch_ack", lang))
    parts.append(_ask_slot(missing_after[0], lang))
    return "\n\n".join(parts)


def _maybe_category_intent(session: dict[str, Any], text: str) -> str | None:
    """From welcome / menu / idle: category keyword → that pack (skip hub).

    Named scheme lookup wins when both could match (PR #6, if present).
    Bare Individual / Family / Help / 1-2-3 stay on the menu path.
    """
    if not category_intent.is_idle_phase(session.get("phase")):
        return None
    if category_intent.prefer_named_scheme(text):
        return None
    cid = category_intent.detect_category_intent(text)
    if cid:
        lang = session.get("language") or category_intent.infer_category_language(text)
        extra: dict[str, Any] = {}
        if cid == "disability":
            extra["pension_slice"] = True
        return category_path.start_for_category(session, cid, language=lang, **extra)
    if not category_intent.looks_like_unknown_category(text):
        return None
    lang = session.get("language")
    miss = i18n.t("cat_unknown", lang)
    if session.get("phase") == "welcome_language":
        return miss + "\n\n" + _welcome()
    if session.get("phase") == "end_menu":
        return miss + "\n\n" + i18n.t("end_menu", lang)
    session["phase"] = "main_menu"
    return miss + "\n\n" + _main_menu(lang)


def _idle_from_named(session: dict[str, Any], text: str) -> str | None:
    """Re-classify a life story / category / shortcut typed during a named-scheme step."""
    if nlu.is_plain_menu_choice(text):
        return None
    if not (
        profile_intent.block_named_lookup(text)
        or profile_intent.classify_free_text(text) in ("category", "shortcut", "who_first", "vague")
    ):
        return None
    return _route_idle_free_text(session, text)


def _route_idle_free_text(session: dict[str, Any], text: str) -> str | None:
    """Enforce free-text order: named (already tried) → category → shortcut/story → clarify."""
    if nlu.is_plain_menu_choice(text):
        return None
    if nlu.detect_language(text) and nlu._norm(text) in nlu.LANGUAGE_MAP:
        return None
    kind = profile_intent.classify_free_text(text)
    if kind == "named_scheme":
        return None
    if kind == "category" and not profile_intent.skip_category_keyword(text):
        return _start_known_or_unknown_category(session, text)
    if kind == "shortcut":
        pack = profile_intent.detect_role_shortcut(text)
        if pack:
            lang = session.get("language") or category_intent.infer_category_language(text)
            kwargs: dict[str, Any] = {"language": lang}
            if pack == "disability":
                kwargs["pension_slice"] = True
            if pack == "women_child":
                kwargs["preset"] = {"who": "pregnant_lactating"}
            return category_path.start_for_category(session, pack, **kwargs)
        return None
    if kind == "who_first":
        return _present_who_first(session, text, clarify=False)
    if kind == "vague":
        return _present_who_first(session, text, clarify=True)
    return _start_known_or_unknown_category(session, text)


def _start_known_or_unknown_category(session: dict[str, Any], text: str) -> str | None:
    """Category keyword or honest unknown-topic miss, even mid named-scheme."""
    if category_intent.prefer_named_scheme(text):
        return None
    cid = category_intent.detect_category_intent(text)
    if cid:
        lang = session.get("language") or category_intent.infer_category_language(text)
        extra: dict[str, Any] = {}
        if cid == "disability":
            extra["pension_slice"] = True
        return category_path.start_for_category(session, cid, language=lang, **extra)
    if not category_intent.looks_like_unknown_category(text):
        return None
    lang = session.get("language")
    miss = i18n.t("cat_unknown", lang)
    session["phase"] = "main_menu"
    session["path"] = None
    session["journey_id"] = None
    return miss + "\n\n" + _main_menu(lang)


def _who_options(session: dict[str, Any]) -> list[tuple[str, str]]:
    clarify = session.get("phase") == "who_clarify" or session.get("who_mode") == "clarify"
    return interactive.who_options(session.get("language"), clarify=clarify)


def _who_prompt_body(session: dict[str, Any]) -> str:
    lang = _lang(session)
    clarify = session.get("phase") == "who_clarify" or session.get("who_mode") == "clarify"
    bits = profile_intent.ack_bits(session.get("profile_signals") or {}, lang)
    if clarify:
        body = i18n.t("who_clarify", lang)
    elif bits:
        body = i18n.t("who_ack", lang, bits=bits) + " " + i18n.t("who_intro", lang)
    else:
        body = i18n.t("who_intro", lang)
    return interactive.with_numbered_options(body, _who_options(session))


def _present_who_first(session: dict[str, Any], text: str, *, clarify: bool) -> str:
    _infer_language(session, text)
    session["path"] = None
    session["journey_id"] = None
    session["profile_signals"] = profile_intent.extract_signals(text)
    session["who_mode"] = "clarify" if clarify else "story"
    session["phase"] = "who_clarify" if clarify else "who_first"
    opts = _who_options(session)
    session["who_options"] = [oid for oid, _title in opts]
    return _who_prompt_body(session)


def _on_who_choice(session: dict[str, Any], text: str) -> str:
    opts = _who_options(session)
    choice = interactive.pick_by_number_or_id(text, opts)
    if not choice:
        return i18n.t("who_unclear", session.get("language")) + "\n\n" + _who_prompt_body(session)
    signals = session.get("profile_signals") or {}
    lang = session.get("language")
    if choice == "who_me":
        pack = profile_intent.pack_for_me(signals)
        if pack:
            extra: dict[str, Any] = {"language": lang}
            if pack == "disability":
                extra["pension_slice"] = True
            return category_path.start_for_category(session, pack, **extra)
        journey = _start_journey(session, "journey_1")
        return (
            i18n.t("individual_intro", lang)
            + "\n\n"
            + _ask_slot(journey["slots"][0], lang)
        )
    if choice == "who_wife":
        return category_path.start_for_category(
            session, "women_child", language=lang, preset={"who": "adult_woman"}
        )
    if choice == "who_children":
        pack = profile_intent.pack_for_children(signals)
        preset = {"who": "girl_child"} if pack == "women_child" else None
        return category_path.start_for_category(session, pack, language=lang, preset=preset)
    if choice == "who_family":
        journey = _start_journey(session, "journey_2")
        return (
            i18n.t("family_intro", lang)
            + "\n\n"
            + _ask_slot(journey["slots"][0], lang)
        )
    if choice == "who_category":
        return category_path.start(session)
    if choice == "who_menu":
        session["phase"] = "main_menu"
        session["path"] = None
        session["journey_id"] = None
        return _main_menu(lang)
    return i18n.t("who_unclear", lang) + "\n\n" + _who_prompt_body(session)


def _on_consent(session: dict[str, Any], text: str) -> str:
    choice = consent.detect(text)
    lang = session.get("language")
    if choice == "Decline":
        session["consent"] = "declined"
        session["pending_after_consent"] = None
        session["path"] = None
        session["journey_id"] = None
        session["phase"] = "consent_declined"
        return consent.declined_message(session)
    if choice != "Accept":
        return i18n.t("consent_unclear", lang) + "\n\n" + consent.prompt(session)
    session["consent"] = "accepted"
    resume = session.get("consent_resume")
    pending = session.pop("pending_after_consent", None)
    if resume == "category":
        return category_path.after_consent(session)
    if resume == "confirm_profile":
        session["phase"] = "confirm_profile"
        return pending or _profile_summary(
            session.get("slots") or {}, session.get("journey_id"), lang
        )
    session["phase"] = "collect_profile"
    if pending:
        return pending
    journey = load_journey(session.get("journey_id"))
    missing = _missing_slots(journey, session.get("slots") or {})
    if missing:
        return _ask_slot(missing[0], lang)
    session["phase"] = "confirm_profile"
    return _profile_summary(session.get("slots") or {}, session.get("journey_id"), lang)


def _gate_collect_consent(session: dict[str, Any], pending: str | None) -> str | None:
    if not consent.should_gate(session):
        return None
    journey = load_journey(session.get("journey_id"))
    missing = _missing_slots(journey, session.get("slots") or {})
    session["pending_after_consent"] = pending
    session["consent_resume"] = "confirm_profile" if not missing else "collect_profile"
    if not missing and not pending:
        session["pending_after_consent"] = _profile_summary(
            session.get("slots") or {}, session.get("journey_id"), session.get("language")
        )
        session["consent_resume"] = "confirm_profile"
    session["phase"] = "consent"
    return consent.prompt(session)


def _on_consent_declined(session: dict[str, Any], text: str) -> str:
    if (
        nlu.detect_end_choice(text) == "Main Menu"
        or interactive.pick_by_number_or_id(
            text, [("Main Menu", i18n.t("named_next_menu", session.get("language")))]
        )
        == "Main Menu"
        or nlu._norm(text) in ("1", "1)")
    ):
        session["phase"] = "main_menu"
        return _main_menu(session.get("language"))
    return consent.declined_message(session)


def _welcome() -> str:
    return interactive.with_numbered_options(
        "Hi! Welcome to SETU. I can help you discover government schemes "
        "or get support with an issue.\n\n"
        "Which language would you like to continue in?",
        interactive.language_options("English"),
    )


def _main_menu(language: str | None = None) -> str:
    return i18n.t("main_menu", language)


def _slot_schema(journey: dict[str, Any]) -> str:
    parts = []
    for s in journey["slots"]:
        opts = s.get("options")
        if opts:
            parts.append(f"- {s['id']}: one of {opts}")
        else:
            parts.append(f"- {s['id']}: free text (Indian state name for state)")
    return "\n".join(parts)


def _apply_extracted(
    session: dict[str, Any],
    extracted: dict[str, str],
    prefer: str | None = None,
) -> dict[str, str]:
    """Write extracted slots. Preferred slot may overwrite; others only fill gaps."""
    applied: dict[str, str] = {}
    slots = session.setdefault("slots", {})
    for key, value in extracted.items():
        if not value:
            continue
        if key == prefer or not slots.get(key):
            slots[key] = value
            applied[key] = value
    return applied


def _merge_llm_slots(raw: dict[str, Any], allowed: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    slots = raw.get("slots") if isinstance(raw.get("slots"), dict) else raw
    if not isinstance(slots, dict):
        return out
    for k, v in slots.items():
        if k not in allowed or v in (None, "", "null", "unknown"):
            continue
        text = str(v).strip()
        if k in nlu.COUNT_SLOTS:
            m = re.search(r"\d+", text)
            if m:
                num = int(m.group(0))
                if 0 <= num <= 30:
                    out[k] = str(num)
            continue
        out[k] = text
    return out


def _conversational_collect(
    session: dict[str, Any],
    journey: dict[str, Any],
    text: str,
    switched_to: str | None = None,
) -> str | None:
    """LLM-powered profile collection. Returns reply or None to fall back."""
    if not llm.llm_configured():
        return None

    missing = _missing_slots(journey, session["slots"])
    missing_ids = [m["id"] for m in missing]
    allowed = {s["id"] for s in journey["slots"]}

    journey_id = session.get("journey_id") or "journey_1"
    journey_label = "Family Schemes" if journey_id == "journey_2" else "Individual Schemes"
    next_id = missing_ids[0] if missing_ids else None
    count_note = ""
    if journey_id == "journey_2":
        count_note = (
            "\nCount fields (household_size, children_under_18, members_60_plus) "
            "must be integers and may be 0.\n"
        )
    else:
        count_note = "\nAge group must be exactly one of: 0–17 | 18–59 | 60+.\n"

    system = (
        SYSTEM_PERSONA
        + i18n.language_instruction(session.get("language"))
        + f"\nYou are collecting a short eligibility profile for {journey_label}.\n"
        + "Return ONLY JSON with keys:\n"
        + '  "slots": object with any newly inferred fields from this user message,\n'
        + '  "reply": your next WhatsApp message to the user,\n'
        + '  "language": English|Hindi|Marathi|Kannada if the user just changed language, else null,\n'
        + '  "ready_for_confirm": boolean true only when ALL required slots are filled.\n'
        + "Required slots and allowed values:\n"
        + _slot_schema(journey)
        + count_note
        + "Extract every slot value present in this user message, even if mixed with a language-switch request.\n"
        + "The slot schema is for extraction only — never recite several fields or their option lists.\n"
        + "Write reply as a helpful WhatsApp chat: briefly acknowledge the user's words "
        + "(not slot-id labels like 'state: Karnataka'), then ask only "
        + f"the next needed fact ({next_id}) as ONE natural question.\n"
        + "Do not use form-field labels. Light option hints are OK for that one question, "
        + "or omit them if a free-text answer works (age, numbers, yes/no, state names).\n"
        + "If the user chats off-topic or answers in a full sentence, stay conversational "
        + "and still extract every slot value you can.\n"
        + "Do not list schemes yet. Do not claim eligibility.\n"
    )
    user = json.dumps(
        {
            "language": session.get("language"),
            "already_collected": session.get("slots") or {},
            "still_needed": missing_ids,
            "ask_only": next_id,
            "user_message": text,
        },
        ensure_ascii=False,
    )
    data = llm.chat_json(system, user, temperature=0.45)
    if not data:
        return None

    llm_lang = data.get("language")
    if llm_lang in i18n.SUPPORTED:
        session["language"] = llm_lang
        if llm_lang != switched_to:
            switched_to = llm_lang

    prefer = missing_ids[0] if missing_ids else None
    extracted = _merge_llm_slots(data, allowed)
    extracted.update(nlu.extract_slots(text, journey["slots"], prefer_slot=prefer))
    llm_only = _merge_llm_slots(data, allowed)
    extracted.update(llm_only)
    extracted = _apply_extracted(session, extracted, prefer=prefer)

    reply = (data.get("reply") or "").strip()
    missing_after = _missing_slots(journey, session["slots"])
    ready = bool(data.get("ready_for_confirm")) and not missing_after
    if ready or not missing_after:
        session["phase"] = "confirm_profile"
        summary = _profile_summary(session["slots"], journey_id, session.get("language"))
        if reply and data.get("ready_for_confirm") and i18n.usable_collect_reply(
            reply, session.get("language"), journey.get("slots") or []
        ):
            return reply + "\n\n" + summary
        return summary

    if missing_after:
        return _one_slot_reply(session, missing_after, llm_reply=reply, switched_to=switched_to)
    return None


def _conversational_openers(phase: str, session: dict[str, Any], text: str) -> str | None:
    """Natural replies for welcome/menu/help when LLM is available."""
    if not llm.llm_configured():
        return None

    if phase == "welcome_language":
        system = (
            SYSTEM_PERSONA
            + "\nUser is choosing a language. Return JSON: "
            '{"language": "English"|"Hindi"|"Marathi"|"Kannada"|null, '
            '"choice": "named_scheme"|null, "scheme_query": string|null, "reply": "..."}. '
            "If unclear, ask again. If set, greet briefly IN THAT LANGUAGE and ask "
            "1 Individual / 2 Family / 3 Browse category, or Help. Ask only that one menu question. "
            "If the user named a government scheme, set choice=named_scheme and scheme_query "
            "to the name. Do not invent scheme facts."
        )
        data = llm.chat_json(system, text, temperature=0.4)
        if not data:
            return None
        lang = data.get("language")
        if lang in ("English", "Hindi", "Marathi", "Kannada"):
            session["language"] = lang
            session["phase"] = "main_menu"
        scheme_query = (data.get("scheme_query") or "").strip()
        if data.get("choice") == "named_scheme" or scheme_query:
            found = _handle_named_scheme_intent(session, scheme_query or text)
            if found:
                return found
            _infer_language(session, text)
            return _named_scheme_miss(session, scheme_query or text)
        reply = _safe_user_reply(data.get("reply"))
        return reply or None

    if phase == "main_menu":
        system = (
            SYSTEM_PERSONA
            + i18n.language_instruction(session.get("language"))
            + "\nUser is at main menu. Return JSON: "
            '{"choice": "Individual Schemes"|"Family Schemes"|"Browse by category"|"I need help"|"named_scheme"|null, '
            '"scheme_query": string|null, "reply": "..."}. '
            "If the user names a scheme or asks 'tell me about X yojana/scheme', choice MUST be named_scheme. "
            "Do not start Individual/Family/category collection and do not choose help/End Chat for a named scheme. "
            "Never invent scheme facts — the app will look the name up. "
            "If the user is asking to shift/switch/change language to English, Hindi, Marathi, or Kannada, "
            "that is allowed — do not refuse and do not say you only support one language. "
            "If Individual Schemes, start collecting an individual profile conversationally (ask state first). "
            "If Family Schemes, start collecting a household profile conversationally (ask state first). "
            "If Browse by category, do NOT collect a profile — reply briefly that they can browse by topic. "
            "If help, ask what support they need. Ask exactly one question."
        )
        data = llm.chat_json(
            system,
            json.dumps({"language": session.get("language"), "user_message": text}, ensure_ascii=False),
            temperature=0.4,
        )
        if not data:
            return None
        choice = data.get("choice")
        scheme_query = (data.get("scheme_query") or "").strip()
        if choice == "named_scheme" or scheme_query:
            found = _handle_named_scheme_intent(session, scheme_query or text)
            if found:
                return found
            _infer_language(session, text)
            return _named_scheme_miss(session, scheme_query or text)
        reply = _safe_user_reply(data.get("reply")) or ""
        if choice == "I need help":
            session["phase"] = "help_crm"
            return reply or (
                "Sure — tell me briefly what you need help with and I’ll raise a support request."
            )
        if choice == "Family Schemes":
            _start_journey(session, "journey_2")
            return reply or (
                "Great. I’ll ask a few quick questions about your household, in plain chat.\n\n"
                "Which state does your family live in?"
            )
        if choice == "Browse by category":
            started = category_path.start(session)
            return (reply + "\n\n" + started) if reply else started
        if choice == "Individual Schemes":
            _start_journey(session, "journey_1")
            return reply or (
                "Great. I’ll ask a few quick questions about you, in plain chat.\n\n"
                "Which state do you live in?"
            )
        # No menu choice. Empty/rejected reply → fall through to templates.
        return reply or None

    if phase == "help_crm":
        # Named-scheme asks must never be logged as CRM / End Chat.
        named = _handle_named_scheme_intent(session, text)
        if named:
            return named
        system = (
            SYSTEM_PERSONA
            + i18n.language_instruction(session.get("language"))
            + "\nUser is describing a support issue. Acknowledge warmly in JSON: "
            '{"reply": "...", "summary": "short issue summary"}. '
            "If they named a government scheme, do not close the chat; set summary to the scheme name only."
        )
        data = llm.chat_json(system, text, temperature=0.4)
        summary = text
        reply = None
        if data:
            summary = data.get("summary") or text
            reply = _safe_user_reply(data.get("reply"))
        print(f"CRM_TICKET user_issue={summary}", flush=True)
        session["phase"] = "end_menu"
        base = reply or "Thanks — I’ve logged that for the SETU team."
        return base + "\n\nWould you like the *Main Menu* or *End Chat*?"

    if phase == "scheme_detail":
        scheme_sn = session.get("selected_scheme_sn")
        schemes = session.get("matched_schemes") or []
        scheme = next((s for s in schemes if str(s.get("SN")) == str(scheme_sn)), None)
        if not scheme:
            return None
        offer = (
            "End by offering *I need help* or *Go Back*."
            if session.get("journey_id") == "journey_2"
            else "End by offering help or other schemes."
        )
        system = (
            SYSTEM_PERSONA
            + i18n.language_instruction(session.get("language"))
            + "\nExplain this scheme simply for WhatsApp. Return plain text only (no JSON). "
            "Include benefit, who it is for, and that official verification is needed. "
            + offer
        )
        user = json.dumps(scheme, ensure_ascii=False)[:4000]
        text_out = llm.chat_text(system, user, temperature=0.5)
        return _safe_user_reply(text_out)
    return None


def handle_message(user_id: str, text: str) -> str:
    reply = _handle_message_inner(user_id, text)
    return interactive.finalize(get_session(user_id), reply)


def _handle_message_inner(user_id: str, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Please send a short message and I’ll help."

    session = get_session(user_id)
    phase = session["phase"]
    low = text.lower().strip()
    switched_to = None
    if phase != "welcome_language":
        switched_to = _apply_language_switch(session, text)

    # Global restart
    if low in ("hi", "hello", "hey", "start", "restart", "/start"):
        reset_session(user_id)
        session = get_session(user_id)
        if llm.llm_configured():
            warm = _safe_user_reply(
                llm.chat_text(
                    SYSTEM_PERSONA
                    + "\nUser just said hi. Welcome them to SETU and ask language: English/Hindi/Marathi/Kannada. Plain text only.",
                    text,
                    temperature=0.6,
                )
            )
            if warm:
                return warm
        return _welcome()

    # Language-switch-only: stay on the current step in the new language.
    # Never send these turns to the LLM — it may invent a Hindi-only refusal.
    if phase not in ("welcome_language", "cat_language") and nlu.is_language_switch_only(text):
        if session.get("phase") == "consent":
            return _continue_after_language_switch(session)
        if session.get("path") == "category" or session.get("journey_id") == "schemes_by_category_v1":
            return category_path.replay_after_language_switch(session)
        return _continue_after_language_switch(session)

    if phase == "consent":
        return _on_consent(session, text)
    if phase == "consent_declined":
        return _on_consent_declined(session, text)
    if phase in ("who_first", "who_clarify"):
        return _on_who_choice(session, text)

    # Isolated category path — Journey 1 / Journey 2 handlers never see these sessions.
    if session.get("path") == "category" or session.get("journey_id") == "schemes_by_category_v1":
        return category_path.handle(session, text, user_id, switched_to=switched_to)

    named_reply = _handle_named_scheme_intent(session, text)
    if named_reply:
        return named_reply

    journey = load_journey(session.get("journey_id"))

    # ---- welcome / language ----
    if phase == "welcome_language":
        idle = _route_idle_free_text(session, text)
        if idle:
            return idle
        convo = _conversational_openers(phase, session, text)
        if convo:
            return convo
        lang = nlu.detect_language(text) or nlu.detect_language_switch(text)
        if not lang:
            return (
                "I support English, Hindi, Marathi, and Kannada for now. "
                "Which one should we use?"
            )
        session["language"] = lang
        session["phase"] = "main_menu"
        return i18n.t("continuing_in", lang, chosen=lang) + "\n\n" + _main_menu(lang)

    # ---- main menu ----
    if phase == "main_menu":
        # Button 3 / explicit category tap is deterministic intent — do not send to LLM.
        if nlu.detect_menu(text) == "Browse by category" and not category_intent.detect_category_intent(text):
            return category_path.start(session)
        idle = _route_idle_free_text(session, text)
        if idle:
            return idle
        convo = _conversational_openers(phase, session, text)
        if convo:
            return convo
        choice = nlu.detect_menu(text)
        if nlu._norm(text) in ("4", "4)"):
            choice = "I need help"
        if not choice:
            return i18n.t("menu_unclear", session.get("language"))
        if choice == "I need help":
            session["phase"] = "help_crm"
            return i18n.t("help_intro", session.get("language"))
        if choice == "Family Schemes":
            journey = _start_journey(session, "journey_2")
            return (
                i18n.t("family_intro", session.get("language"))
                + "\n\n"
                + _ask_slot(journey["slots"][0], session.get("language"))
            )
        journey = _start_journey(session, "journey_1")
        return (
            i18n.t("individual_intro", session.get("language"))
            + "\n\n"
            + _ask_slot(journey["slots"][0], session.get("language"))
        )

    # ---- help / CRM ----
    if phase == "help_crm":
        if nlu.is_plain_menu_choice(text):
            choice = nlu.detect_menu(text)
            if choice == "Individual Schemes":
                journey = _start_journey(session, "journey_1")
                return (
                    i18n.t("individual_intro", session.get("language"))
                    + "\n\n"
                    + _ask_slot(journey["slots"][0], session.get("language"))
                )
            if choice == "Family Schemes":
                journey = _start_journey(session, "journey_2")
                return (
                    i18n.t("family_intro", session.get("language"))
                    + "\n\n"
                    + _ask_slot(journey["slots"][0], session.get("language"))
                )
            if choice == "Browse by category":
                started = _start_category_path(session)
                if started:
                    return started
        convo = _conversational_openers(phase, session, text)
        if convo:
            return convo
        print(f"CRM_TICKET user={user_id} issue={text}", flush=True)
        session["phase"] = "end_menu"
        return (
            i18n.t("help_logged", session.get("language"), ref=user_id[-4:])
            + "\n\n"
            + i18n.t("end_menu", session.get("language"))
        )

    # ---- collect profile (conversational) ----
    if phase == "collect_profile":
        convo = _conversational_collect(session, journey, text, switched_to=switched_to)
        gated = _gate_collect_consent(session, convo)
        if gated:
            return gated
        if convo:
            return convo

        missing_before = _missing_slots(journey, session["slots"])
        prefer = missing_before[0]["id"] if missing_before else None
        extracted = nlu.extract_slots(text, journey["slots"], prefer_slot=prefer)
        extracted = _apply_extracted(session, extracted, prefer=prefer)

        missing = _missing_slots(journey, session["slots"])
        lang = session.get("language")
        if not extracted and missing:
            prefix = ""
            if switched_to:
                prefix = i18n.t("language_switch_ack", lang) + "\n\n"
            return prefix + i18n.t("didnt_catch", lang) + " " + _ask_slot(missing[0], lang)

        missing = _missing_slots(journey, session["slots"])
        if missing:
            parts: list[str] = []
            if switched_to:
                parts.append(i18n.t("language_switch_ack", lang))
            if extracted:
                parts.append(i18n.t("got_it_short", lang))
            parts.append(_ask_slot(missing[0], lang))
            next_reply = "\n\n".join(parts)
        else:
            session["phase"] = "confirm_profile"
            next_reply = _profile_summary(session["slots"], session.get("journey_id"), lang)
        gated = _gate_collect_consent(session, next_reply)
        if gated:
            return gated
        return next_reply

    # ---- confirm profile (deterministic branch) ----
    if phase == "confirm_profile":
        picked = interactive.pick_by_number_or_id(
            text,
            [
                ("Proceed", i18n.t("confirm_proceed", session.get("language"))),
                ("Edit details", i18n.t("confirm_edit", session.get("language"))),
            ],
        )
        if picked:
            text = picked
        decision = nlu.detect_confirm(text)
        if decision is None and llm.llm_configured():
            data = llm.chat_json(
                SYSTEM_PERSONA
                + i18n.language_instruction(session.get("language"))
                + '\nUser confirming profile. Return JSON {"decision":"Proceed"|"Edit details"|null,"reply":"..."}',
                text,
                temperature=0.1,
            )
            if data and data.get("decision") in ("Proceed", "Edit details"):
                decision = data["decision"]
        if decision == "Edit details":
            session["phase"] = "collect_profile"
            keep_state = session["slots"].get("state")
            session["slots"] = {}
            if keep_state:
                session["slots"]["state"] = keep_state
            return (
                i18n.t("edit_ack", session.get("language"))
                + "\n\n"
                + _ask_slot(
                    journey["slots"][0] if not keep_state else journey["slots"][1],
                    session.get("language"),
                )
            )
        if decision != "Proceed":
            return i18n.t("confirm_unclear", session.get("language"))

        matched, scope_note = eligibility.match_schemes(
            session["slots"], journey_id=session.get("journey_id")
        )
        session["matched_schemes"] = matched
        session["phase"] = "scheme_list"

        listing = eligibility.format_scheme_list(matched, scope_note=scope_note)
        if llm.llm_configured():
            intro = llm.chat_text(
                SYSTEM_PERSONA
                + i18n.language_instruction(session.get("language"))
                + "\nWrite a short warm intro (1-2 sentences) before a scheme list. Plain text. No bullet list.",
                json.dumps({"slots": session["slots"], "count": len(matched)}, ensure_ascii=False),
                temperature=0.5,
            )
            if intro and not i18n.claims_single_language_lock(intro):
                return intro + "\n\n" + listing
        return listing

    # ---- scheme list ----
    if phase == "scheme_list":
        schemes = session.get("matched_schemes") or []
        chosen = nlu.match_scheme_choice(text, schemes)
        if not chosen and llm.llm_configured():
            # allow natural language pick
            names = [f"{i+1}. {s.get('Scheme Name')}" for i, s in enumerate(schemes)]
            data = llm.chat_json(
                SYSTEM_PERSONA
                + i18n.language_instruction(session.get("language"))
                + "\nUser is picking a scheme from the list. Return JSON "
                '{"index": 1-based int or null, "reply": optional clarifying question}.',
                json.dumps({"options": names, "user_message": text}, ensure_ascii=False),
                temperature=0.1,
            )
            if data and isinstance(data.get("index"), int):
                idx = data["index"] - 1
                if 0 <= idx < len(schemes):
                    chosen = schemes[idx]
            elif data and _safe_user_reply(data.get("reply")) and not chosen:
                return _safe_user_reply(data.get("reply"))
        if not chosen:
            if "edit" in low:
                session["phase"] = "confirm_profile"
                return _profile_summary(
                    session["slots"], session.get("journey_id"), session.get("language")
                )
            return (
                i18n.t("scheme_pick", session.get("language"))
                + "\n\n"
                + eligibility.format_scheme_list(schemes)
            )
        session["selected_scheme_sn"] = chosen.get("SN")
        session["phase"] = "scheme_detail"
        convo = _conversational_openers("scheme_detail", session, text)
        if convo:
            return convo
        return eligibility.format_scheme_detail(
            chosen,
            back_prompt=_after_detail_prompt(
                session.get("journey_id"), session.get("language")
            ),
        )

    # ---- scheme detail ----
    if phase == "scheme_detail":
        action = nlu.detect_after_scheme(text)
        if action == "I need help":
            session["phase"] = "help_crm"
            return i18n.t("help_intro", session.get("language"))
        if action in ("View other schemes", "Go Back") or "other" in low or "list" in low or "back" in low:
            session["phase"] = "scheme_list"
            return eligibility.format_scheme_list(session.get("matched_schemes") or [])
        schemes = session.get("matched_schemes") or []
        chosen = nlu.match_scheme_choice(text, schemes)
        if chosen:
            session["selected_scheme_sn"] = chosen.get("SN")
            convo = _conversational_openers("scheme_detail", session, text)
            if convo:
                return convo
            return eligibility.format_scheme_detail(
                chosen,
                back_prompt=_after_detail_prompt(
                    session.get("journey_id"), session.get("language")
                ),
            )
        # free-text question about scheme
        if llm.llm_configured():
            scheme = next(
                (s for s in schemes if str(s.get("SN")) == str(session.get("selected_scheme_sn"))),
                None,
            )
            if scheme:
                ans = _safe_user_reply(
                    llm.chat_text(
                        SYSTEM_PERSONA
                        + i18n.language_instruction(session.get("language"))
                        + "\nAnswer the user's question using only the scheme JSON. If unknown, say to check the official link. Plain text. "
                        + (
                            "Offer *I need help* or *Go Back*."
                            if session.get("journey_id") == "journey_2"
                            else "Offer help or other schemes."
                        ),
                        json.dumps({"scheme": scheme, "question": text}, ensure_ascii=False)[:5000],
                        temperature=0.4,
                    )
                )
                if ans:
                    return ans
        session["phase"] = "end_menu"
        return i18n.t("end_menu", session.get("language"))

    # ---- end menu ----
    if phase == "end_menu":
        idle = _route_idle_free_text(session, text)
        if idle:
            return idle
        choice = nlu.detect_end_choice(text)
        if interactive.pick_by_number_or_id(
            text,
            [
                ("Main Menu", i18n.t("end_opt_menu", session.get("language"))),
                ("End Chat", i18n.t("end_opt_end", session.get("language"))),
            ],
        ) == "Main Menu":
            choice = "Main Menu"
        if interactive.pick_by_number_or_id(
            text,
            [
                ("Main Menu", i18n.t("end_opt_menu", session.get("language"))),
                ("End Chat", i18n.t("end_opt_end", session.get("language"))),
            ],
        ) == "End Chat":
            choice = "End Chat"
        if choice == "Main Menu":
            session["phase"] = "main_menu"
            session["journey_id"] = None
            session["path"] = None
            session["slots"] = {}
            session["matched_schemes"] = []
            session["selected_scheme_sn"] = None
            return _main_menu(session.get("language"))
        if choice == "End Chat":
            session["phase"] = "feedback"
            return i18n.t("feedback_prompt", session.get("language"))
        return i18n.t("choose_end", session.get("language"))

    # ---- feedback (deterministic rating gate) ----
    if phase == "feedback":
        rating = nlu.detect_rating(text)
        if rating is None:
            return i18n.t("feedback_need_rating", session.get("language"))
        session["rating"] = rating
        if rating in (1, 2):
            reset_session(user_id)
            return "Thanks for the feedback. Take care!"
        session["phase"] = "referral"
        return (
            "Thanks for the feedback. If SETU was useful, would you like to share "
            "it with someone who may also benefit? Reply *Share SETU* or *No, thanks*."
        )

    if phase == "referral":
        reset_session(user_id)
        if "share" in low:
            return (
                "Thank you! You can share SETU with others by forwarding this WhatsApp number.\n"
                "Goodbye!"
            )
        return "No problem — goodbye!"

    session["phase"] = "main_menu"
    return i18n.t("restart_menu", session.get("language")) + "\n\n" + _main_menu(session.get("language"))
