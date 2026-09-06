"""Regression tests for session language + one-slot-per-turn collection."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from setu import i18n, nlu
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session


J1_DUMP = (
    "कृपया अपनी आयु समूह (0-17, 18-59, 60+), पेशा (Farmer, Labourer, Salaried, "
    "Self-employed, Student, Unemployed, Homemaker, Retired, Other), परिवार की आय "
    "(Up to ₹10,000, ₹10,001-₹30,000), सामाजिक वर्ग (SC, ST, OBC, General, Minority), "
    "वैवाहिक स्थिति (Single, Married), और क्या आप विकलांग हैं (Yes, No) बताइए।"
)

J2_DUMP = (
    "कुटुंबात 60+ किती सदस्य आहेत? अपंगत्व आहे का? गर्भवती आहे का? "
    "व्यवसाय काय? उत्पन्न किती? घर कसे आहे? शिधापत्रिका? विमा? सामाजिक श्रेणी?"
)


class DetectLanguageSwitchTests(unittest.TestCase):
    def test_mixed_switch_and_state(self):
        self.assertEqual(
            nlu.detect_language_switch(
                "can you switch back to english. i stay in karnataka"
            ),
            "English",
        )
        self.assertEqual(nlu.detect_state("can you switch back to english. i stay in karnataka"), "Karnataka")

    def test_bare_language_name(self):
        self.assertEqual(nlu.detect_language_switch("marathi"), "Marathi")
        self.assertEqual(nlu.detect_language_switch("Hindi"), "Hindi")

    def test_ordinary_answer_is_not_a_switch(self):
        self.assertIsNone(nlu.detect_language_switch("I stay in Karnataka"))
        self.assertIsNone(nlu.detect_language_switch("20"))
        self.assertIsNone(nlu.detect_language_switch("farmer"))


class MultiSlotGuardTests(unittest.TestCase):
    def test_journey1_hindi_form_dump(self):
        missing = [
            {"id": sid}
            for sid in (
                "age_group",
                "occupation",
                "household_income",
                "social_category",
                "marital_status",
                "disability",
            )
        ]
        self.assertTrue(i18n.is_multi_slot_prompt(J1_DUMP, missing))
        self.assertFalse(i18n.is_multi_slot_prompt("आप किस आयु वर्ग में हैं?", missing))

    def test_journey2_marathi_form_dump(self):
        missing = [
            {"id": sid}
            for sid in (
                "members_60_plus",
                "family_disability",
                "pregnant_or_breastfeeding",
                "primary_occupation",
                "household_income",
                "housing",
                "ration_card",
                "has_insurance",
                "social_category",
            )
        ]
        self.assertTrue(i18n.is_multi_slot_prompt(J2_DUMP, missing))
        self.assertFalse(
            i18n.is_multi_slot_prompt(
                "घरात 60 वर्षे किंवा त्याहून अधिक वयाचे किती सदस्य आहेत? (0 चालेल)",
                missing,
            )
        )


class KeywordJourneyTests(unittest.TestCase):
    def test_one_slot_at_a_time_without_llm_both_journeys(self):
        uid = "kw-j1"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(uid, "individual schemes")
        self.assertIn("state", reply.lower())
        reply = handle_message(uid, "Karnataka")
        self.assertIn("age", reply.lower())
        self.assertNotIn("marital", reply.lower())
        self.assertNotIn("disability", reply.lower())

        uid = "kw-j2"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "family schemes")
        handle_message(uid, "Karnataka")
        reply = handle_message(uid, "5")
        self.assertIn("children", reply.lower())
        self.assertNotIn("ration", reply.lower())
        self.assertNotIn("insurance", reply.lower())

    def test_language_switch_persists_on_keyword_path(self):
        uid = "kw-switch"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "marathi")
        handle_message(uid, "2")
        reply = handle_message(uid, "can you switch back to english. i stay in karnataka")
        self.assertEqual(get_session(uid)["language"], "English")
        self.assertEqual(get_session(uid)["slots"].get("state"), "Karnataka")
        self.assertIn("household", reply.lower())
        self.assertNotRegex(reply, r"[\u0900-\u097F]")
        reply = handle_message(uid, "20")
        self.assertEqual(get_session(uid)["language"], "English")
        self.assertIn("children", reply.lower())
        self.assertNotRegex(reply, r"[\u0900-\u097F]")

    def test_hard_branches_still_work(self):
        uid = "kw-branch"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "individual schemes")
        for msg in ("Karnataka", "28", "salaried", "25000", "OBC", "married", "no"):
            handle_message(uid, msg)
        reply = handle_message(uid, "proceed")
        self.assertIn("scheme", reply.lower())
        session = get_session(uid)
        self.assertEqual(session["phase"], "scheme_list")
        self.assertTrue(session.get("matched_schemes"))


class LlmRegressionTests(unittest.TestCase):
    def test_journey2_language_stick_and_no_dump(self):
        uid = "llm-j2"
        reset_session(uid)
        replies = iter(
            [
                {"language": "Marathi", "reply": "नमस्कार! 1) वैयक्तिक 2) कुटुंब 3) मदत"},
                {"choice": "Family Schemes", "reply": "कृपया तुमच्या राज्याचे नाव सांगा."},
                {
                    "slots": {"state": "Karnataka"},
                    "reply": "Sure, let's continue in English. How many people are in your household?",
                    "ready_for_confirm": False,
                },
                {
                    "slots": {"household_size": "20"},
                    "reply": "कुटुंबात 18 वर्षांखालील किती मुले आहेत?",
                    "ready_for_confirm": False,
                },
                {
                    "slots": {"children_under_18": "0"},
                    "reply": J2_DUMP,
                    "ready_for_confirm": False,
                },
            ]
        )

        def fake_json(_system, _user, temperature=0.3):
            return next(replies)

        with (
            patch("setu.llm.llm_configured", return_value=True),
            patch("setu.orchestrator.llm.llm_configured", return_value=True),
            patch("setu.llm.chat_json", side_effect=fake_json),
            patch("setu.orchestrator.llm.chat_json", side_effect=fake_json),
        ):
            handle_message(uid, "marathi")
            handle_message(uid, "2")
            reply = handle_message(uid, "can you switch back to english. i stay in karnataka")
            self.assertEqual(get_session(uid)["language"], "English")
            self.assertIn("household", reply.lower())

            reply = handle_message(uid, "20")
            self.assertEqual(get_session(uid)["language"], "English")
            self.assertIn("children", reply.lower())
            self.assertNotRegex(reply, r"[\u0900-\u097F]")

            reply = handle_message(uid, "0")
            self.assertEqual(get_session(uid)["language"], "English")
            self.assertIn("60", reply)
            self.assertNotIn("ration", reply.lower())
            self.assertNotIn("insurance", reply.lower())
            self.assertLess(reply.count("?"), 2)
            self.assertEqual(get_session(uid)["slots"].get("children_under_18"), "0")
            self.assertFalse(get_session(uid)["slots"].get("ration_card"))

    def test_journey1_hindi_dump_is_replaced_with_one_slot(self):
        uid = "llm-j1"
        reset_session(uid)
        replies = iter(
            [
                {"language": "Hindi", "reply": "नमस्ते! Individual / Family / Help?"},
                {"choice": "Individual Schemes", "reply": "नमस्ते! आप किस राज्य से हैं?"},
                {
                    "slots": {"state": "Karnataka"},
                    "reply": J1_DUMP,
                    "ready_for_confirm": False,
                },
            ]
        )

        def fake_json(_system, _user, temperature=0.3):
            return next(replies)

        with (
            patch("setu.llm.llm_configured", return_value=True),
            patch("setu.orchestrator.llm.llm_configured", return_value=True),
            patch("setu.llm.chat_json", side_effect=fake_json),
            patch("setu.orchestrator.llm.chat_json", side_effect=fake_json),
        ):
            handle_message(uid, "hindi")
            handle_message(uid, "Vyaktigat")
            reply = handle_message(uid, "Karnataka")
            self.assertEqual(get_session(uid)["language"], "Hindi")
            self.assertIn("आयु", reply)
            self.assertNotIn("वैवाहिक", reply)
            self.assertNotIn("Farmer, Labourer", reply)
            self.assertEqual(get_session(uid)["slots"].get("state"), "Karnataka")
            self.assertFalse(get_session(uid)["slots"].get("occupation"))


if __name__ == "__main__":
    unittest.main()
