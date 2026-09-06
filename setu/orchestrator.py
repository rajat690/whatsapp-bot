"""Conversation-first Journey 1 orchestrator with deterministic checkpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import eligibility, nlu
from .session import get_session, reset_session

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


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
        return _welcome()

    # ---- welcome / language ----
    if phase == "welcome_language":
        lang = nlu.detect_language(text)
        if not lang:
            return (
                "I support English, Hindi, Marathi, and Kannada for now. "
                "Which one should we use?"
            )
        session["language"] = lang
        session["phase"] = "main_menu"
        # Prototype replies stay in English
        return (
            f"Great — continuing in {lang}.\n\n" + _main_menu()
        )

    # ---- main menu ----
    if phase == "main_menu":
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
        # Individual
        session["phase"] = "collect_profile"
        session["slots"] = {}
        return (
            "You’ve chosen Individual Schemes. I’ll ask a few short questions "
            "so I can show schemes that may be relevant to you.\n\n"
            + _ask_slot(journey["slots"][0])
        )

    # ---- help / CRM ----
    if phase == "help_crm":
        print(f"CRM_TICKET user={user_id} issue={text}", flush=True)
        session["phase"] = "end_menu"
        return (
            "Thanks — I’ve logged a support request for the SETU team "
            f"(ref: SETU-{user_id[-4:]}).\n\n"
            "Would you like to go back to the *Main Menu* or *End Chat*?"
        )

    # ---- collect profile (conversational) ----
    if phase == "collect_profile":
        missing_before = _missing_slots(journey, session["slots"])
        prefer = missing_before[0]["id"] if missing_before else None
        extracted = nlu.extract_slots(text, journey["slots"], prefer_slot=prefer)
        session["slots"].update(extracted)

        # If user answered but nothing extracted, nudge using current missing slot
        missing = _missing_slots(journey, session["slots"])
        if not extracted and missing:
            slot = missing[0]
            return (
                "I didn’t catch that clearly. "
                + _ask_slot(slot)
            )

        missing = _missing_slots(journey, session["slots"])
        if missing:
            # Ask next missing slot conversationally
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
        if decision == "Edit details":
            session["phase"] = "collect_profile"
            # clear to re-collect, keep state if present
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
        return eligibility.format_scheme_list(matched, scope_note=scope_note)

    # ---- scheme list ----
    if phase == "scheme_list":
        schemes = session.get("matched_schemes") or []
        chosen = nlu.match_scheme_choice(text, schemes)
        if not chosen:
            # allow rematch intent
            if "edit" in low:
                session["phase"] = "confirm_profile"
                return _profile_summary(session["slots"])
            return (
                "Please reply with the scheme number or name from the list.\n\n"
                + eligibility.format_scheme_list(schemes)
            )
        session["selected_scheme_sn"] = chosen.get("SN")
        session["phase"] = "scheme_detail"
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
        # maybe another scheme choice
        schemes = session.get("matched_schemes") or []
        chosen = nlu.match_scheme_choice(text, schemes)
        if chosen:
            session["selected_scheme_sn"] = chosen.get("SN")
            return eligibility.format_scheme_detail(chosen)
        session["phase"] = "end_menu"
        return (
            "Would you like to go back to the *Main Menu* or *End Chat*?"
        )

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

    # Fallback
    session["phase"] = "main_menu"
    return "Let’s restart from the menu.\n\n" + _main_menu()
