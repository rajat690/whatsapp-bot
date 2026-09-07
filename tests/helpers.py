"""Shared test helpers."""

from __future__ import annotations

from setu.orchestrator import handle_message
from setu.session import get_session


def accept_consent(uid: str) -> str | None:
    """Accept the consent gate when the session is waiting on it."""
    if get_session(uid).get("phase") == "consent":
        return handle_message(uid, "Accept")
    return None
