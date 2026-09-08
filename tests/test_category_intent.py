"""Free-text category keywords enter the existing category pack (skip hub)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from setu import category_catalog as cat
from setu import category_intent, nlu
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent


def _walk_to_menu(uid: str, language: str = "English") -> None:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, language)


class DetectCategoryKeywordTests(unittest.TestCase):
    def test_english_and_hindi_keywords(self):
        cases = {
            "scholarship": "scholarship",
            "scholarships": "scholarship",
            "छात्रवृत्ति": "scholarship",
            "pension": "pension",
            "पेंशन": "pension",
            "education": "education",
            "शिक्षा": "education",
            "housing": "housing",
            "आवास": "housing",
            "health": "health",
            "स्वास्थ्य": "health",
            "agriculture": "agriculture",
            "farmer": "agriculture",
            "disability": "disability",
            "divyang": "disability",
            "livelihood": "livelihood",
            "msme": "livelihood",
            "women": "women_child",
            "महिला": "women_child",
            "food": "food_ration",
            "ration": "food_ration",
            "राशन": "food_ration",
            "bocw": "labour_bocw",
            "labour": "labour_bocw",
        }
        for text, pack in cases.items():
            self.assertEqual(category_intent.detect_category_intent(text), pack, text)
            self.assertIn(pack, cat.PACKS)

    def test_scholarship_beats_education(self):
        self.assertEqual(
            category_intent.detect_category_intent("education scholarship"),
            "scholarship",
        )

    def test_menu_numbers_are_not_categories(self):
        self.assertIsNone(category_intent.detect_category_intent("1"))
        self.assertIsNone(category_intent.detect_category_intent("2"))
        self.assertIsNone(category_intent.detect_category_intent("3"))
        self.assertIsNone(category_intent.detect_category_intent("individual"))
        self.assertIsNone(category_intent.detect_category_intent("family"))

    def test_named_scheme_words_are_not_category_keywords(self):
        self.assertIsNone(category_intent.detect_category_intent("ujjwala"))
        self.assertIsNone(category_intent.detect_category_intent("stree shakti"))
        self.assertIsNone(category_intent.detect_category_intent("ayushman"))


class NamedSchemePreferenceTests(unittest.TestCase):
    def test_bare_category_is_not_named_preference(self):
        fake = [{"Scheme Name": "Some Scholarship", "_lookup_score": 88}]
        with patch.object(category_intent, "named_scheme_hits", return_value=fake):
            self.assertFalse(category_intent.prefer_named_scheme("scholarship"))
            self.assertFalse(category_intent.prefer_named_scheme("I want scholarship schemes"))

    def test_scheme_name_plus_category_prefers_named(self):
        fake = [{"Scheme Name": "Pradhan Mantri Ujjwala Yojana", "_lookup_score": 94}]
        with patch.object(category_intent, "named_scheme_hits", return_value=fake):
            self.assertTrue(category_intent.prefer_named_scheme("ujjwala housing"))
            self.assertTrue(category_intent.prefer_named_scheme("tell me about stree shakti"))

    def test_no_lookup_module_does_not_block_category(self):
        with patch.object(category_intent, "named_scheme_hits", return_value=[]):
            self.assertFalse(category_intent.prefer_named_scheme("scholarship"))


class CategoryIntentWalkTests(unittest.TestCase):
    def test_scholarship_from_main_menu_skips_hub(self):
        uid = "intent-schol"
        _walk_to_menu(uid)
        reply = handle_message(uid, "scholarship")
        session = get_session(uid)
        self.assertEqual(session.get("path"), "category")
        self.assertEqual(session.get("journey_id"), "schemes_by_category_v1")
        self.assertEqual(session.get("category_id"), "scholarship")
        self.assertEqual(session.get("phase"), "cat_state_scope")
        self.assertNotEqual(session.get("phase"), "cat_hub")
        self.assertIn("Scholarship", reply)
        self.assertIn("Central", reply)
        self.assertNotIn("Pick a topic", reply)

        reply = handle_message(uid, "2")  # Karnataka
        reply = accept_consent(uid) or reply
        session = get_session(uid)
        self.assertEqual(session["phase"], "cat_collect")
        self.assertEqual(session["category_id"], "scholarship")
        self.assertLessEqual(len(cat.questions_for("scholarship", session["slots"])), 4)
        self.assertIn("1 of 4", reply)
        self.assertIn("scholarship", reply.lower())
        self.assertNotIn("Pick a topic", reply)

        handle_message(uid, "1")
        handle_message(uid, "1")
        handle_message(uid, "1")
        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["phase"], "cat_results")
        self.assertRegex(reply, r"(?m)^1\. ")

    def test_pension_from_welcome_sets_language(self):
        uid = "intent-welcome"
        reset_session(uid)
        handle_message(uid, "hi")
        reply = handle_message(uid, "pension")
        session = get_session(uid)
        self.assertEqual(session.get("language"), "English")
        self.assertEqual(session.get("category_id"), "pension")
        self.assertEqual(session.get("phase"), "cat_state_scope")
        self.assertIn("Pension", reply)

        reply = handle_message(uid, "Karnataka")
        reply = accept_consent(uid) or reply
        self.assertEqual(get_session(uid)["phase"], "cat_collect")
        self.assertIn("1 of 4", reply)
        self.assertIn("pension", reply.lower())

    def test_hindi_keyword_from_menu(self):
        uid = "intent-hi"
        _walk_to_menu(uid, "Hindi")
        reply = handle_message(uid, "छात्रवृत्ति")
        session = get_session(uid)
        self.assertEqual(session.get("language"), "Hindi")
        self.assertEqual(session.get("category_id"), "scholarship")
        self.assertEqual(session.get("phase"), "cat_state_scope")
        self.assertIn("छात्रवृत्ति", reply)

    def test_bocw_and_ration_keywords(self):
        uid = "intent-bocw"
        _walk_to_menu(uid)
        handle_message(uid, "bocw")
        self.assertEqual(get_session(uid)["category_id"], "labour_bocw")
        reply = handle_message(uid, "2")
        reply = accept_consent(uid) or reply
        self.assertEqual(get_session(uid)["phase"], "cat_collect")
        self.assertIn("1 of 4", reply)

        uid = "intent-ration"
        _walk_to_menu(uid)
        handle_message(uid, "ration")
        self.assertEqual(get_session(uid)["category_id"], "food_ration")

    def test_individual_and_family_without_category_unchanged(self):
        uid = "intent-j1"
        _walk_to_menu(uid)
        reply = handle_message(uid, "individual")
        session = get_session(uid)
        self.assertIsNone(session.get("path"))
        self.assertEqual(session.get("journey_id"), "journey_1")
        self.assertEqual(session.get("phase"), "collect_profile")
        self.assertIn("state", reply.lower())

        uid = "intent-j2"
        _walk_to_menu(uid)
        reply = handle_message(uid, "family")
        session = get_session(uid)
        self.assertIsNone(session.get("path"))
        self.assertEqual(session.get("journey_id"), "journey_2")
        self.assertIn("household", reply.lower())

    def test_menu_3_still_shows_hub(self):
        uid = "intent-hub"
        _walk_to_menu(uid)
        reply = handle_message(uid, "3")
        session = get_session(uid)
        self.assertEqual(session.get("phase"), "cat_language")
        self.assertIsNone(session.get("category_id"))
        handle_message(uid, "1")
        reply = handle_message(uid, "2")
        reply = accept_consent(uid) or reply
        self.assertEqual(get_session(uid)["phase"], "cat_hub")
        self.assertIn("Education", reply)

    def test_unknown_category_is_honest_miss(self):
        uid = "intent-miss"
        _walk_to_menu(uid)
        reply = handle_message(uid, "transport schemes")
        session = get_session(uid)
        self.assertNotEqual(session.get("path"), "category")
        self.assertNotEqual(session.get("journey_id"), "journey_1")
        self.assertIn("don't have a topic pack", reply.lower())
        self.assertIn("Browse category", reply)
        self.assertIn("3", reply)

    def test_llm_cannot_force_individual_on_scholarship(self):
        uid = "intent-llm"
        reset_session(uid)

        def fake_json(_system, _user, temperature=0.3):
            return {"choice": "Individual Schemes", "reply": "Which state do you live in?"}

        with (
            patch("setu.llm.llm_configured", return_value=True),
            patch("setu.orchestrator.llm.llm_configured", return_value=True),
            patch("setu.llm.chat_json", side_effect=fake_json),
            patch("setu.orchestrator.llm.chat_json", side_effect=fake_json),
        ):
            handle_message(uid, "English")
            reply = handle_message(uid, "scholarship")
        session = get_session(uid)
        self.assertEqual(session.get("path"), "category")
        self.assertEqual(session.get("category_id"), "scholarship")
        self.assertNotEqual(session.get("phase"), "collect_profile")
        self.assertIn("Scholarship", reply)

    def test_named_scheme_plus_category_does_not_start_pack(self):
        uid = "intent-named"
        _walk_to_menu(uid)
        fake = [{"Scheme Name": "Pradhan Mantri Ujjwala Yojana", "_lookup_score": 94}]
        with patch.object(category_intent, "named_scheme_hits", return_value=fake):
            reply = handle_message(uid, "tell me about ujjwala housing")
        session = get_session(uid)
        self.assertNotEqual(session.get("path"), "category")
        self.assertNotEqual(session.get("category_id"), "housing")
        # Without PR #6 on this branch the named path is not implemented;
        # we only promise not to steal it into a category pack.
        self.assertTrue(
            session.get("phase") in ("main_menu", "collect_profile", "help_crm")
            or "Ujjwala" in reply
            or "menu" in reply.lower()
        )


class DetectMenuStillWorks(unittest.TestCase):
    def test_help_and_numbers(self):
        self.assertEqual(nlu.detect_menu("1"), "Individual Schemes")
        self.assertEqual(nlu.detect_menu("2"), "Family Schemes")
        self.assertEqual(nlu.detect_menu("3"), "Browse by category")
        self.assertEqual(nlu.detect_menu("I need help"), "I need help")


if __name__ == "__main__":
    unittest.main()
