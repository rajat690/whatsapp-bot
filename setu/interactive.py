"""WhatsApp Cloud API interactive messages (reply buttons + lists) with text fallback.

Meta limits (Cloud API):
- Reply buttons: at most 3; button title ≤20 chars; button id ≤256 chars.
- List messages: 2–10 rows (we also allow 4–10 as the product preference);
  row title ≤24 chars; row description ≤72 chars; list button ≤20 chars.
- Interactive body ≤1024 chars (plain text allows ~4096).
- More than 10 options → plain-text numbered list only.
If an interactive send fails, the same numbered body is resent as text.
"""

from __future__ import annotations

import re
from typing import Any

from . import category_catalog as cat
from . import i18n

BUTTON_TITLE_MAX = 20
LIST_ROW_TITLE_MAX = 24
LIST_ROW_DESC_MAX = 72
LIST_BUTTON_MAX = 20
INTERACTIVE_BODY_MAX = 1024
TEXT_BODY_MAX = 4000
MAX_REPLY_BUTTONS = 3
MAX_LIST_ROWS = 10


def clip(text: str, limit: int) -> str:
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw
    if limit <= 1:
        return raw[:limit]
    return raw[: limit - 1] + "…"


def numbered_block(options: list[tuple[str, str]]) -> str:
    lines = [f"{i}. {title}" for i, (_oid, title) in enumerate(options, 1)]
    return "\n".join(lines)


def with_numbered_options(body: str, options: list[tuple[str, str]]) -> str:
    block = numbered_block(options)
    text = (body or "").rstrip()
    if not block:
        return text
    if block in text:
        return text
    return text + "\n\n" + block


def parse_inbound_message(message: dict[str, Any] | None) -> str:
    """Turn a Meta webhook message into the text/id the orchestrator already understands.

    Prefer interactive id (button_reply / list_reply) so truncated titles still route.
    Fall back to the visible title, then to a regular text body.
    """
    if not message:
        return ""
    mtype = message.get("type")
    if mtype == "text":
        return (message.get("text") or {}).get("body", "").strip()
    if mtype != "interactive":
        return ""
    interactive = message.get("interactive") or {}
    itype = interactive.get("type")
    if itype == "button_reply":
        payload = interactive.get("button_reply") or {}
        return (payload.get("id") or payload.get("title") or "").strip()
    if itype == "list_reply":
        payload = interactive.get("list_reply") or {}
        return (payload.get("id") or payload.get("title") or "").strip()
    return ""


def options_for_session(session: dict[str, Any]) -> list[tuple[str, str]]:
    """Structured options for the current phase (empty → text-only send)."""
    phase = session.get("phase") or ""
    lang = session.get("language")
    if phase in ("welcome_language", "cat_language"):
        return language_options(lang)
    if phase == "main_menu":
        return main_menu_options(lang)
    if phase == "consent":
        return consent_options(lang)
    if phase == "consent_declined":
        return [( "Main Menu", i18n.t("named_next_menu", lang))]
    if phase in ("who_first", "who_clarify"):
        return who_options(lang, clarify=phase == "who_clarify")
    if phase == "confirm_profile":
        return [
            ("Proceed", i18n.t("confirm_proceed", lang)),
            ("Edit details", i18n.t("confirm_edit", lang)),
        ]
    if phase == "end_menu":
        return [
            ("Main Menu", i18n.t("end_opt_menu", lang)),
            ("End Chat", i18n.t("end_opt_end", lang)),
        ]
    if phase in ("named_scheme", "named_scheme_ask"):
        return named_next_options(session, lang)
    if phase == "cat_state_scope":
        return catalog_options(cat.STATE_SCOPES, lang)
    if phase == "cat_state_plus":
        return catalog_options(cat.STATE_PLUS_CENTRAL, lang)
    if phase == "cat_hub":
        ids = list(cat.HUB_2 if session.get("hub_screen") == 2 else cat.HUB_1)
        return [(cid, cat.label_of(cid, lang)) for cid in ids]
    if phase == "cat_who":
        return catalog_options(cat.WHO_FIRST, lang)
    if phase == "cat_collect":
        return _category_question_options(session, lang)
    if phase == "collect_profile":
        from . import conversation_engine as engine

        return engine.current_slot_options(session)
    if phase == "scheme_detail":
        return after_detail_options(session.get("journey_id"), lang)
    if phase == "cat_detail":
        return [
            ("Go Back", i18n.t("after_back", lang)),
            ("Back to categories", i18n.t("after_categories", lang)),
            ("Main Menu", i18n.t("named_next_menu", lang)),
        ]
    return []


def language_options(language: str | None = None) -> list[tuple[str, str]]:
    lang = language or "English"
    return [(item["id"], cat.label_of(item, lang)) for item in cat.LANGUAGES]


def main_menu_options(language: str | None) -> list[tuple[str, str]]:
    return [
        ("Individual Schemes", i18n.t("menu_opt_individual", language)),
        ("Family Schemes", i18n.t("menu_opt_family", language)),
        ("Browse by category", i18n.t("menu_opt_category", language)),
        ("I need help", i18n.t("menu_opt_help", language)),
    ]


def consent_options(language: str | None) -> list[tuple[str, str]]:
    return [
        ("Accept", i18n.t("consent_accept", language)),
        ("Decline", i18n.t("consent_decline", language)),
    ]


def who_options(language: str | None, *, clarify: bool = False) -> list[tuple[str, str]]:
    opts = [
        ("who_me", i18n.t("who_me", language)),
        ("who_wife", i18n.t("who_wife", language)),
        ("who_children", i18n.t("who_children", language)),
        ("who_family", i18n.t("who_family", language)),
    ]
    if not clarify:
        opts.append(("who_category", i18n.t("who_category", language)))
        opts.append(("who_menu", i18n.t("who_menu", language)))
    else:
        opts.append(("who_menu", i18n.t("who_menu", language)))
    return opts


def named_next_options(session: dict[str, Any], language: str | None) -> list[tuple[str, str]]:
    keys = session.get("named_next_options") or []
    labels = {
        "another": i18n.t("named_next_another", language),
        "resume": i18n.t("resume_opt", language),
        "Individual Schemes": i18n.t("named_next_individual", language),
        "Family Schemes": i18n.t("named_next_family", language),
        "Browse by category": i18n.t("named_next_category", language),
        "Main Menu": i18n.t("named_next_menu", language),
        "End Chat": i18n.t("end_opt_end", language),
    }
    if keys:
        return [(k, labels.get(k, k)) for k in keys]
    return [(k, v) for k, v in labels.items()]


def catalog_options(items: list[dict[str, Any] | str], language: str | None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, str):
            out.append((item, cat.label_of(item, language)))
        else:
            oid = str(item.get("id") or "")
            out.append((oid, cat.label_of(item, language)))
    return out


def after_detail_options(journey_id: str | None, language: str | None) -> list[tuple[str, str]]:
    if journey_id == "journey_2":
        return [
            ("I need help", i18n.t("menu_opt_help", language)),
            ("Go Back", i18n.t("after_back", language)),
            ("End Chat", i18n.t("end_opt_end", language)),
        ]
    return [
        ("I need help", i18n.t("menu_opt_help", language)),
        ("View other schemes", i18n.t("after_other", language)),
        ("End Chat", i18n.t("end_opt_end", language)),
    ]


def _category_question_options(session: dict[str, Any], language: str | None) -> list[tuple[str, str]]:
    category_id = session.get("category_id") or ""
    questions = cat.questions_for(category_id, session.get("slots"))
    idx = session.get("cat_q_index") or 0
    if idx >= len(questions):
        return []
    q = questions[idx]
    opts = []
    for opt in q.get("options") or []:
        oid = str(opt.get("id") or "")
        opts.append((oid, cat.label_of(opt, language)))
    return opts


DETAIL_MENU_PHASES = frozenset({"named_scheme", "scheme_detail", "cat_detail"})
LANGUAGE_PHASES = frozenset({"welcome_language", "cat_language"})


def _collect_slot_id(session: dict[str, Any]) -> str | None:
    if (session.get("phase") or "") != "collect_profile":
        return None
    if not session.get("journey_id"):
        return session.get("collect_slot_id")
    from . import conversation_engine as engine

    slot = engine.current_collect_slot(session)
    return (slot or {}).get("id") or session.get("collect_slot_id")


def _list_button_label(session: dict[str, Any]) -> str:
    phase = session.get("phase") or ""
    lang = session.get("language")
    slot_id = _collect_slot_id(session) if phase == "collect_profile" else None
    return clip(i18n.interactive_list_button(lang, phase=phase, slot_id=slot_id), LIST_BUTTON_MAX)


def finalize(session: dict[str, Any], reply: str | None) -> str:
    """Keep numbered fallback in the body; stash interactive spec on the session."""
    text = reply or ""
    options = options_for_session(session)
    phase = session.get("phase") or ""
    list_button = _list_button_label(session)
    option_rows = [{"id": oid, "title": title} for oid, title in options]

    if phase in DETAIL_MENU_PHASES and options:
        menu_prompt = _short_body(session)
        session["outbound"] = {
            "body": text,
            "options": [],
            "separate_menu": True,
            "detail_text": text,
            "menu_options": option_rows,
            "list_button": list_button,
            "followup": {
                "body": with_numbered_options(menu_prompt, options),
                "options": option_rows,
                "list_button": list_button,
                "short_body": menu_prompt,
            },
        }
        return text

    if options:
        text = with_numbered_options(text, options)
    session["outbound"] = {
        "body": text,
        "options": option_rows,
        "list_button": list_button,
        "short_body": _short_body(session),
    }
    return text


def outbound_sends(message_text: str, outbound: dict | None) -> list[dict[str, Any]]:
    """Ordered WhatsApp send specs. Detail + What-next are always two sends."""
    outbound = outbound or {}
    follow = outbound.get("followup")
    if outbound.get("separate_menu") or follow:
        detail = outbound.get("detail_text") or outbound.get("body") or message_text
        follow = follow or {}
        menu_opts = follow.get("options") or outbound.get("menu_options") or []
        menu_prompt = follow.get("short_body") or _default_what_next()
        menu_body = follow.get("body") or with_numbered_options(
            menu_prompt,
            [(str(o.get("id") or ""), str(o.get("title") or "")) for o in menu_opts],
        )
        return [
            {
                "body": detail,
                "options": [],
                "list_button": "Choose",
                "short_body": "",
            },
            {
                "body": menu_body,
                "options": menu_opts,
                "list_button": follow.get("list_button") or outbound.get("list_button") or "Choose",
                "short_body": menu_prompt,
            },
        ]
    return [
        {
            "body": outbound.get("body") or message_text,
            "options": outbound.get("options") or [],
            "list_button": outbound.get("list_button") or "Choose",
            "short_body": outbound.get("short_body") or "",
        }
    ]


def _default_what_next() -> str:
    return i18n.t("named_next_intro", "English")


def _short_body(session: dict[str, Any]) -> str:
    phase = session.get("phase") or ""
    lang = session.get("language")
    if phase in ("named_scheme", "named_scheme_ask", "scheme_detail", "cat_detail"):
        return i18n.t("named_next_intro", lang)
    if phase == "consent":
        return i18n.t("consent_body", lang)
    if phase in ("who_first", "who_clarify"):
        return i18n.t("who_clarify" if phase == "who_clarify" else "who_intro", lang)
    if phase == "main_menu":
        return i18n.t("main_menu_header", lang)
    if phase in LANGUAGE_PHASES or phase == "collect_profile":
        slot_id = _collect_slot_id(session) if phase == "collect_profile" else None
        return i18n.interactive_list_button(lang, phase=phase, slot_id=slot_id)
    return i18n.t("interactive_choose", lang)


def spec_mode(options: list[dict[str, str]] | list[tuple[str, str]]) -> str:
    n = len(options)
    if 1 <= n <= MAX_REPLY_BUTTONS:
        return "buttons"
    if 4 <= n <= MAX_LIST_ROWS:
        return "list"
    return "text"


def build_text_payload(recipient: str, body: str) -> dict[str, Any]:
    text = body or ""
    if len(text) > TEXT_BODY_MAX:
        text = text[: TEXT_BODY_MAX - 10] + "…"
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }


def build_interactive_payload(
    recipient: str,
    body: str,
    options: list[dict[str, str]],
    *,
    list_button: str = "Choose",
) -> dict[str, Any] | None:
    mode = spec_mode(options)
    if mode == "text":
        return None
    body = clip(body, INTERACTIVE_BODY_MAX) or " "
    if mode == "buttons":
        buttons = []
        for opt in options[:MAX_REPLY_BUTTONS]:
            buttons.append(
                {
                    "type": "reply",
                    "reply": {
                        "id": str(opt.get("id") or "")[:256],
                        "title": clip(str(opt.get("title") or opt.get("id") or ""), BUTTON_TITLE_MAX),
                    },
                }
            )
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": buttons},
            },
        }
    rows = []
    for opt in options[:MAX_LIST_ROWS]:
        rows.append(
            {
                "id": str(opt.get("id") or "")[:200],
                "title": clip(str(opt.get("title") or opt.get("id") or ""), LIST_ROW_TITLE_MAX),
            }
        )
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": clip(list_button or "Choose", LIST_BUTTON_MAX),
                "sections": [{"title": "Options", "rows": rows}],
            },
        },
    }


def pick_by_number_or_id(
    text: str,
    options: list[tuple[str, str]],
) -> str | None:
    """Map a typed number, id, or title onto the option id."""
    n = (text or "").strip()
    if not n or not options:
        return None
    low = n.lower()
    if re.fullmatch(r"\d{1,2}", n):
        idx = int(n) - 1
        if 0 <= idx < len(options):
            return options[idx][0]
    for oid, title in options:
        if n == oid or low == oid.lower() or low == (title or "").lower():
            return oid
    return None
