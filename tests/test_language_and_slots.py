"""Regression tests for session language + one-slot-per-turn collection."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from setu import i18n, nlu
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent


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

    def test_shift_to_kannada_and_similar_phrases(self):
        self.assertEqual(nlu.detect_language_switch("shift to kannada"), "Kannada")
        self.assertEqual(nlu.detect_language_switch("shift to Kannada"), "Kannada")
        self.assertEqual(nlu.detect_language_switch("change to Kannada"), "Kannada")
        self.assertEqual(nlu.detect_language_switch("switch to marathi"), "Marathi")
        self.assertEqual(nlu.detect_language_switch("switch to english"), "English")
        self.assertEqual(nlu.detect_language_switch("switch to hindi"), "Hindi")
        self.assertEqual(nlu.detect_language_switch("ಕನ್ನಡ"), "Kannada")
        self.assertEqual(nlu.detect_language_switch("कन्नड़"), "Kannada")
        self.assertTrue(nlu.is_language_switch_only("shift to kannada"))
        self.assertTrue(nlu.is_language_switch_only("change to Kannada"))
        self.assertTrue(nlu.is_language_switch_only("ಕನ್ನಡ"))
        self.assertFalse(
            nlu.is_language_switch_only("can you switch back to english. i stay in karnataka")
        )


class LanguageLockGuardTests(unittest.TestCase):
    def test_live_hindi_only_refusal_is_rejected(self):
        live = "माफ़ कीजिए, मैं अभी हिन्दी में ही सहायता कर सकता हूँ।"
        self.assertTrue(i18n.claims_single_language_lock(live))
        self.assertTrue(i18n.claims_single_language_lock("Sorry, I can only help in Hindi right now."))
        self.assertFalse(i18n.claims_single_language_lock("Sure, let's continue in Kannada."))
        self.assertFalse(i18n.claims_single_language_lock("ये योजनाएँ काम आ सकती हैं"))


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

    def test_natural_two_question_marks_is_not_a_dump(self):
        missing = [
            {"id": sid}
            for sid in ("age_group", "occupation", "household_income", "disability")
        ]
        natural = (
            "Nice, Karnataka! How old are you? Under 18, around 18 to 59, or 60+?"
        )
        self.assertFalse(i18n.is_multi_slot_prompt(natural, missing))
        self.assertTrue(i18n.usable_collect_reply(natural, "English", missing))

    def test_option_bullets_for_one_slot_are_not_a_dump(self):
        missing = [
            {"id": sid}
            for sid in ("occupation", "household_income", "social_category")
        ]
        natural = "Got it — you're 28. What do you do for work?\n• Farmer\n• Labourer\n• Salaried"
        self.assertFalse(i18n.is_multi_slot_prompt(natural, missing))
        self.assertTrue(i18n.usable_collect_reply(natural, "English", missing))

    def test_two_remaining_slots_asked_is_still_a_dump(self):
        missing = [
            {"id": sid}
            for sid in ("children_under_18", "members_60_plus", "housing")
        ]
        dump = "How many children under 18? And how many members are aged 60+?"
        self.assertTrue(i18n.is_multi_slot_prompt(dump, missing))
        self.assertFalse(i18n.usable_collect_reply(dump, "English", missing))


class LanguageMatchTests(unittest.TestCase):
    def test_english_allows_light_native_code_mix(self):
        reply = (
            "Sure, English it is. Noted — Karnataka (कर्नाटक). "
            "How many people live in your household?"
        )
        self.assertTrue(i18n.reply_matches_language(reply, "English"))
        self.assertTrue(
            i18n.usable_collect_reply(
                reply, "English", [{"id": "household_size"}, {"id": "children_under_18"}]
            )
        )

    def test_english_rejects_mostly_marathi_reply(self):
        reply = "कुटुंबात 18 वर्षांखालील किती मुले आहेत?"
        self.assertFalse(i18n.reply_matches_language(reply, "English"))

    def test_hindi_still_requires_devanagari(self):
        self.assertTrue(i18n.reply_matches_language("आप किस आयु वर्ग में हैं?", "Hindi"))
        self.assertFalse(i18n.reply_matches_language("Which age group are you in?", "Hindi"))


class KeywordJourneyTests(unittest.TestCase):
    def test_one_slot_at_a_time_without_llm_both_journeys(self):
        uid = "kw-j1"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(uid, "individual schemes")
        self.assertIn("state", reply.lower())
        handle_message(uid, "Karnataka")
        reply = accept_consent(uid)
        self.assertIn("age", reply.lower())
        self.assertNotIn("marital", reply.lower())
        self.assertNotIn("disability", reply.lower())
        self.assertNotIn("Examples:", reply)
        self.assertNotIn("Farmer, Labourer", reply)

        uid = "kw-j2"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "family schemes")
        handle_message(uid, "Karnataka")
        accept_consent(uid)
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
        self.assertEqual(get_session(uid)["phase"], "consent")
        reply = accept_consent(uid)
        self.assertIn("household", reply.lower())
        self.assertNotRegex(reply, r"[\u0900-\u097F]")
        reply = handle_message(uid, "20")
        self.assertEqual(get_session(uid)["language"], "English")
        self.assertIn("children", reply.lower())
        self.assertNotRegex(reply, r"[\u0900-\u097F]")

    def test_shift_to_kannada_from_hindi_main_menu(self):
        uid = "kw-shift-kn"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "Hindi")
        self.assertEqual(get_session(uid)["phase"], "main_menu")
        self.assertEqual(get_session(uid)["language"], "Hindi")
        reply = handle_message(uid, "shift to kannada")
        session = get_session(uid)
        self.assertEqual(session["language"], "Kannada")
        self.assertEqual(session["phase"], "main_menu")
        self.assertNotIn("हिन्दी में ही", reply)
        self.assertNotIn("only help in Hindi", reply.lower())
        self.assertNotIn("only speak", reply.lower())
        self.assertRegex(reply, r"[\u0C80-\u0CFF]")
        self.assertIn("1.", reply)
        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["journey_id"], "journey_1")
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        self.assertEqual(get_session(uid)["language"], "Kannada")

    def test_switch_languages_from_main_menu(self):
        uid = "kw-switch-menu"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(uid, "switch to marathi")
        self.assertEqual(get_session(uid)["language"], "Marathi")
        self.assertRegex(reply, r"[\u0900-\u097F]")
        reply = handle_message(uid, "switch to hindi")
        self.assertEqual(get_session(uid)["language"], "Hindi")
        self.assertIn("व्यक्तिगत", reply)
        reply = handle_message(uid, "switch to english")
        self.assertEqual(get_session(uid)["language"], "English")
        self.assertIn("Individual", reply)
        self.assertIn("continue in English", reply)
        self.assertNotIn("हिन्दी में ही", reply)

    def test_hard_branches_still_work(self):
        uid = "kw-branch"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "individual schemes")
        handle_message(uid, "Karnataka")
        accept_consent(uid)
        for msg in ("28", "salaried", "25000", "OBC", "married", "no"):
            handle_message(uid, msg)
        reply = handle_message(uid, "proceed")
        self.assertIn("scheme", reply.lower())
        self.assertRegex(reply, r"(?m)^1\. ")
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
            handle_message(uid, "can you switch back to english. i stay in karnataka")
            self.assertEqual(get_session(uid)["language"], "English")
            self.assertEqual(get_session(uid)["phase"], "consent")
            reply = accept_consent(uid)
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
            handle_message(uid, "Karnataka")
            self.assertEqual(get_session(uid)["phase"], "consent")
            reply = accept_consent(uid)
            self.assertEqual(get_session(uid)["language"], "Hindi")
            self.assertIn("आयु", reply)
            self.assertNotIn("वैवाहिक", reply)
            self.assertNotIn("Farmer, Labourer", reply)
            self.assertEqual(get_session(uid)["slots"].get("state"), "Karnataka")
            self.assertFalse(get_session(uid)["slots"].get("occupation"))

    def test_natural_llm_reply_is_shown_not_template(self):
        uid = "llm-natural"
        reset_session(uid)
        natural = (
            "Nice, Karnataka! How old are you? You can just say 28, or 60 if you're a senior."
        )
        replies = iter(
            [
                {"language": "English", "reply": "Hi! Individual, Family, or help?"},
                {
                    "choice": "Individual Schemes",
                    "reply": "Sure — which state do you live in?",
                },
                {
                    "slots": {"state": "Karnataka"},
                    "reply": natural,
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
            handle_message(uid, "English")
            handle_message(uid, "individual schemes")
            handle_message(uid, "I stay in Karnataka")
            self.assertEqual(get_session(uid)["phase"], "consent")
            reply = accept_consent(uid)
            self.assertIn(natural, reply)
            self.assertNotIn("Which age group are you in?", reply)
            self.assertNotIn("Examples:", reply)
            self.assertEqual(get_session(uid)["slots"].get("state"), "Karnataka")

    def test_off_topic_sentence_keeps_conversational_llm_reply(self):
        uid = "llm-offtopic"
        reset_session(uid)
        natural = (
            "Ha, I follow cricket too. Anyway — roughly how old are you?"
        )
        replies = iter(
            [
                {"language": "English", "reply": "Hi! Individual, Family, or help?"},
                {
                    "choice": "Individual Schemes",
                    "reply": "Which state do you live in?",
                },
                {
                    "slots": {"state": "Maharashtra"},
                    "reply": "Got it, Maharashtra. How old are you?",
                    "ready_for_confirm": False,
                },
                {
                    "slots": {},
                    "reply": natural,
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
            handle_message(uid, "English")
            handle_message(uid, "individual")
            handle_message(uid, "Maharashtra")
            self.assertEqual(get_session(uid)["phase"], "consent")
            accept_consent(uid)
            reply = handle_message(uid, "by the way did you watch the match yesterday")
            self.assertIn(natural, reply)
            self.assertFalse(get_session(uid)["slots"].get("age_group"))
            self.assertEqual(get_session(uid)["slots"].get("state"), "Maharashtra")

    def test_journey2_natural_reply_is_shown_not_template(self):
        uid = "llm-j2-natural"
        reset_session(uid)
        natural = (
            "Five of you — nice. How many children under 18? Zero is completely fine."
        )
        replies = iter(
            [
                {"language": "English", "reply": "Hi! Individual, Family, or help?"},
                {
                    "choice": "Family Schemes",
                    "reply": "Which state does your family live in?",
                },
                {
                    "slots": {"state": "Karnataka"},
                    "reply": "Karnataka, got it. How many people live in the house, including you?",
                    "ready_for_confirm": False,
                },
                {
                    "slots": {"household_size": "5"},
                    "reply": natural,
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
            handle_message(uid, "English")
            handle_message(uid, "family")
            handle_message(uid, "Karnataka")
            self.assertEqual(get_session(uid)["phase"], "consent")
            accept_consent(uid)
            reply = handle_message(uid, "there are five of us")
            self.assertIn(natural, reply)
            self.assertNotIn("How many children under 18 are in the household?", reply)
            self.assertEqual(get_session(uid)["slots"].get("household_size"), "5")

    def test_shift_to_kannada_from_hindi_menu_skips_llm_hindi_only_refusal(self):
        uid = "llm-shift-kn"
        reset_session(uid)
        hindi_menu = (
            "आज आप क्या देखना चाहेंगे?\n1. व्यक्तिगत\n2. परिवार\n3. श्रेणी से खोजें"
        )
        replies = iter(
            [
                {"language": "Hindi", "reply": hindi_menu},
            ]
        )

        def fake_json(_system, _user, temperature=0.3):
            try:
                return next(replies)
            except StopIteration:
                raise AssertionError("shift to kannada must not be sent to the LLM")

        with (
            patch("setu.llm.llm_configured", return_value=True),
            patch("setu.orchestrator.llm.llm_configured", return_value=True),
            patch("setu.llm.chat_json", side_effect=fake_json),
            patch("setu.orchestrator.llm.chat_json", side_effect=fake_json),
        ):
            handle_message(uid, "hindi")
            reply = handle_message(uid, "shift to kannada")
            self.assertEqual(get_session(uid)["language"], "Kannada")
            self.assertEqual(get_session(uid)["phase"], "main_menu")
            self.assertNotIn("हिन्दी में ही", reply)
            self.assertNotIn("only help in Hindi", reply.lower())
            self.assertRegex(reply, r"[\u0C80-\u0CFF]")
            self.assertIn("1.", reply)

    def test_llm_hindi_only_refusal_is_not_shown_at_main_menu(self):
        uid = "llm-lock-drop"
        reset_session(uid)
        replies = iter(
            [
                {
                    "language": "Hindi",
                    "reply": "आज आप क्या देखना चाहेंगे?\n1. व्यक्तिगत\n2. परिवार",
                },
                {
                    "choice": None,
                    "reply": "माफ़ कीजिए, मैं अभी हिन्दी में ही सहायता कर सकता हूँ।",
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
            reply = handle_message(uid, "something unclear")
            self.assertNotIn("हिन्दी में ही", reply)
            self.assertNotIn("only help in Hindi", reply.lower())
            self.assertEqual(get_session(uid)["language"], "Hindi")
            self.assertEqual(get_session(uid)["phase"], "main_menu")


if __name__ == "__main__":
    unittest.main()
