"""Isolated Browse-by-category / Find-by-topic workflow (schemes_by_category_v1).

Does not mutate Journey 1 / Journey 2 slot collection. Existing sessions without
path=category never enter this module.

`start()` is menu button 3 (language → state → hub).
`start_for_category()` is a free-text topic keyword (language if needed → state → pack).
"""

from __future__ import annotations

import re
from typing import Any

from . import category_catalog as cat
from . import category_intent, consent, eligibility, i18n, nlu


def start(session: dict[str, Any]) -> str:
    """Enter the category path from main menu button 3 only."""
    _reset_category_session(session, category_id=None)
    session["phase"] = "cat_language"
    return _language_prompt(session)


def start_for_category(
    session: dict[str, Any],
    category_id: str,
    language: str | None = None,
    preset: dict[str, str] | None = None,
    pension_slice: bool = False,
) -> str:
    """Enter a known pack from free-text intent — skip the hub."""
    _reset_category_session(session, category_id=category_id)
    if language:
        session["language"] = language
    session["pack_preset"] = dict(preset or {})
    session["pension_slice"] = bool(pension_slice)
    lang = session.get("language")
    label = cat.label_of(category_id, lang)
    ack = i18n.t("cat_intent_ack", lang, category=label)
    if not session.get("language"):
        session["phase"] = "cat_language"
        return ack + "\n\n" + _language_prompt(session)
    session["phase"] = "cat_state_scope"
    return ack + "\n\n" + _state_scope_prompt(session)


def _reset_category_session(session: dict[str, Any], category_id: str | None) -> None:
    from . import conversation_engine as engine

    engine.ensure_fields(session)
    known = dict(session.get("known_profile") or {})
    session["path"] = cat.PATH_FLAG
    session["journey_id"] = cat.WORKFLOW_ID
    session["slots"] = {}
    if known.get("state"):
        session["slots"]["state"] = known["state"]
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
    session["category_id"] = category_id
    session["state_scope"] = None
    session["hub_screen"] = 1
    session["pension_slice"] = False
    session["cat_q_index"] = 0
    session["known_profile"] = known


def _after_state_ready(session: dict[str, Any]) -> str:
    """Hub when browsing; pack questions when the category is already known."""
    if consent.should_gate(session):
        session["phase"] = "consent"
        session["consent_resume"] = "category"
        return consent.prompt(session)
    cid = session.get("category_id")
    if cid and cid in cat.PACKS:
        return _begin_pack(session, cid)
    session["phase"] = "cat_hub"
    session["hub_screen"] = 1
    return _hub_prompt(session)


def after_consent(session: dict[str, Any]) -> str:
    """Continue the category path after the user accepts consent."""
    session["consent"] = "accepted"
    return _after_state_ready(session)


def replay_after_language_switch(session: dict[str, Any]) -> str:
    """Re-show the current category step in the new session language."""
    return i18n.t("language_switch_ack", session.get("language")) + "\n\n" + current_prompt(session)


def current_prompt(session: dict[str, Any]) -> str:
    phase = session.get("phase") or "cat_language"
    lang = session.get("language")
    if phase == "cat_language":
        return _language_prompt(session)
    if phase == "cat_state_scope":
        return _state_scope_prompt(session)
    if phase == "cat_state_plus":
        return i18n.t("cat_state_plus_prompt", lang) + "\n\n" + _numbered(cat.STATE_PLUS_CENTRAL, lang)
    if phase == "cat_hub":
        return _hub_prompt(session)
    if phase == "cat_who":
        return _who_prompt(session)
    if phase == "cat_collect":
        return _question_prompt(session)
    if phase == "cat_results":
        schemes = session.get("matched_schemes") or []
        if not schemes:
            return i18n.t("cat_no_match", lang) + "\n\n" + i18n.t("cat_results_footer", lang)
        return eligibility.format_scheme_list(
            schemes,
            footer=_results_footer(lang),
            intro=i18n.t("cat_results_intro", lang),
            language=lang,
        )
    if phase == "cat_detail":
        scheme_sn = session.get("selected_scheme_sn")
        schemes = session.get("matched_schemes") or []
        scheme = next((s for s in schemes if str(s.get("SN")) == str(scheme_sn)), None)
        if scheme:
            return eligibility.format_scheme_detail(
                scheme,
                language=lang,
            )
        return i18n.t("cat_after_detail", lang)
    return _hub_prompt(session)


def handle(
    session: dict[str, Any],
    text: str,
    user_id: str,
    switched_to: str | None = None,
) -> str:
    phase = session.get("phase") or "cat_language"

    if _wants_main_menu(text) and phase not in ("cat_language",):
        return _to_main_menu(session)

    if nlu.is_language_switch_only(text) and phase != "cat_language":
        return replay_after_language_switch(session)

    if phase == "cat_language":
        return _on_language(session, text)
    if phase == "cat_state_scope":
        prefix = _switch_ack(session, switched_to)
        return prefix + _on_state_scope(session, text)
    if phase == "cat_state_plus":
        prefix = _switch_ack(session, switched_to)
        return prefix + _on_state_plus(session, text)
    if phase == "cat_hub":
        prefix = _switch_ack(session, switched_to)
        return prefix + _on_hub(session, text)
    if phase == "cat_who":
        prefix = _switch_ack(session, switched_to)
        return prefix + _on_who_first(session, text)
    if phase == "cat_collect":
        prefix = _switch_ack(session, switched_to)
        return prefix + _on_collect(session, text)
    if phase == "cat_results":
        return _on_results(session, text)
    if phase == "cat_detail":
        return _on_detail(session, text)

    session["phase"] = "cat_hub"
    return _hub_prompt(session)


def _switch_ack(session: dict[str, Any], switched_to: str | None) -> str:
    if not switched_to:
        return ""
    return i18n.t("language_switch_ack", session.get("language")) + "\n\n"


def _wants_main_menu(text: str) -> bool:
    n = nlu._norm(text)
    return nlu.detect_end_choice(text) == "Main Menu" or n in (
        "main menu",
        "menu",
        "start over",
        "मुख्य मेनू",
    )


def _wants_categories(text: str) -> bool:
    n = nlu._norm(text)
    return any(
        p in n
        for p in (
            "back to categories",
            "back to category",
            "category hub",
            "श्रेणियों",
        )
    ) or n in ("back", "back to list", "categories", "श्रेणियाँ", "और श्रेणियाँ")


def _to_main_menu(session: dict[str, Any]) -> str:
    from . import conversation_engine as engine

    lang = session.get("language")
    engine.clear_ephemeral_path(session)
    session["phase"] = "main_menu"
    return i18n.t("main_menu", lang)


def _back_to_hub(session: dict[str, Any]) -> str:
    keep_state = session.get("slots", {}).get("state")
    keep_scope = session.get("state_scope")
    session["slots"] = {}
    if keep_state:
        session["slots"]["state"] = keep_state
    session["state_scope"] = keep_scope
    session["category_id"] = None
    session["pension_slice"] = False
    session["cat_q_index"] = 0
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
    session["hub_screen"] = 1
    session["phase"] = "cat_hub"
    return _hub_prompt(session)


def _pick(text: str, options: list[dict[str, Any] | str], language: str | None) -> int | None:
    n = nlu._norm(text)
    if not n:
        return None
    m = re.fullmatch(r"(\d{1,2})[).]?", n)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(options):
            return idx
    for i, opt in enumerate(options):
        if isinstance(opt, str):
            oid = opt
            labels = [cat.label_of(opt, language), cat.label_of(opt, "English"), cat.label_of(opt, "Hindi"), oid]
        else:
            oid = str(opt.get("id") or "")
            labels = [
                oid,
                cat.label_of(opt, language),
                cat.label_of(opt, "English"),
                cat.label_of(opt, "Hindi"),
                str(opt.get("English") or ""),
                str(opt.get("Hindi") or ""),
            ]
        for lab in labels:
            lab_n = nlu._norm(lab)
            if not lab_n:
                continue
            if n == lab_n:
                return i
            if len(lab_n) >= 4 and lab_n in n:
                return i
            if len(n) >= 4 and n in lab_n:
                return i
    return None


def _numbered(options: list[dict[str, Any] | str], language: str | None) -> str:
    lines = []
    for i, opt in enumerate(options, 1):
        lines.append(f"{i}. {cat.label_of(opt, language)}")
    return "\n".join(lines)


def _language_prompt(session: dict[str, Any]) -> str:
    lang = session.get("language") or "English"
    header = i18n.t("cat_language_prompt", lang)
    return header + "\n\n" + _numbered(cat.LANGUAGES, lang)


def _on_language(session: dict[str, Any], text: str) -> str:
    idx = _pick(text, cat.LANGUAGES, session.get("language"))
    if idx is None:
        detected = nlu.detect_language(text) or nlu.detect_language_switch(text)
        if detected:
            session["language"] = detected
            session["phase"] = "cat_state_scope"
            return _state_scope_prompt(session)
        return i18n.t("cat_language_unclear", session.get("language")) + "\n\n" + _language_prompt(session)
    session["language"] = cat.LANGUAGES[idx]["id"]
    session["phase"] = "cat_state_scope"
    return _state_scope_prompt(session)


def _state_scope_prompt(session: dict[str, Any]) -> str:
    lang = session.get("language")
    return i18n.t("cat_state_prompt", lang) + "\n\n" + _numbered(cat.STATE_SCOPES, lang)


def _apply_scope(session: dict[str, Any], scope_id: str, state: str | None = None) -> None:
    session["state_scope"] = scope_id
    slots = session.setdefault("slots", {})
    if scope_id == "karnataka":
        slots["state"] = "Karnataka"
    elif scope_id == "maharashtra":
        slots["state"] = "Maharashtra"
    elif scope_id == "central":
        slots.pop("state", None)
    elif scope_id == "state_central" and state:
        slots["state"] = state


def _on_state_scope(session: dict[str, Any], text: str) -> str:
    idx = _pick(text, cat.STATE_SCOPES, session.get("language"))
    if idx is None:
        # Allow typing a state name as Karnataka / Maharashtra shortcut
        state = nlu.detect_state(text)
        if state == "Karnataka":
            _apply_scope(session, "karnataka")
            return _after_state_ready(session)
        if state == "Maharashtra":
            _apply_scope(session, "maharashtra")
            return _after_state_ready(session)
        return i18n.t("cat_pick_number", session.get("language")) + "\n\n" + _state_scope_prompt(session)
    scope_id = cat.STATE_SCOPES[idx]["id"]
    if scope_id == "state_central":
        session["phase"] = "cat_state_plus"
        lang = session.get("language")
        return i18n.t("cat_state_plus_prompt", lang) + "\n\n" + _numbered(cat.STATE_PLUS_CENTRAL, lang)
    _apply_scope(session, scope_id)
    return _after_state_ready(session)


def _on_state_plus(session: dict[str, Any], text: str) -> str:
    idx = _pick(text, cat.STATE_PLUS_CENTRAL, session.get("language"))
    if idx is None:
        state = nlu.detect_state(text)
        if state in ("Karnataka", "Maharashtra"):
            _apply_scope(session, "state_central", state)
            return _after_state_ready(session)
        return (
            i18n.t("cat_pick_number", session.get("language"))
            + "\n\n"
            + i18n.t("cat_state_plus_prompt", session.get("language"))
            + "\n\n"
            + _numbered(cat.STATE_PLUS_CENTRAL, session.get("language"))
        )
    state = "Karnataka" if cat.STATE_PLUS_CENTRAL[idx]["id"] == "karnataka" else "Maharashtra"
    _apply_scope(session, "state_central", state)
    return _after_state_ready(session)


def _hub_ids(session: dict[str, Any]) -> list[str]:
    screen = session.get("hub_screen") or 1
    return list(cat.HUB_2 if screen == 2 else cat.HUB_1)


def _hub_prompt(session: dict[str, Any]) -> str:
    lang = session.get("language")
    ids = _hub_ids(session)
    header = (
        i18n.t("cat_hub2_prompt", lang)
        if session.get("hub_screen") == 2
        else i18n.t("cat_hub_prompt", lang)
    )
    return header + "\n\n" + _numbered(ids, lang)


def _on_hub(session: dict[str, Any], text: str) -> str:
    ids = _hub_ids(session)
    idx = _pick(text, ids, session.get("language"))
    if idx is None:
        typed = category_intent.detect_category_intent(text)
        if typed and typed in cat.PACKS:
            return _begin_pack(session, typed)
        return i18n.t("cat_pick_number", session.get("language")) + "\n\n" + _hub_prompt(session)
    chosen = ids[idx]
    if chosen == "more":
        session["hub_screen"] = 2
        return _hub_prompt(session)
    if chosen == "back":
        session["hub_screen"] = 1
        return _hub_prompt(session)
    if chosen == "family_who":
        session["phase"] = "cat_who"
        return _who_prompt(session)
    return _begin_pack(session, chosen)


def _who_prompt(session: dict[str, Any]) -> str:
    lang = session.get("language")
    return i18n.t("cat_who_prompt", lang) + "\n\n" + _numbered(cat.WHO_FIRST, lang)


def _on_who_first(session: dict[str, Any], text: str) -> str:
    idx = _pick(text, cat.WHO_FIRST, session.get("language"))
    if idx is None:
        return i18n.t("cat_pick_number", session.get("language")) + "\n\n" + _who_prompt(session)
    item = cat.WHO_FIRST[idx]
    if item.get("route") == "back":
        session["phase"] = "cat_hub"
        session["hub_screen"] = 2
        return _hub_prompt(session)
    session["pension_slice"] = bool(item.get("pension_slice"))
    preset = dict(item.get("preset") or {})
    return _begin_pack(session, item["route"], preset=preset)


def _begin_pack(
    session: dict[str, Any],
    category_id: str,
    preset: dict[str, str] | None = None,
) -> str:
    slots = session.setdefault("slots", {})
    # Drop previous pack answers; keep state from the scope step.
    state = slots.get("state")
    session["slots"] = {}
    if state:
        session["slots"]["state"] = state
    if preset:
        session["slots"].update(preset)
    else:
        packed = session.pop("pack_preset", None) or {}
        if packed:
            session["slots"].update(packed)
    session["category_id"] = category_id
    session["cat_q_index"] = 0
    session["phase"] = "cat_collect"
    questions = cat.questions_for(category_id, session["slots"])
    # Skip questions already filled by who-first presets
    while session["cat_q_index"] < len(questions) and session["slots"].get(questions[session["cat_q_index"]]["id"]):
        session["cat_q_index"] += 1
    if session["cat_q_index"] >= len(questions):
        return _run_match(session)
    return _question_prompt(session)


def _question_prompt(session: dict[str, Any]) -> str:
    lang = session.get("language")
    category_id = session.get("category_id") or ""
    questions = cat.questions_for(category_id, session.get("slots"))
    idx = session.get("cat_q_index") or 0
    q = questions[idx]
    total = len(questions)
    cat_label = cat.label_of(category_id, lang)
    header = i18n.t("cat_question_header", lang, category=cat_label, n=str(idx + 1), total=str(total))
    pack = cat.PACKS.get(category_id) or {}
    hint = ""
    if idx == 0:
        show = pack.get("show_hint") or {}
        hint_text = cat.label_of(show, lang) if show else ""
        if hint_text:
            hint = hint_text + "\n\n"
    body = cat.label_of(q, lang)
    return f"{header}\n\n{hint}{body}\n\n{_numbered(q['options'], lang)}"


def _on_collect(session: dict[str, Any], text: str) -> str:
    if _wants_categories(text):
        return _back_to_hub(session)
    category_id = session.get("category_id") or ""
    questions = cat.questions_for(category_id, session.get("slots"))
    idx = session.get("cat_q_index") or 0
    if idx >= len(questions):
        return _run_match(session)
    q = questions[idx]
    pick = _pick(text, q["options"], session.get("language"))
    if pick is None:
        return i18n.t("cat_pick_number", session.get("language")) + "\n\n" + _question_prompt(session)
    chosen = q["options"][pick]
    session.setdefault("slots", {})[q["id"]] = chosen["id"]
    session["cat_q_index"] = idx + 1
    # Recompute remaining (labour board_state may skip after state is known)
    questions = cat.questions_for(category_id, session.get("slots"))
    if session["cat_q_index"] >= len(questions):
        return _run_match(session)
    return _question_prompt(session)


def _results_footer(language: str | None) -> str:
    return i18n.t("cat_results_footer", language)


def _slots_for_match(session: dict[str, Any]) -> dict[str, str]:
    """Category answers plus known_profile facts (exact age, minority, …)."""
    slots = dict(session.get("slots") or {})
    known = session.get("known_profile") or {}
    for key in (
        "age",
        "age_group",
        "occupation",
        "social_category",
        "gender",
        "household_income",
    ):
        if known.get(key) and not slots.get(key):
            slots[key] = known[key]
    return slots


def _run_match(session: dict[str, Any]) -> str:
    category_id = session.get("category_id") or ""
    matched, scope_note = eligibility.match_category_schemes(
        _slots_for_match(session),
        category_id,
        scope=session.get("state_scope"),
        pension_slice=bool(session.get("pension_slice")),
    )
    session["matched_schemes"] = matched
    session["phase"] = "cat_results"
    lang = session.get("language")
    if not matched:
        empty = i18n.t("cat_no_match", lang)
        return empty + "\n\n" + i18n.t("cat_results_footer", lang)
    listing = eligibility.format_scheme_list(
        matched,
        scope_note=scope_note,
        footer=_results_footer(lang),
        intro=i18n.t("cat_results_intro", lang),
        language=lang,
    )
    return listing


def _on_results(session: dict[str, Any], text: str) -> str:
    if _wants_categories(text):
        return _back_to_hub(session)
    schemes = session.get("matched_schemes") or []
    if not schemes:
        return (
            i18n.t("cat_no_match", session.get("language"))
            + "\n\n"
            + i18n.t("cat_results_footer", session.get("language"))
        )
    chosen = nlu.match_scheme_choice(text, schemes)
    if not chosen:
        return (
            i18n.t("scheme_pick", session.get("language"))
            + "\n\n"
            + eligibility.format_scheme_list(
                schemes,
                footer=_results_footer(session.get("language")),
                intro=i18n.t("cat_results_intro", session.get("language")),
                language=session.get("language"),
            )
        )
    session["selected_scheme_sn"] = chosen.get("SN")
    session["phase"] = "cat_detail"
    return eligibility.format_scheme_detail(
        chosen,
        language=session.get("language"),
    )


def _on_detail(session: dict[str, Any], text: str) -> str:
    n = nlu._norm(text)
    if _wants_categories(text):
        return _back_to_hub(session)
    if nlu.detect_after_scheme(text) in ("View other schemes", "Go Back") or "list" in n or "other" in n:
        session["phase"] = "cat_results"
        schemes = session.get("matched_schemes") or []
        return eligibility.format_scheme_list(
            schemes,
            footer=_results_footer(session.get("language")),
            intro=i18n.t("cat_results_intro", session.get("language")),
            language=session.get("language"),
        )
    if nlu.detect_after_scheme(text) == "I need help":
        session["path"] = None
        session["journey_id"] = None
        session["phase"] = "help_crm"
        return i18n.t("help_intro", session.get("language"))
    schemes = session.get("matched_schemes") or []
    chosen = nlu.match_scheme_choice(text, schemes)
    if chosen:
        session["selected_scheme_sn"] = chosen.get("SN")
        return eligibility.format_scheme_detail(
            chosen,
            language=session.get("language"),
        )
    return i18n.t("cat_after_detail", session.get("language"))
