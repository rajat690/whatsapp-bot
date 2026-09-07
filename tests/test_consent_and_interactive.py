"""Consent gate after language + state, before more PII or matching."""

from __future__ import annotations

import unittest

from setu.interactive import (
    build_interactive_payload,
    parse_inbound_message,
    spec_mode,
)
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent


class ConsentGateTests(unittest.TestCase):
    def test_individual_consent_after_state_before_age(self):
        uid = "consent-j1"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "individual schemes")
        reply = handle_message(uid, "Karnataka")
        session = get_session(uid)
        self.assertEqual(session["phase"], "consent")
        self.assertEqual(session["slots"].get("state"), "Karnataka")
        self.assertIsNone(session["slots"].get("age_group"))
        self.assertIn("only", reply.lower())
        self.assertIn("accept", reply.lower())
        self.assertIn("1.", reply)
        self.assertIn("2.", reply)

        reply = handle_message(uid, "Accept")
        session = get_session(uid)
        self.assertEqual(session["consent"], "accepted")
        self.assertEqual(session["phase"], "collect_profile")
        self.assertIn("age", reply.lower())
        self.assertIsNone(session["slots"].get("age_group"))

    def test_consent_decline_does_not_collect_more_pii(self):
        uid = "consent-no"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "individual schemes")
        handle_message(uid, "Karnataka")
        reply = handle_message(uid, "Decline")
        session = get_session(uid)
        self.assertEqual(session["consent"], "declined")
        self.assertEqual(session["phase"], "consent_declined")
        self.assertIn("will not collect", reply.lower())
        self.assertIn("main menu", reply.lower())
        handle_message(uid, "28")
        self.assertIsNone(get_session(uid)["slots"].get("age_group"))
        reply = handle_message(uid, "Main Menu")
        self.assertEqual(get_session(uid)["phase"], "main_menu")
        self.assertIn("1.", reply)

    def test_category_consent_after_state_scope(self):
        uid = "consent-cat"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "3")
        handle_message(uid, "1")
        reply = handle_message(uid, "2")  # Karnataka
        session = get_session(uid)
        self.assertEqual(session["phase"], "consent")
        self.assertEqual(session["state_scope"], "karnataka")
        self.assertNotEqual(session["phase"], "cat_hub")
        reply = accept_consent(uid)
        session = get_session(uid)
        self.assertEqual(session["consent"], "accepted")
        self.assertEqual(session["phase"], "cat_hub")
        self.assertIn("Education", reply)

    def test_button_accept_id_is_understood(self):
        uid = "consent-id"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "individual")
        handle_message(uid, "Maharashtra")
        self.assertEqual(get_session(uid)["phase"], "consent")
        handle_message(uid, "Accept")
        self.assertEqual(get_session(uid)["consent"], "accepted")


class InteractiveInboundTests(unittest.TestCase):
    def test_button_reply_prefers_id(self):
        parsed = parse_inbound_message(
            {
                "type": "interactive",
                "interactive": {
                    "type": "button_reply",
                    "button_reply": {"id": "Accept", "title": "Acce…"},
                },
            }
        )
        self.assertEqual(parsed, "Accept")

    def test_list_reply_prefers_id(self):
        parsed = parse_inbound_message(
            {
                "type": "interactive",
                "interactive": {
                    "type": "list_reply",
                    "list_reply": {
                        "id": "Individual Schemes",
                        "title": "Individual",
                    },
                },
            }
        )
        self.assertEqual(parsed, "Individual Schemes")

    def test_text_body_still_works(self):
        parsed = parse_inbound_message(
            {"type": "text", "text": {"body": "  English  "}}
        )
        self.assertEqual(parsed, "English")

    def test_payload_uses_buttons_for_two_options(self):
        payload = build_interactive_payload(
            "911",
            "Do you accept?",
            [{"id": "Accept", "title": "Accept"}, {"id": "Decline", "title": "Decline"}],
        )
        self.assertEqual(payload["type"], "interactive")
        self.assertEqual(payload["interactive"]["type"], "button")
        self.assertEqual(len(payload["interactive"]["action"]["buttons"]), 2)

    def test_payload_uses_list_for_four_options(self):
        opts = [{"id": str(i), "title": f"Opt {i}"} for i in range(1, 5)]
        self.assertEqual(spec_mode(opts), "list")
        payload = build_interactive_payload("911", "Pick", opts)
        self.assertEqual(payload["interactive"]["type"], "list")
        self.assertEqual(len(payload["interactive"]["action"]["sections"][0]["rows"]), 4)

    def test_payload_none_when_over_ten(self):
        opts = [{"id": str(i), "title": str(i)} for i in range(11)]
        self.assertEqual(spec_mode(opts), "text")
        self.assertIsNone(build_interactive_payload("911", "Pick", opts))

    def test_list_reply_falls_back_to_title(self):
        parsed = parse_inbound_message(
            {
                "type": "interactive",
                "interactive": {
                    "type": "list_reply",
                    "list_reply": {"title": "Karnataka"},
                },
            }
        )
        self.assertEqual(parsed, "Karnataka")

    def test_main_menu_stashes_list_options(self):
        uid = "int-menu"
        reset_session(uid)
        handle_message(uid, "English")
        outbound = get_session(uid).get("outbound") or {}
        ids = [row["id"] for row in outbound.get("options") or []]
        self.assertEqual(len(ids), 4)
        self.assertIn("Individual Schemes", ids)
        self.assertIn("Browse by category", ids)

    def test_consent_stashes_two_buttons(self):
        uid = "int-consent"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "1")
        handle_message(uid, "Karnataka")
        outbound = get_session(uid).get("outbound") or {}
        ids = [row["id"] for row in outbound.get("options") or []]
        self.assertEqual(ids, ["Accept", "Decline"])


if __name__ == "__main__":
    unittest.main()
