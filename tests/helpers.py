"""Shared test helpers."""

from __future__ import annotations

from setu import i18n
from setu.interactive import (
    build_interactive_payload,
    outbound_sends,
    spec_mode,
)
from setu.orchestrator import handle_message
from setu.session import get_session


def accept_consent(uid: str) -> str | None:
    """Accept the consent gate when the session is waiting on it."""
    if get_session(uid).get("phase") == "consent":
        return handle_message(uid, "Accept")
    return None


def whatsapp_interactive_views(session: dict, reply: str | None = None) -> list[dict]:
    """What WhatsApp would show: short_body (else body) + list/button titles."""
    outbound = session.get("outbound") or {}
    views = []
    for spec in outbound_sends(outbound.get("body") or reply or "", outbound):
        options = spec.get("options") or []
        if not options:
            continue
        body = spec.get("short_body") or spec.get("body") or ""
        button = spec.get("list_button") or ""
        views.append(
            {
                "body": body,
                "button": button,
                "options": options,
                "section_title": spec.get("section_title") or "",
                "mode": spec_mode(options),
            }
        )
    return views


def assert_no_bare_choose(test, session: dict, reply: str | None = None) -> None:
    """Fail if any interactive send uses 'Choose' as the only body or button."""
    views = whatsapp_interactive_views(session, reply)
    test.assertTrue(views, msg="expected at least one interactive send")
    for view in views:
        test.assertFalse(
            i18n.is_bare_choose(view["body"]),
            msg=f"interactive body is bare Choose: {view['body']!r}",
        )
        if view["mode"] == "list":
            test.assertFalse(
                i18n.is_bare_choose(view["button"]),
                msg=f"list button is bare Choose: {view['button']!r}",
            )
            payload = build_interactive_payload(
                "test",
                view["body"],
                view["options"],
                list_button=view["button"],
                section_title=view["section_title"],
            )
            test.assertIsNotNone(payload)
            shown = payload["interactive"]["body"]["text"]
            action_btn = payload["interactive"]["action"]["button"]
            test.assertFalse(i18n.is_bare_choose(shown), msg=shown)
            test.assertFalse(i18n.is_bare_choose(action_btn), msg=action_btn)
            rows = payload["interactive"]["action"]["sections"][0]["rows"]
            test.assertGreaterEqual(len(rows), 1)
