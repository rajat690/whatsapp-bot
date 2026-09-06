"""Conversation-first Journey 1 + Journey 2 orchestrator with deterministic checkpoints."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import eligibility, i18n, llm, nlu
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
Languages: greet/accept English, Hindi, Marathi, Kannada.
Always reply in the session language. Never revert to an earlier language.
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
    """Persist a mid-flow language change. Returns the new language or None."""
    new_lang = nlu.detect_language_switch(text)
    if new_lang and new_lang != session.get("language"):
        session["language"] = new_lang
        return new_lang
    return None


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


def _start_journey(session: dict[str, Any], journey_id: str) -> dict[str, Any]:
    session["journey_id"] = journey_id
    session["phase"] = "collect_profile"
    session["slots"] = {}
    session["matched_schemes"] = []
    session["selected_scheme_sn"] = None
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


def _welcome() -> str:
    return (
        "Hi! Welcome to SETU. I can help you discover government schemes "
        "or get support with an issue.\n\n"
        "Which language would you like to continue in?\n"
        "English / Hindi / Marathi / Kannada"
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
            '{"language": "English"|"Hindi"|"Marathi"|"Kannada"|null, "reply": "..."}. '
            "If unclear, ask again. If set, greet briefly IN THAT LANGUAGE and ask "
            "Individual Schemes / Family Schemes / Help. Ask only that one menu question."
        )
        data = llm.chat_json(system, text, temperature=0.4)
        if not data:
            return None
        lang = data.get("language")
        if lang in ("English", "Hindi", "Marathi", "Kannada"):
            session["language"] = lang
            session["phase"] = "main_menu"
        reply = (data.get("reply") or "").strip()
        return reply or None

    if phase == "main_menu":
        system = (
            SYSTEM_PERSONA
            + i18n.language_instruction(session.get("language"))
            + "\nUser is at main menu. Return JSON: "
            '{"choice": "Individual Schemes"|"Family Schemes"|"I need help"|null, "reply": "..."}. '
            "If Individual Schemes, start collecting an individual profile conversationally (ask state first). "
            "If Family Schemes, start collecting a household profile conversationally (ask state first). "
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
        reply = (data.get("reply") or "").strip()
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
        if choice == "Individual Schemes":
            _start_journey(session, "journey_1")
            return reply or (
                "Great. I’ll ask a few quick questions about you, in plain chat.\n\n"
                "Which state do you live in?"
            )
        return reply or "You can say Individual Schemes, Family Schemes, or I need help."

    if phase == "help_crm":
        system = (
            SYSTEM_PERSONA
            + i18n.language_instruction(session.get("language"))
            + "\nUser is describing a support issue. Acknowledge warmly in JSON: "
            '{"reply": "...", "summary": "short issue summary"}.'
        )
        data = llm.chat_json(system, text, temperature=0.4)
        summary = text
        reply = None
        if data:
            summary = data.get("summary") or text
            reply = (data.get("reply") or "").strip()
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
        return text_out
    return None


def handle_message(user_id: str, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Please send a short message and I’ll help."

    session = get_session(user_id)
    journey = load_journey(session.get("journey_id"))
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
            warm = llm.chat_text(
                SYSTEM_PERSONA
                + "\nUser just said hi. Welcome them to SETU and ask language: English/Hindi/Marathi/Kannada. Plain text only.",
                text,
                temperature=0.6,
            )
            if warm:
                return warm
        return _welcome()

    # ---- welcome / language ----
    if phase == "welcome_language":
        convo = _conversational_openers(phase, session, text)
        if convo:
            return convo
        lang = nlu.detect_language(text)
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
        convo = _conversational_openers(phase, session, text)
        if convo:
            return convo
        choice = nlu.detect_menu(text)
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
            return "\n\n".join(parts)

        session["phase"] = "confirm_profile"
        return _profile_summary(session["slots"], session.get("journey_id"), lang)

    # ---- confirm profile (deterministic branch) ----
    if phase == "confirm_profile":
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
            if intro:
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
            elif data and data.get("reply") and not chosen:
                return str(data["reply"]).strip()
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
                ans = llm.chat_text(
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
                if ans:
                    return ans
        session["phase"] = "end_menu"
        return i18n.t("end_menu", session.get("language"))

    # ---- end menu ----
    if phase == "end_menu":
        choice = nlu.detect_end_choice(text)
        if choice == "Main Menu":
            session["phase"] = "main_menu"
            session["journey_id"] = None
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
