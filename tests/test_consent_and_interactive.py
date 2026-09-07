"""Consent gate after language + state, before more PII or matching."""

from __future__ import annotations

import unittest

from setu.interactive import (
    build_interactive_payload,
    parse_inbound_message,
    spec_mode,
)
from setu import i18n
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

    def test_consent_body_and_buttons_follow_session_language(self):
        cases = (
            ("Hindi", "योजना", "स्वीकार", "Do you accept?"),
            ("Marathi", "योजना", "स्वीकारा", "Do you accept?"),
            ("Kannada", "ಯೋಜನೆ", "ಒಪ್ಪುತ್ತೇನೆ", "Do you accept?"),
        )
        for lang, needle, accept_title, english in cases:
            uid = f"consent-lang-{lang}"
            reset_session(uid)
            handle_message(uid, "hi")
            handle_message(uid, lang)
            handle_message(uid, "individual schemes")
            reply = handle_message(uid, "Karnataka")
            session = get_session(uid)
            self.assertEqual(session["language"], lang)
            self.assertEqual(session["phase"], "consent")
            self.assertIn(needle, reply)
            self.assertNotIn(english, reply)
            titles = [row["title"] for row in (session.get("outbound") or {}).get("options") or []]
            self.assertTrue(any(accept_title in t for t in titles), msg=titles)
            self.assertNotIn("Accept", titles)

    def test_karnataka_does_not_switch_language_to_kannada(self):
        uid = "consent-ka-state"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "individual schemes")
        reply = handle_message(uid, "Karnataka")
        session = get_session(uid)
        self.assertEqual(session["language"], "English")
        self.assertEqual(session["phase"], "consent")
        self.assertIn("Do you accept?", reply)

    def test_language_switch_on_consent_rerenders(self):
        uid = "consent-switch"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "individual schemes")
        handle_message(uid, "Karnataka")
        self.assertEqual(get_session(uid)["phase"], "consent")
        reply = handle_message(uid, "shift to hindi")
        self.assertEqual(get_session(uid)["language"], "Hindi")
        self.assertEqual(get_session(uid)["phase"], "consent")
        self.assertIn("योजना", reply)
        self.assertNotIn("Do you accept?", reply)
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


class LanguageAndIntroCopyTests(unittest.TestCase):
    def test_welcome_language_list_button_says_choose_language(self):
        uid = "copy-lang-btn"
        reset_session(uid)
        handle_message(uid, "hi")
        session = get_session(uid)
        self.assertEqual(session["phase"], "welcome_language")
        outbound = session.get("outbound") or {}
        self.assertEqual(outbound.get("list_button"), "choose language")
        self.assertEqual(outbound.get("short_body"), "choose language")
        self.assertLessEqual(len(outbound.get("list_button") or ""), 20)

    def test_main_menu_keeps_generic_choose(self):
        uid = "copy-menu-btn"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        session = get_session(uid)
        self.assertEqual(session["phase"], "main_menu")
        outbound = session.get("outbound") or {}
        self.assertEqual(outbound.get("list_button"), "Choose")
        handle_message(uid, "switch to hindi")
        session = get_session(uid)
        self.assertEqual(session["language"], "Hindi")
        self.assertEqual(session["phase"], "main_menu")
        self.assertEqual((session.get("outbound") or {}).get("list_button"), "चुनें")

    def test_hindi_individual_intro_uses_localized_menu_name(self):
        uid = "copy-hi-intro"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "Hindi")
        reply = handle_message(uid, "1")
        self.assertIn("व्यक्तिगत योजनाएँ", reply)
        self.assertNotIn("Individual Schemes", reply)
        self.assertIn(i18n.t("menu_opt_individual", "Hindi"), i18n.t("individual_intro", "Hindi"))

    def test_hindi_family_intro_uses_localized_menu_name(self):
        uid = "copy-hi-fam"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "Hindi")
        reply = handle_message(uid, "2")
        self.assertIn("परिवार योजनाएँ", reply)
        self.assertNotIn("Family Schemes", reply)
        self.assertIn(i18n.t("menu_opt_family", "Hindi"), i18n.t("family_intro", "Hindi"))

    def test_english_intros_keep_scheme_titles(self):
        self.assertIn("Individual Schemes", i18n.t("individual_intro", "English"))
        self.assertIn("Family Schemes", i18n.t("family_intro", "English"))
        self.assertNotIn("Individual Schemes", i18n.t("individual_intro", "Marathi"))
        self.assertNotIn("Family Schemes", i18n.t("family_intro", "Kannada"))
        self.assertIn(i18n.t("menu_opt_individual", "Marathi"), i18n.t("individual_intro", "Marathi"))
        self.assertIn(i18n.t("menu_opt_family", "Kannada"), i18n.t("family_intro", "Kannada"))

    def test_choose_language_labels_fit_whatsapp_limit(self):
        from setu.interactive import LIST_BUTTON_MAX

        for lang in ("English", "Hindi", "Marathi", "Kannada"):
            label = i18n.t("interactive_choose_language", lang)
            self.assertLessEqual(len(label), LIST_BUTTON_MAX, msg=f"{lang}: {label}")
            self.assertNotEqual(label.lower(), "choose")
        self.assertEqual(i18n.t("interactive_choose_language", "English"), "choose language")
        self.assertEqual(i18n.t("interactive_choose_language", "Hindi"), "भाषा चुनें")


class CollectListButtonCopyTests(unittest.TestCase):
    def test_individual_collect_list_buttons_name_the_slot(self):
        uid = "copy-j1-slots"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "1")
        handle_message(uid, "Karnataka")
        handle_message(uid, "Accept")
        expected = [
            ("age_group", "choose age", "28"),
            ("occupation", "choose profession", "salaried"),
            ("household_income", "choose income", "25000"),
            ("social_category", "choose category", "OBC"),
        ]
        for slot_id, label, answer in expected:
            session = get_session(uid)
            self.assertEqual(session["phase"], "collect_profile", msg=slot_id)
            self.assertEqual(session.get("collect_slot_id"), slot_id)
            outbound = session.get("outbound") or {}
            self.assertEqual(outbound.get("list_button"), label, msg=slot_id)
            self.assertNotEqual(outbound.get("list_button"), "Choose")
            self.assertLessEqual(len(label), 20)
            handle_message(uid, answer)
        self.assertEqual(get_session(uid)["phase"], "confirm_profile")
        confirm_btn = (get_session(uid).get("outbound") or {}).get("list_button")
        self.assertEqual(confirm_btn, "Choose")

    def test_hindi_collect_age_button_is_localized(self):
        uid = "copy-hi-age-btn"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "Hindi")
        handle_message(uid, "1")
        handle_message(uid, "Karnataka")
        handle_message(uid, "Accept")
        session = get_session(uid)
        self.assertEqual(session["phase"], "collect_profile")
        self.assertEqual(session.get("collect_slot_id"), "age_group")
        self.assertEqual((session.get("outbound") or {}).get("list_button"), "आयु चुनें")
        self.assertNotEqual((session.get("outbound") or {}).get("list_button"), "चुनें")

    def test_consent_buttons_are_not_generic_choose(self):
        uid = "copy-consent-btns"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "1")
        handle_message(uid, "Karnataka")
        outbound = get_session(uid).get("outbound") or {}
        titles = [row["title"] for row in outbound.get("options") or []]
        self.assertEqual(titles, ["Accept", "Decline"])

    def test_slot_choose_labels_fit_whatsapp_limit(self):
        from setu.interactive import LIST_BUTTON_MAX

        slots = (
            "age_group",
            "occupation",
            "household_income",
            "social_category",
            "state",
        )
        for slot_id in slots:
            for lang in ("English", "Hindi", "Marathi", "Kannada"):
                label = i18n.interactive_list_button(lang, phase="collect_profile", slot_id=slot_id)
                self.assertLessEqual(len(label), LIST_BUTTON_MAX, msg=f"{slot_id}/{lang}: {label}")
                self.assertNotEqual(label, i18n.t("interactive_choose", lang), msg=f"{slot_id}/{lang}")
        self.assertEqual(
            i18n.interactive_list_button("English", phase="collect_profile", slot_id="age_group"),
            "choose age",
        )
        self.assertEqual(
            i18n.interactive_list_button("Hindi", phase="collect_profile", slot_id="occupation"),
            "पेशा चुनें",
        )
        self.assertEqual(
            i18n.interactive_list_button("Hindi", phase="collect_profile", slot_id="household_income"),
            "आय चुनें",
        )
        self.assertEqual(
            i18n.interactive_list_button("Hindi", phase="collect_profile", slot_id="social_category"),
            "श्रेणी चुनें",
        )


if __name__ == "__main__":
    unittest.main()
