"""Conversation-first Journey 1 + Journey 2 orchestrator with deterministic checkpoints."""

from __future__ import annotations

import json
import re
from typing import Any

from . import (
    category_intent,
    category_path,
    consent,
    conversation_engine as engine,
    eligibility,
    greetings,
    i18n,
    interactive,
    llm,
    lookup,
    nlu,
    profile_intent,
)
from .session import get_session, reset_session

PROFILE_LABELS = {
    "journey_1": {
        "state": "State",
        "age": "Age",
        "age_group": "Age group",
        "occupation": "Occupation",
        "gender": "Gender",
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
Never list, bullet, or name schemes. Numbered scheme lists are produced by the app, not by you.
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
            body = _ask_slot(missing[0], lang, session)
        else:
            session["phase"] = "confirm_profile"
            body = _profile_summary(session["slots"], session.get("journey_id"), lang)
    elif phase == "confirm_profile":
        body = _profile_summary(session.get("slots") or {}, session.get("journey_id"), lang)
    elif phase == "scheme_list":
        body = eligibility.format_scheme_list(
            session.get("matched_schemes") or [],
            language=lang,
        )
    elif phase == "scheme_detail":
        scheme_sn = session.get("selected_scheme_sn")
        schemes = session.get("matched_schemes") or []
        scheme = next((s for s in schemes if str(s.get("SN")) == str(scheme_sn)), None)
        if scheme:
            body = eligibility.format_scheme_detail(
                scheme,
                language=lang,
            )
        else:
            body = _main_menu(lang)
    elif phase == "named_scheme":
        scheme_sn = session.get("selected_scheme_sn")
        schemes = session.get("matched_schemes") or []
        scheme = next((s for s in schemes if str(s.get("SN")) == str(scheme_sn)), None)
        if scheme:
            _stash_named_next_options(session)
            body = lookup.format_named_scheme_detail(scheme, next_prompt="", language=lang)
        else:
            body = i18n.t("named_next_intro", lang)
    elif phase == "named_scheme_list":
        body = lookup.format_named_scheme_list(
            session.get("matched_schemes") or [],
            i18n.t("named_list_intro", lang),
            i18n.t("named_list_footer", lang),
            language=lang,
        )
    elif phase == "named_scheme_ask":
        body = i18n.t("named_ask_another", lang)
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
    return engine.load_journey(journey_id)


def _missing_slots(journey: dict[str, Any], slots: dict[str, str]) -> list[dict[str, Any]]:
    """Outstanding collect slots only (state + ≤4 priority). Extra schema slots are opportunistic."""
    jid = journey.get("id")
    if jid == "journey_2_family":
        jid = "journey_2"
    elif jid == "journey_1_individual":
        jid = "journey_1"
    return engine.missing_collect_slots(journey, slots, jid)


def _profile_summary(
    slots: dict[str, str],
    journey_id: str | None = None,
    language: str | None = None,
) -> str:
    labels = PROFILE_LABELS.get(journey_id or "journey_1", PROFILE_LABELS["journey_1"])
    lang = _lang(language=language)
    lines = [i18n.t("profile_header", lang)]
    for key, fallback in labels.items():
        val = (slots or {}).get(key)
        if not val:
            continue
        if key == "age_group" and (slots or {}).get("age"):
            continue
        lines.append(f"• {i18n.profile_label(key, lang, fallback)}: {val}")
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


def _named_next_options(session: dict[str, Any] | None, language: str | None = None) -> list[tuple[str, str]]:
    lang = _lang(session, language=language)
    options = [
        ("another", i18n.t("named_next_another", lang)),
        ("Individual Schemes", i18n.t("named_next_individual", lang)),
        ("Family Schemes", i18n.t("named_next_family", lang)),
    ]
    if session and session.get("parked"):
        options.insert(0, ("resume", i18n.t("resume_opt", lang)))
    if _category_available():
        options.append(("Browse by category", i18n.t("named_next_category", lang)))
    options.append(("Main Menu", i18n.t("named_next_menu", lang)))
    options.append(("End Chat", i18n.t("end_opt_end", lang)))
    return options


def _named_next_prompt(session: dict[str, Any]) -> str:
    lang = _lang(session)
    options = _named_next_options(session, lang)
    session["named_next_options"] = [key for key, _label in options]
    lines = [i18n.t("named_next_intro", lang)]
    for i, (_key, label) in enumerate(options, 1):
        lines.append(f"{i}. {label}")
    return "\n".join(lines)


def _stash_named_next_options(session: dict[str, Any]) -> None:
    options = _named_next_options(session)
    session["named_next_options"] = [key for key, _label in options]


def _present_named_schemes(session: dict[str, Any], hits: list[dict[str, Any]]) -> str:
    lang = _lang(session)
    session["journey_id"] = None
    session["matched_schemes"] = hits
    _stash_named_next_options(session)
    if len(hits) == 1:
        session["phase"] = "named_scheme"
        session["selected_scheme_sn"] = hits[0].get("SN")
        return lookup.format_named_scheme_detail(hits[0], next_prompt="", language=lang)
    session["phase"] = "named_scheme_list"
    session["selected_scheme_sn"] = None
    return lookup.format_named_scheme_list(
        hits,
        i18n.t("named_list_intro", lang),
        i18n.t("named_list_footer", lang),
        language=lang,
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
    if action == "resume":
        if engine.restore_parked(session):
            return _resume_collect_prompt(session)
        session["phase"] = "main_menu"
        return _main_menu(session.get("language"))
    if action == "another":
        session["phase"] = "named_scheme_ask"
        return i18n.t("named_ask_another", session.get("language"))
    if action == "Individual Schemes":
        journey = _start_journey(session, "journey_1")
        return _begin_journey_reply(
            session, journey, i18n.t("individual_intro", session.get("language"))
        )
    if action == "Family Schemes":
        journey = _start_journey(session, "journey_2")
        return _begin_journey_reply(
            session, journey, i18n.t("family_intro", session.get("language"))
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
    if action == "End Chat":
        return _end_chat_reply(session)
    return None


def _detect_named_next(session: dict[str, Any], text: str) -> str | None:
    n = text.lower().strip()
    options = session.get("named_next_options") or [k for k, _ in _named_next_options(session)]
    if re.fullmatch(r"\d{1,2}", n):
        idx = int(n) - 1
        if 0 <= idx < len(options):
            return options[idx]
    if engine.is_resume_request(text) and session.get("parked"):
        return "resume"
    if nlu.detect_end_choice(text) == "Main Menu" or n in ("main menu", "menu"):
        return "Main Menu"
    if engine.is_hard_stop(text) or nlu.detect_end_choice(text) == "End Chat":
        return "End Chat"
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
    if engine.is_hard_stop(text) or greetings.is_pure_greeting(text):
        return None
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
            _stash_named_next_options(session)
            return lookup.format_named_scheme_detail(
                chosen, next_prompt="", language=session.get("language")
            )
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
                language=session.get("language"),
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
    engine.ensure_fields(session)
    session["path"] = None
    session["journey_id"] = journey_id
    session["phase"] = "collect_profile"
    session["slots"] = {}
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
    session["named_next_options"] = []
    session["prompted_slots"] = []
    session["collect_slot_id"] = None
    engine.seed_slots_from_known(session)
    return load_journey(journey_id)


def _ask_slot(slot: dict[str, Any], language: str | None = None, session: dict[str, Any] | None = None) -> str:
    """Fallback question used only when the LLM is unavailable or its reply is unusable."""
    lang = _lang(language=language)
    if session is not None:
        engine.set_current_slot(session, slot)
    return i18n.slot_prompt(slot["id"], lang, slot.get("prompt_hint"))


def _heard_prefix(applied: dict[str, str], language: str | None) -> str:
    if len(applied) < 2:
        return ""
    bits = engine.heard_you_bits(applied, language)
    if not bits:
        return ""
    return i18n.t("got_it", language, bits=bits)


def _after_collect_facts(
    session: dict[str, Any],
    journey: dict[str, Any],
    extracted: dict[str, str],
    *,
    llm_reply: str | None = None,
    switched_to: str | None = None,
) -> str:
    """Merge facts, then one next ask or confirm — never re-ask a filled slot."""
    prefer = None
    current = engine.current_collect_slot(session, journey)
    if current:
        prefer = current["id"]
    applied = engine.apply_facts(session, extracted, prefer=prefer)
    lang = _lang(session)
    missing = _missing_slots(journey, session.get("slots") or {})
    if not missing:
        session["collect_slot_id"] = None
        gated = _gate_collect_consent(session, None)
        if gated:
            heard = _heard_prefix(applied, lang)
            return (heard + "\n\n" + gated) if heard else gated
        if session.get("oneshot_profile") or (
            engine.has_enough_match_profile(applied)
            and engine.has_enough_match_profile(session.get("slots") or {})
        ):
            heard = _heard_prefix(applied, lang)
            listing = _emit_matches(session)
            return (heard + "\n\n" + listing) if heard else listing
        session["phase"] = "confirm_profile"
        summary = _profile_summary(session["slots"], session.get("journey_id"), lang)
        heard = _heard_prefix(applied, lang)
        if llm_reply and i18n.usable_collect_reply(llm_reply, lang, journey.get("slots") or []):
            body = llm_reply + "\n\n" + summary
            return (heard + "\n\n" + body) if heard else body
        return (heard + "\n\n" + summary) if heard else summary

    next_slot = missing[0]
    engine.set_current_slot(session, next_slot)
    parts: list[str] = []
    if switched_to:
        parts.append(i18n.t("language_switch_ack", lang))
    heard = _heard_prefix(applied, lang)
    if heard:
        parts.append(heard)
    elif applied and not llm_reply:
        parts.append(i18n.t("got_it_short", lang))
    question = None
    if i18n.usable_collect_reply(llm_reply, lang, missing):
        question = llm_reply.strip()
    if not question:
        question = _ask_slot(next_slot, lang, session)
    parts.append(question)
    return "\n\n".join(p for p in parts if p)


def _go_main_menu(session: dict[str, Any], *, greet: bool = False) -> str:
    lang = _lang(session)
    engine.clear_ephemeral_path(session)
    session["phase"] = "main_menu"
    body = _main_menu(lang)
    if greet:
        return i18n.t("greeting_ack", lang) + "\n\n" + body
    return body


def _with_resume_hint(session: dict[str, Any], reply: str) -> str:
    if not session.get("parked"):
        return reply
    lang = _lang(session)
    hint = i18n.t("resume_hint", lang)
    if hint in (reply or ""):
        return reply
    return (reply or "").rstrip() + "\n\n" + hint


def _apply_greeting(session: dict[str, Any]) -> str:
    """Fresh-session activation: language picker, same as a brand-new `hi`."""
    session["phase"] = "welcome_language"
    return _welcome()


def _end_chat_reply(session: dict[str, Any]) -> str:
    """Thank-you goodbye + feedback. Never re-show a scheme list."""
    lang = _lang(session)
    engine.clear_ephemeral_path(session)
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
    session["named_next_options"] = []
    session["parked"] = None
    session["journey_id"] = None
    session["path"] = None
    session["phase"] = "feedback"
    return i18n.t("goodbye_thanks", lang) + "\n\n" + i18n.t("feedback_prompt", lang)


def _resume_collect_prompt(session: dict[str, Any]) -> str:
    lang = _lang(session)
    journey = load_journey(session.get("journey_id"))
    missing = _missing_slots(journey, session.get("slots") or {})
    ack = i18n.t("resume_ack", lang)
    if not missing:
        session["phase"] = "confirm_profile"
        return ack + "\n\n" + _profile_summary(session.get("slots") or {}, session.get("journey_id"), lang)
    session["phase"] = "collect_profile"
    return ack + "\n\n" + _ask_slot(missing[0], lang, session)


def _begin_journey_reply(session: dict[str, Any], journey: dict[str, Any], intro: str) -> str:
    lang = _lang(session)
    missing = _missing_slots(journey, session.get("slots") or {})
    if missing and missing[0]["id"] == "state":
        return intro + "\n\n" + _ask_slot(missing[0], lang, session)
    gated = _gate_collect_consent(session, None)
    if gated:
        return intro + "\n\n" + gated
    if not missing:
        if session.get("oneshot_profile"):
            return intro + "\n\n" + _emit_matches(session)
        session["phase"] = "confirm_profile"
        return intro + "\n\n" + _profile_summary(session.get("slots") or {}, session.get("journey_id"), lang)
    return intro + "\n\n" + _ask_slot(missing[0], lang, session)


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
        engine.set_current_slot(session, missing_after[0])
        return reply
    parts: list[str] = []
    if switched_to:
        parts.append(i18n.t("language_switch_ack", lang))
    parts.append(_ask_slot(missing_after[0], lang, session))
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


def _capture_profile_text(session: dict[str, Any], text: str) -> dict[str, str]:
    """Extract every volunteered fact from a free-text dump into known_profile."""
    signals = profile_intent.extract_signals(text)
    session["profile_signals"] = signals
    facts = engine.facts_from_signals(text, signals)
    engine.merge_known_profile(session, facts)
    return facts


def _emit_matches(session: dict[str, Any]) -> str:
    matched, scope_note = eligibility.match_schemes(
        session.get("slots") or {}, journey_id=session.get("journey_id")
    )
    session["matched_schemes"] = matched
    session["phase"] = "scheme_list"
    return eligibility.format_scheme_list(
        matched, scope_note=scope_note, language=session.get("language")
    )


def _route_oneshot_profile(session: dict[str, Any], text: str) -> str | None:
    """Age + occupation + community (+ what schemes) → Individual match, not extra asks."""
    facts = _capture_profile_text(session, text)
    if not engine.has_enough_match_profile(facts):
        return None
    if not profile_intent.asks_for_schemes(text):
        return None
    session["oneshot_profile"] = True
    lang = session.get("language") or category_intent.infer_category_language(text)
    if lang and not session.get("language"):
        session["language"] = lang
    journey = _start_journey(session, "journey_1")
    return _begin_journey_reply(session, journey, i18n.t("individual_intro", _lang(session)))


def _route_idle_free_text(session: dict[str, Any], text: str) -> str | None:
    """Enforce free-text order: named (already tried) → category → shortcut/story → clarify."""
    if nlu.is_plain_menu_choice(text):
        return None
    if nlu.detect_language(text) and nlu._norm(text) in nlu.LANGUAGE_MAP:
        return None
    oneshot = _route_oneshot_profile(session, text)
    if oneshot:
        return oneshot
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
    engine.merge_known_profile(
        session, engine.facts_from_signals(text, session["profile_signals"])
    )
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
        return _begin_journey_reply(session, journey, i18n.t("individual_intro", lang))
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
        return _begin_journey_reply(session, journey, i18n.t("family_intro", lang))
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
        if session.get("oneshot_profile") and engine.has_enough_match_profile(
            session.get("slots") or {}
        ):
            return _emit_matches(session)
        session["phase"] = "confirm_profile"
        return pending or _profile_summary(
            session.get("slots") or {}, session.get("journey_id"), lang
        )
    session["phase"] = "collect_profile"
    if pending:
        journey = load_journey(session.get("journey_id"))
        missing = _missing_slots(journey, session.get("slots") or {})
        if missing:
            engine.set_current_slot(session, missing[0])
        return pending
    journey = load_journey(session.get("journey_id"))
    missing = _missing_slots(journey, session.get("slots") or {})
    if missing:
        return _ask_slot(missing[0], lang, session)
    if session.get("oneshot_profile"):
        return _emit_matches(session)
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
        + '  "ready_for_confirm": boolean true only when still_needed is empty.\n'
        + "You may extract extra optional fields if the user volunteers them.\n"
        + "Slots and allowed values (extract any of these; only still_needed are prompted):\n"
        + _slot_schema(journey)
        + count_note
        + "Extract every slot value present in this user message, even if mixed with a language-switch request.\n"
        + "The slot schema is for extraction only — never recite several fields or their option lists.\n"
        + "Never re-ask a field that is already in already_collected.\n"
        + "Write reply as a helpful WhatsApp chat: briefly acknowledge the user's words "
        + "(not slot-id labels like 'state: Karnataka'), then ask only "
        + f"the next needed fact ({next_id}) as ONE natural question.\n"
        + "Do not paste a long option menu — WhatsApp buttons/list will attach for closed choices.\n"
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
    if llm_lang in i18n.SUPPORTED and not session.get("language"):
        session["language"] = llm_lang

    extracted = engine.extract_turn(session, journey, text)
    extracted.update(_merge_llm_slots(data, allowed | {"age", "gender"}))
    reply = (data.get("reply") or "").strip()
    return _after_collect_facts(
        session, journey, extracted, llm_reply=reply, switched_to=switched_to
    )


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
            journey = _start_journey(session, "journey_2")
            return _begin_journey_reply(
                session, journey, i18n.t("family_intro", session.get("language"))
            )
        if choice == "Browse by category":
            started = category_path.start(session)
            return (reply + "\n\n" + started) if reply else started
        if choice == "Individual Schemes":
            journey = _start_journey(session, "journey_1")
            return _begin_journey_reply(
                session, journey, i18n.t("individual_intro", session.get("language"))
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


def _execute_interrupt(session: dict[str, Any], text: str, hit: engine.Interrupt) -> str | None:
    """Run a hard interrupt. Never append the previous slot question."""
    lang = _lang(session)
    if hit.kind == "resume":
        if engine.restore_parked(session):
            return _resume_collect_prompt(session)
        return _go_main_menu(session)
    if hit.kind == "main_menu":
        return _go_main_menu(session)
    if hit.kind == "help":
        engine.clear_ephemeral_path(session)
        session["phase"] = "help_crm"
        return i18n.t("help_intro", lang)
    if hit.kind == "stop":
        return _end_chat_reply(session)
    if hit.kind in ("named_scheme", "category", "shortcut", "wife"):
        engine.park_current(session)
        engine.merge_known_profile(session, session.get("slots") or {})
    if hit.kind == "named_scheme":
        found = _handle_named_scheme_intent(session, text)
        if found:
            return _with_resume_hint(session, found)
        return _with_resume_hint(session, _named_scheme_miss(session, text))
    if hit.kind == "category":
        routed = _start_known_or_unknown_category(session, text)
        if routed:
            return _with_resume_hint(session, routed)
        return None
    if hit.kind == "shortcut":
        oneshot = _route_oneshot_profile(session, text)
        if oneshot:
            return _with_resume_hint(session, oneshot)
        pack = profile_intent.detect_role_shortcut(text)
        if pack:
            kwargs: dict[str, Any] = {"language": lang}
            if pack == "disability":
                kwargs["pension_slice"] = True
            if pack == "women_child":
                kwargs["preset"] = {"who": "pregnant_lactating"}
            started = category_path.start_for_category(session, pack, **kwargs)
            return _with_resume_hint(session, started)
        return None
    if hit.kind == "wife":
        started = category_path.start_for_category(
            session, "women_child", language=lang, preset={"who": "adult_woman"}
        )
        return _with_resume_hint(session, started)
    if hit.kind == "menu_choice":
        choice = hit.payload
        if choice == "Individual Schemes":
            journey = _start_journey(session, "journey_1")
            return _begin_journey_reply(session, journey, i18n.t("individual_intro", lang))
        if choice == "Family Schemes":
            journey = _start_journey(session, "journey_2")
            return _begin_journey_reply(session, journey, i18n.t("family_intro", lang))
        if choice == "Browse by category":
            engine.park_current(session)
            started = _start_category_path(session)
            if started:
                return _with_resume_hint(session, started)
            return _go_main_menu(session)
    return None


def handle_message(user_id: str, text: str) -> str:
    reply = _handle_message_inner(user_id, text)
    return interactive.finalize(get_session(user_id), reply)


def _handle_message_inner(user_id: str, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Please send a short message and I’ll help."

    session = get_session(user_id)
    engine.ensure_fields(session)
    phase = session["phase"]
    low = text.lower().strip()

    # Greetings restart the whole workflow before language-switch / list / slots.
    # ("hi" must not be treated as the Hindi language code.)
    if greetings.is_explicit_restart(text) or greetings.is_pure_greeting(text):
        reset_session(user_id)
        session = get_session(user_id)
        return _welcome()

    switched_to = None
    if phase != "welcome_language":
        switched_to = _apply_language_switch(session, text)

    # Language-switch-only: stay on the current step in the new language.
    # Never send these turns to the LLM — it may invent a Hindi-only refusal.
    if phase not in ("welcome_language", "cat_language") and nlu.is_language_switch_only(text):
        if session.get("phase") == "consent":
            return _continue_after_language_switch(session)
        if session.get("path") == "category" or session.get("journey_id") == "schemes_by_category_v1":
            return category_path.replay_after_language_switch(session)
        return _continue_after_language_switch(session)

    if engine.is_resume_request(text) and session.get("parked"):
        if engine.restore_parked(session):
            return _resume_collect_prompt(session)

    hard = engine.detect_hard_interrupt(session, text)
    if hard:
        executed = _execute_interrupt(session, text, hard)
        if executed is not None:
            return executed

    if phase in engine.INTERRUPTIBLE_PHASES:
        hit = engine.detect_interrupt(session, text)
        if hit:
            executed = _execute_interrupt(session, text, hit)
            if executed is not None:
                return executed

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
            return _begin_journey_reply(
                session, journey, i18n.t("family_intro", session.get("language"))
            )
        journey = _start_journey(session, "journey_1")
        return _begin_journey_reply(
            session, journey, i18n.t("individual_intro", session.get("language"))
        )

    # ---- help / CRM ----
    if phase == "help_crm":
        if nlu.is_plain_menu_choice(text):
            choice = nlu.detect_menu(text)
            if choice == "Individual Schemes":
                journey = _start_journey(session, "journey_1")
                return _begin_journey_reply(
                    session, journey, i18n.t("individual_intro", session.get("language"))
                )
            if choice == "Family Schemes":
                journey = _start_journey(session, "journey_2")
                return _begin_journey_reply(
                    session, journey, i18n.t("family_intro", session.get("language"))
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

        extracted = engine.extract_turn(session, journey, text)
        missing = _missing_slots(journey, session.get("slots") or {})
        lang = session.get("language")
        if not extracted and missing:
            prefix = ""
            if switched_to:
                prefix = i18n.t("language_switch_ack", lang) + "\n\n"
            return prefix + i18n.t("didnt_catch", lang) + " " + _ask_slot(missing[0], lang, session)

        next_reply = _after_collect_facts(
            session, journey, extracted, switched_to=switched_to
        )
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
            session["prompted_slots"] = []
            session["collect_slot_id"] = None
            profile = session.setdefault("known_profile", {})
            for key in engine.collect_slot_ids(session.get("journey_id")):
                if key != "state":
                    profile.pop(key, None)
            missing = _missing_slots(journey, session["slots"])
            ask = missing[0] if missing else None
            if not ask:
                session["phase"] = "confirm_profile"
                return _profile_summary(session["slots"], session.get("journey_id"), session.get("language"))
            return (
                i18n.t("edit_ack", session.get("language"))
                + "\n\n"
                + _ask_slot(ask, session.get("language"), session)
            )
        if decision != "Proceed":
            return i18n.t("confirm_unclear", session.get("language"))

        # Rules own the list body: scope note + intro + numbered lines + footer.
        # Never prepend LLM prose (it dumps unnumbered bullets in production).
        return _emit_matches(session)

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
                clarify = _safe_user_reply(data.get("reply"))
                if clarify and not eligibility.llm_lists_schemes(clarify):
                    return clarify
        if not chosen:
            if "edit" in low:
                session["phase"] = "confirm_profile"
                return _profile_summary(
                    session["slots"], session.get("journey_id"), session.get("language")
                )
            return (
                i18n.t("scheme_pick", session.get("language"))
                + "\n\n"
                + eligibility.format_scheme_list(schemes, language=session.get("language"))
            )
        session["selected_scheme_sn"] = chosen.get("SN")
        session["phase"] = "scheme_detail"
        convo = _conversational_openers("scheme_detail", session, text)
        if convo:
            return convo
        return eligibility.format_scheme_detail(
            chosen,
            language=session.get("language"),
        )

    # ---- scheme detail ----
    if phase == "scheme_detail":
        action = nlu.detect_after_scheme(text)
        if action == "I need help":
            session["phase"] = "help_crm"
            return i18n.t("help_intro", session.get("language"))
        if action in ("View other schemes", "Go Back") or "other" in low or "list" in low or "back" in low:
            session["phase"] = "scheme_list"
            return eligibility.format_scheme_list(
                session.get("matched_schemes") or [], language=session.get("language")
            )
        schemes = session.get("matched_schemes") or []
        chosen = nlu.match_scheme_choice(text, schemes)
        if chosen:
            session["selected_scheme_sn"] = chosen.get("SN")
            convo = _conversational_openers("scheme_detail", session, text)
            if convo:
                return convo
            return eligibility.format_scheme_detail(
                chosen,
                language=session.get("language"),
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
            return _go_main_menu(session)
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
