"""Gender collect slot, free-text extract, and eligibility policy."""

from __future__ import annotations

import unittest

from setu import category_catalog as cat
from setu import conversation_engine as engine
from setu import eligibility, i18n, nlu, profile_intent
from setu.interactive import spec_mode
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent

UJJWALA = {
    "Scheme Name": "Pradhan Mantri Ujjwala Yojana (PMUY)",
    "Category": "Energy / Clean cooking fuel",
    "Age Criteria": "Adult woman applicant",
    "Income Criteria": "Targeted to women from poor households",
    "Gender / Category Criteria": "Woman of the household as connection holder; priority categories as notified",
    "Other Key Eligibility Criteria": "No existing LPG connection",
    "Benefit": "LPG connection",
}

MALE_ONLY = {
    "Scheme Name": "Example Men Only Grant",
    "Category": "Livelihood",
    "Age Criteria": "Adult",
    "Income Criteria": "No income restriction",
    "Gender / Category Criteria": "Men only",
    "Other Key Eligibility Criteria": "",
    "Benefit": "Grant",
}


def _start_individual(uid: str, language: str = "English") -> str:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, language)
    handle_message(uid, "individual schemes")
    handle_message(uid, "Karnataka")
    return accept_consent(uid) or ""


def _start_family(uid: str, language: str = "English") -> str:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, language)
    handle_message(uid, "family schemes")
    handle_message(uid, "Karnataka")
    return accept_consent(uid) or ""


def _to_category_hub(uid: str, language: str = "English") -> str:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, language)
    handle_message(uid, "3")
    handle_message(uid, "1" if language == "English" else language)
    handle_message(uid, "2")
    return accept_consent(uid) or ""


class GenderExtractTests(unittest.TestCase):
    def test_english_self_id(self):
        self.assertEqual(nlu.detect_gender("I am a woman"), "Female")
        self.assertEqual(nlu.detect_gender("I am female age 30"), "Female")
        self.assertEqual(nlu.detect_gender("I'm a man"), "Male")
        self.assertEqual(nlu.detect_gender("I am male"), "Male")
        self.assertIsNone(nlu.detect_gender("2 girls 8th class"))

    def test_indic_self_id(self):
        self.assertEqual(nlu.detect_gender("मैं महिला हूँ उम्र 30"), "Female")
        self.assertEqual(nlu.detect_gender("मैं पुरुष हूँ"), "Male")
        self.assertEqual(nlu.detect_gender("मी स्त्री आहे"), "Female")
        self.assertEqual(nlu.detect_gender("ನಾನು ಪುರುಷ"), "Male")
        self.assertEqual(nlu.detect_gender("ನಾನು ಮಹಿಳೆ"), "Female")

    def test_prefer_not_on_gender_ask(self):
        self.assertEqual(nlu.detect_gender("Prefer not to say", prefer=True), "Prefer not to say")
        self.assertEqual(nlu.detect_gender("नहीं बताना", prefer=True), "Prefer not to say")
        self.assertEqual(nlu.detect_gender("सांगायचे नाही", prefer=True), "Prefer not to say")
        self.assertEqual(nlu.detect_gender("ಹೇಳಲು ಇಷ್ಟವಿಲ್ಲ", prefer=True), "Prefer not to say")

    def test_bare_token_only_when_asking(self):
        self.assertIsNone(nlu.detect_gender("female"))
        self.assertEqual(nlu.detect_gender("female", prefer=True), "Female")
        self.assertEqual(nlu.detect_gender("पुरुष", prefer=True), "Male")

    def test_extract_slots_from_story(self):
        slots = nlu.extract_slots(
            "I am female age 30 and work as daily labourer",
            engine.load_journey("journey_1")["slots"],
        )
        self.assertEqual(slots.get("gender"), "Female")
        self.assertEqual(slots.get("age"), "30")
        self.assertEqual(slots.get("age_group"), "18–59")
        self.assertEqual(slots.get("occupation"), "Labourer")


class GenderButtonCollectTests(unittest.TestCase):
    def test_individual_shows_gender_buttons_when_unknown(self):
        uid = "gen-j1-btns"
        _start_individual(uid)
        reply = handle_message(uid, "28")
        session = get_session(uid)
        self.assertEqual(session.get("collect_slot_id"), "gender")
        self.assertIn("gender", reply.lower())
        outbound = session.get("outbound") or {}
        ids = [row["id"] for row in outbound.get("options") or []]
        self.assertEqual(ids, ["Male", "Female", "Prefer not to say"])
        self.assertEqual(spec_mode(outbound.get("options") or []), "buttons")
        self.assertEqual(outbound.get("list_button"), "choose gender")
        self.assertIn("1.", reply)
        self.assertIn("2.", reply)
        self.assertIn("3.", reply)

    def test_family_shows_gender_buttons_when_unknown(self):
        uid = "gen-j2-btns"
        _start_family(uid)
        reply = handle_message(uid, "4")
        session = get_session(uid)
        self.assertEqual(session.get("collect_slot_id"), "gender")
        outbound = session.get("outbound") or {}
        ids = [row["id"] for row in outbound.get("options") or []]
        self.assertEqual(ids, ["Male", "Female", "Prefer not to say"])
        self.assertEqual(spec_mode(outbound.get("options") or []), "buttons")
        self.assertIn("gender", reply.lower())
        self.assertEqual(outbound.get("list_button"), "choose gender")

    def test_category_collect_shows_gender_when_unknown(self):
        uid = "gen-cat-btns"
        _to_category_hub(uid)
        reply = handle_message(uid, "1")  # education
        session = get_session(uid)
        self.assertEqual(session["phase"], "cat_collect")
        self.assertIn("School", reply)
        handle_message(uid, "1")
        handle_message(uid, "1")
        reply = handle_message(uid, "1")
        session = get_session(uid)
        self.assertEqual(session["phase"], "cat_collect")
        q = cat.questions_for("education", session.get("slots"))
        idx = session.get("cat_q_index") or 0
        self.assertEqual(q[idx]["id"], "gender")
        outbound = session.get("outbound") or {}
        ids = [row["id"] for row in outbound.get("options") or []]
        self.assertEqual(ids, ["Male", "Female", "Prefer not to say"])
        self.assertEqual(spec_mode(outbound.get("options") or []), "buttons")
        self.assertEqual(outbound.get("list_button"), "choose gender")

    def test_localized_choose_gender_and_option_titles(self):
        cases = (
            ("English", "choose gender", "Male", "Female", "Prefer not to say"),
            ("Hindi", "लिंग चुनें", "पुरुष", "महिला", "नहीं बताना"),
            ("Marathi", "लिंग निवडा", "पुरुष", "महिला", "सांगायचे नाही"),
            ("Kannada", "ಲಿಂಗ ಆಯ್ಕೆ", "ಪುರುಷ", "ಮಹಿಳೆ", "ಹೇಳಲು ಇಷ್ಟವಿಲ್ಲ"),
        )
        for lang, button, male, female, pnts in cases:
            self.assertEqual(
                i18n.interactive_list_button(lang, phase="collect_profile", slot_id="gender"),
                button,
            )
            self.assertLessEqual(len(button), 20)
            self.assertNotEqual(button.lower(), "choose")
            self.assertEqual(i18n.option_label("gender", "Male", lang), male)
            self.assertEqual(i18n.option_label("gender", "Female", lang), female)
            self.assertEqual(i18n.option_label("gender", "Prefer not to say", lang), pnts)
            self.assertLessEqual(len(pnts), 20, msg=lang)


class GenderSkipAndStoreTests(unittest.TestCase):
    def test_free_text_female_skips_gender_ask(self):
        uid = "gen-skip-ft"
        _start_individual(uid)
        reply = handle_message(uid, "I am female age 30 and work as a salaried employee")
        session = get_session(uid)
        self.assertEqual(session["slots"].get("gender"), "Female")
        self.assertEqual(session["known_profile"].get("gender"), "Female")
        self.assertNotEqual(session.get("collect_slot_id"), "gender")
        self.assertNotIn("which gender", reply.lower())
        self.assertNotIn("choose gender", reply.lower())

    def test_prefer_not_to_say_stored_and_flow_continues(self):
        uid = "gen-pnts"
        _start_individual(uid)
        handle_message(uid, "28")
        reply = handle_message(uid, "Prefer not to say")
        session = get_session(uid)
        self.assertEqual(session["slots"].get("gender"), "Prefer not to say")
        self.assertEqual(session["known_profile"].get("gender"), "Prefer not to say")
        self.assertEqual(session["phase"], "collect_profile")
        self.assertEqual(session.get("collect_slot_id"), "occupation")
        handle_message(uid, "salaried")
        reply = handle_message(uid, "25000")
        session = get_session(uid)
        self.assertEqual(session["phase"], "confirm_profile")
        reply = handle_message(uid, "proceed")
        self.assertEqual(get_session(uid)["phase"], "scheme_list")
        self.assertRegex(reply, r"(?m)^1\. ")

    def test_hindi_female_free_text_skips_gender(self):
        uid = "gen-hi-skip"
        _start_individual(uid, "Hindi")
        handle_message(uid, "28")
        reply = handle_message(uid, "मैं महिला हूँ")
        session = get_session(uid)
        self.assertEqual(session["slots"].get("gender"), "Female")
        self.assertNotEqual(session.get("collect_slot_id"), "gender")
        self.assertNotIn("लिंग चुनें", reply)


class GenderEligibilityTests(unittest.TestCase):
    def test_male_hard_fails_women_only(self):
        self.assertTrue(
            eligibility.is_hard_ineligible(UJJWALA, {"gender": "Male", "age": "30"})
        )
        self.assertFalse(
            eligibility.is_hard_ineligible(UJJWALA, {"gender": "Female", "age": "30"})
        )

    def test_prefer_not_to_say_does_not_hard_fail(self):
        self.assertFalse(
            eligibility.is_hard_ineligible(
                UJJWALA, {"gender": "Prefer not to say", "age": "30"}
            )
        )
        score, reasons = eligibility._score_scheme(
            UJJWALA, {"gender": "Prefer not to say", "age_group": "18–59"}
        )
        self.assertIn("gender-unconfirmed", reasons)
        self.assertGreater(score, 0)

    def test_female_hard_fails_male_only(self):
        self.assertTrue(
            eligibility.is_hard_ineligible(MALE_ONLY, {"gender": "Female"})
        )
        self.assertFalse(
            eligibility.is_hard_ineligible(MALE_ONLY, {"gender": "Prefer not to say"})
        )
        self.assertFalse(eligibility.is_hard_ineligible(MALE_ONLY, {"gender": "Male"}))

    def test_male_match_excludes_ujjwala(self):
        matched, _ = eligibility.match_schemes(
            {
                "gender": "Male",
                "age": "30",
                "age_group": "18–59",
                "occupation": "Labourer",
                "state": "Karnataka",
            },
            limit=16,
        )
        names = [(s.get("Scheme Name") or "").lower() for s in matched]
        self.assertFalse(any("ujjwala" in n or "pmuy" in n for n in names), names)


class GenderBudgetPolicyTests(unittest.TestCase):
    def test_individual_asks_gender_in_the_four(self):
        ids = engine.collect_slot_ids("journey_1", {})
        self.assertEqual(ids, ["state", "age_group", "gender", "occupation", "household_income"])
        known = engine.collect_slot_ids("journey_1", {"gender": "Female"})
        self.assertEqual(
            known, ["state", "age_group", "occupation", "household_income", "social_category"]
        )

    def test_family_asks_gender_in_the_four(self):
        ids = engine.collect_slot_ids("journey_2", {})
        self.assertEqual(
            ids, ["state", "household_size", "gender", "children_under_18", "household_income"]
        )

    def test_women_child_preset_skips_gender_question(self):
        qs = cat.questions_for("women_child", {"who": "adult_woman"})
        self.assertNotIn("gender", [q["id"] for q in qs])
        self.assertEqual(cat.infer_gender({"who": "pregnant_lactating"}), "Female")

    def test_oneshot_female_story_stores_gender_and_skips_ask(self):
        uid = "gen-oneshot"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(
            uid,
            "I am female age 30 and work as daily labourer. I am muslim. what schemes will i get?",
        )
        session = get_session(uid)
        self.assertEqual(session.get("known_profile", {}).get("gender"), "Female")
        self.assertTrue(session.get("oneshot_profile"))
        self.assertNotIn("which gender", reply.lower())
        handle_message(uid, "Karnataka")
        accept_consent(uid)
        session = get_session(uid)
        self.assertEqual(session["phase"], "scheme_list")
        self.assertEqual(session["slots"].get("gender"), "Female")
        self.assertNotEqual(session.get("collect_slot_id"), "gender")

    def test_facts_from_signals_store_gender(self):
        facts = engine.facts_from_signals(
            "I am female age 30", profile_intent.extract_signals("I am female age 30")
        )
        self.assertEqual(facts.get("gender"), "Female")


class GenderFamilySubjectTests(unittest.TestCase):
    def test_family_menu_asks_self_gender(self):
        uid = "gen-fam-self"
        _start_family(uid)
        handle_message(uid, "4")
        session = get_session(uid)
        self.assertEqual(session.get("gender_subject"), "self")
        self.assertEqual(session.get("collect_slot_id"), "gender")
        outbound = session.get("outbound") or {}
        self.assertIn("you", (outbound.get("short_body") or "").lower())


if __name__ == "__main__":
    unittest.main()
