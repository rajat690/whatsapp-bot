"""Conversation-first Journey 1 orchestrator with deterministic checkpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import eligibility, llm, nlu
from .session import get_session, reset_session

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SYSTEM_PERSONA = """You are SETU, a warm WhatsApp assistant that helps people in India discover government schemes.
Style: short, natural chat messages (2-5 sentences max). No markdown tables. Light WhatsApp formatting (*bold*) sparingly.
You may ask clarifying questions. Never invent scheme eligibility — the app will run a deterministic matcher.
Languages: greet/accept English, Hindi, Marathi, Kannada; reply in the user's chosen language when possible, otherwise English.
"""


def load_journey() -> dict[str, Any]:
    with (DATA_DIR / "journey1.json").open(encoding="utf-8") as f:
        return json.load(f)


def _missing_slots(journey: dict[str, Any], slots: dict[str, str]) -> list[dict[str, Any]]:
    missing = []
    for slot in journey["slots"]:
        if slot.get("required") and not slots.get(slot["id"]):
            missing.append(slot)
    return missing


def _profile_summary(slots: dict[str, str]) -> str:
    labels = {
        "state": "State",
        "age_group": "Age group",
        "occupation": "Occupation",
        "household_income": "Household income",
        "social_category": "Social category",
        "marital_status": "Marital status",
        "disability": "Disability",
    }
    lines = ["Here’s what I have so far:"]
    for key, label in labels.items():
        lines.append(f"• {label}: {slots.get(key, '—')}")
    lines.append("")
    lines.append("Does this look right? Reply *Proceed* or *Edit details*.")
    return "\n".join(lines)


def _ask_slot(slot: dict[str, Any]) -> str:
    hint = slot.get("prompt_hint") or f"Please share your {slot['id']}."
    options = slot.get("options")
    if options:
        return f"{hint}\n(You can reply in your own words. Examples: {', '.join(options[:5])}…)"
    return f"{hint}\n(You can reply in your own words.)"


def _welcome() -> str:
    return (
        "Hi! Welcome to SETU. I can help you discover government schemes "
        "or get support with an issue.\n\n"
        "Which language would you like to continue in?\n"
        "English / Hindi / Marathi / Kannada"
    )


def _main_menu() -> str:
    return (
        "What would you like to explore today?\n"
        "• Individual Schemes\n"
        "• Family Schemes\n"
        "• I need help\n\n"
        "Just type your choice in your own words."
    )


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
        if k in allowed and v not in (None, "", "null", "unknown"):
            out[k] = str(v).strip()
    return out


def _conversational_collect(session: dict[str, Any], journey: dict[str, Any], text: str) -> str | None:
    """LLM-powered profile collection. Returns reply or None to fall back."""
    if not llm.llm_configured():
        return None

    missing = _missing_slots(journey, session["slots"])
    missing_ids = [m["id"] for m in missing]
    allowed = {s["id"] for s in journey["slots"]}

    system = (
        SYSTEM_PERSONA
        + "\nYou are collecting a short eligibility profile for Individual Schemes.\n"
        + "Return ONLY JSON with keys:\n"
        + '  "slots": object with any newly inferred fields from this user message,\n'
        + '  "reply": your next WhatsApp message to the user,\n'
        + '  "ready_for_confirm": boolean true only when ALL required slots are filled.\n'
        + "Required slots and allowed values:\n"
        + _slot_schema(journey)
        + "\nAge group must be exactly one of: 0–17 | 18–59 | 60+.\n"
        + "If the user asks something off-topic, answer briefly then continue collecting.\n"
        + "Do not list schemes yet. Do not claim eligibility.\n"
    )
    user = json.dumps(
        {
            "language": session.get("language"),
            "already_collected": session.get("slots") or {},
            "still_needed": missing_ids,
            "user_message": text,
        },
        ensure_ascii=False,
    )
    data = llm.chat_json(system, user, temperature=0.3)
    if not data:
        return None

    extracted = _merge_llm_slots(data, allowed)
    # Also run keyword NLU as backup fill
    extracted.update(nlu.extract_slots(text, journey["slots"], prefer_slot=missing_ids[0] if missing_ids else None))
    # Prefer LLM values when both present
    llm_only = _merge_llm_slots(data, allowed)
    extracted.update(llm_only)
    session["slots"].update(extracted)

    reply = (data.get("reply") or "").strip()
    missing_after = _missing_slots(journey, session["slots"])
    ready = bool(data.get("ready_for_confirm")) and not missing_after
    if ready or not missing_after:
        session["phase"] = "confirm_profile"
        # Prefer a conversational confirm if LLM gave one, else template
        if reply and data.get("ready_for_confirm"):
            return reply + "\n\n" + _profile_summary(session["slots"])
        return _profile_summary(session["slots"])

    if reply:
        return reply
    if missing_after:
        return _ask_slot(missing_after[0])
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
            "If unclear, ask again. If set, greet briefly and ask Individual Schemes / Family Schemes / Help."
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
            + "\nUser is at main menu. Return JSON: "
            '{"choice": "Individual Schemes"|"Family Schemes"|"I need help"|null, "reply": "..."}. '
            "If Individual Schemes, start collecting profile conversationally (ask state first). "
            "If Family Schemes, say coming soon and re-offer menu. "
            "If help, ask what support they need."
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
        if choice == "Family Schemes":
            return reply or (
                "Family Schemes is coming soon in this prototype.\n\n" + _main_menu()
            )
        if choice == "I need help":
            session["phase"] = "help_crm"
            return reply or (
                "Sure — tell me briefly what you need help with and I’ll raise a support request."
            )
        if choice == "Individual Schemes":
            session["phase"] = "collect_profile"
            session["slots"] = {}
            return reply or (
                "Great. I’ll ask a few quick questions about you, in plain chat.\n\n"
                "Which state do you live in?"
            )
        return reply or "You can say Individual Schemes, Family Schemes, or I need help."

    if phase == "help_crm":
        system = (
            SYSTEM_PERSONA
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
        system = (
            SYSTEM_PERSONA
            + "\nExplain this scheme simply for WhatsApp. Return plain text only (no JSON). "
            "Include benefit, who it is for, and that official verification is needed. "
            "End by offering help or other schemes."
        )
        user = json.dumps(scheme, ensure_ascii=False)[:4000]
        text_out = llm.chat_text(system, user, temperature=0.5)
        return text_out
    return None


def handle_message(user_id: str, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Please send a short message and I’ll help."

    journey = load_journey()
    session = get_session(user_id)
    phase = session["phase"]
    low = text.lower().strip()

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
        return f"Great — continuing in {lang}.\n\n" + _main_menu()

    # ---- main menu ----
    if phase == "main_menu":
        convo = _conversational_openers(phase, session, text)
        if convo:
            return convo
        choice = nlu.detect_menu(text)
        if not choice:
            return "Please choose Individual Schemes, Family Schemes, or I need help."
        if choice == "Family Schemes":
            return (
                "Family Schemes (Journey 2) is coming soon in this prototype.\n\n"
                + _main_menu()
            )
        if choice == "I need help":
            session["phase"] = "help_crm"
            return (
                "I can help with that. Please tell me briefly what you need "
                "support with, and I’ll create a support request for the SETU team."
            )
        session["phase"] = "collect_profile"
        session["slots"] = {}
        return (
            "You’ve chosen Individual Schemes. I’ll ask a few short questions "
            "so I can show schemes that may be relevant to you.\n\n"
            + _ask_slot(journey["slots"][0])
        )

    # ---- help / CRM ----
    if phase == "help_crm":
        convo = _conversational_openers(phase, session, text)
        if convo:
            return convo
        print(f"CRM_TICKET user={user_id} issue={text}", flush=True)
        session["phase"] = "end_menu"
        return (
            "Thanks — I’ve logged a support request for the SETU team "
            f"(ref: SETU-{user_id[-4:]}).\n\n"
            "Would you like to go back to the *Main Menu* or *End Chat*?"
        )

    # ---- collect profile (conversational) ----
    if phase == "collect_profile":
        convo = _conversational_collect(session, journey, text)
        if convo:
            return convo

        missing_before = _missing_slots(journey, session["slots"])
        prefer = missing_before[0]["id"] if missing_before else None
        extracted = nlu.extract_slots(text, journey["slots"], prefer_slot=prefer)
        session["slots"].update(extracted)

        missing = _missing_slots(journey, session["slots"])
        if not extracted and missing:
            return "I didn’t catch that clearly. " + _ask_slot(missing[0])

        missing = _missing_slots(journey, session["slots"])
        if missing:
            nxt = missing[0]
            ack = ""
            if extracted:
                bits = [f"{k.replace('_', ' ')}: {v}" for k, v in extracted.items()]
                ack = "Got it — " + "; ".join(bits) + ".\n\n"
            return ack + _ask_slot(nxt)

        session["phase"] = "confirm_profile"
        return _profile_summary(session["slots"])

    # ---- confirm profile (deterministic branch) ----
    if phase == "confirm_profile":
        decision = nlu.detect_confirm(text)
        if decision is None and llm.llm_configured():
            data = llm.chat_json(
                SYSTEM_PERSONA
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
                "No problem — let’s update your details.\n\n"
                + _ask_slot(journey["slots"][0] if not keep_state else journey["slots"][1])
            )
        if decision != "Proceed":
            return "Please reply *Proceed* to match schemes, or *Edit details* to change something."

        matched, scope_note = eligibility.match_schemes(session["slots"])
        session["matched_schemes"] = matched
        session["phase"] = "scheme_list"

        listing = eligibility.format_scheme_list(matched, scope_note=scope_note)
        if llm.llm_configured():
            intro = llm.chat_text(
                SYSTEM_PERSONA
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
                return _profile_summary(session["slots"])
            return (
                "Please reply with the scheme number or name from the list.\n\n"
                + eligibility.format_scheme_list(schemes)
            )
        session["selected_scheme_sn"] = chosen.get("SN")
        session["phase"] = "scheme_detail"
        convo = _conversational_openers("scheme_detail", session, text)
        if convo:
            return convo
        return eligibility.format_scheme_detail(chosen)

    # ---- scheme detail ----
    if phase == "scheme_detail":
        action = nlu.detect_after_scheme(text)
        if action == "I need help":
            session["phase"] = "help_crm"
            return (
                "I can help with that. Please tell me briefly what you need "
                "support with, and I’ll create a support request for the SETU team."
            )
        if action == "View other schemes" or "other" in low or "list" in low or "back" in low:
            session["phase"] = "scheme_list"
            return eligibility.format_scheme_list(session.get("matched_schemes") or [])
        schemes = session.get("matched_schemes") or []
        chosen = nlu.match_scheme_choice(text, schemes)
        if chosen:
            session["selected_scheme_sn"] = chosen.get("SN")
            convo = _conversational_openers("scheme_detail", session, text)
            if convo:
                return convo
            return eligibility.format_scheme_detail(chosen)
        # free-text question about scheme
        if llm.llm_configured():
            scheme = next(
                (s for s in schemes if str(s.get("SN")) == str(session.get("selected_scheme_sn"))),
                None,
            )
            if scheme:
                ans = llm.chat_text(
                    SYSTEM_PERSONA
                    + "\nAnswer the user's question using only the scheme JSON. If unknown, say to check the official link. Plain text. Offer help or other schemes.",
                    json.dumps({"scheme": scheme, "question": text}, ensure_ascii=False)[:5000],
                    temperature=0.4,
                )
                if ans:
                    return ans
        session["phase"] = "end_menu"
        return "Would you like to go back to the *Main Menu* or *End Chat*?"

    # ---- end menu ----
    if phase == "end_menu":
        choice = nlu.detect_end_choice(text)
        if choice == "Main Menu":
            session["phase"] = "main_menu"
            session["slots"] = {}
            session["matched_schemes"] = []
            return _main_menu()
        if choice == "End Chat":
            session["phase"] = "feedback"
            return "Before you go, how would you rate your experience with SETU today? (1–5)"
        return "Please choose *Main Menu* or *End Chat*."

    # ---- feedback (deterministic rating gate) ----
    if phase == "feedback":
        rating = nlu.detect_rating(text)
        if rating is None:
            return "Please rate from 1 to 5."
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
    return "Let’s restart from the menu.\n\n" + _main_menu()
