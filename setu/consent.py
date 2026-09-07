"""Consent gate after language + state/scope, before further PII or matching."""

from __future__ import annotations

from typing import Any

from . import i18n, nlu
from .interactive import consent_options, with_numbered_options


def language_and_state_ready(session: dict[str, Any]) -> bool:
    if not session.get("language"):
        return False
    if session.get("path") == "category" or session.get("journey_id") == "schemes_by_category_v1":
        return bool(session.get("state_scope"))
    return bool((session.get("slots") or {}).get("state"))


def should_gate(session: dict[str, Any]) -> bool:
    return session.get("consent") != "accepted" and language_and_state_ready(session)


def prompt(session: dict[str, Any]) -> str:
    lang = session.get("language")
    body = i18n.t("consent_body", lang)
    return with_numbered_options(body, consent_options(lang))


def declined_message(session: dict[str, Any]) -> str:
    lang = session.get("language")
    body = i18n.t("consent_declined", lang)
    return with_numbered_options(body, [("Main Menu", i18n.t("named_next_menu", lang))])


def detect(text: str) -> str | None:
    n = nlu._norm(text)
    if not n:
        return None
    if n in ("1", "1)", "accept", "agree", "yes", "ok", "okay", "y", "सहमत", "स्वीकार", "होय", "ಸಮ್ಮತ"):
        return "Accept"
    if n in ("2", "2)", "decline", "no", "n", "reject", "disagree", "नहीं", "नाही", "ಇಲ್ಲ"):
        return "Decline"
    if n == "accept" or n.startswith("accept"):
        return "Accept"
    if n == "decline" or n.startswith("decline"):
        return "Decline"
    return None
