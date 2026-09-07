"""Category path (schemes_by_category_v1) is isolated from Journey 1 / Journey 2."""

from __future__ import annotations

import re
import unittest

from setu import category_catalog as cat
from setu import eligibility, nlu
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session


def _walk_to_menu(uid: str, language: str = "English") -> None:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, language)


class MenuAndIsolationTests(unittest.TestCase):
    def test_button_3_is_category_not_help(self):
        self.assertEqual(nlu.detect_menu("3"), "Browse by category")
        self.assertEqual(nlu.detect_menu("browse category"), "Browse by category")
        self.assertEqual(nlu.detect_menu("श्रेणी से खोजें"), "Browse by category")
        self.assertEqual(nlu.detect_menu("1"), "Individual Schemes")
        self.assertEqual(nlu.detect_menu("2"), "Family Schemes")
        self.assertEqual(nlu.detect_menu("I need help"), "I need help")

    def test_buttons_1_and_2_still_start_journeys(self):
        uid = "iso-j1"
        _walk_to_menu(uid)
        reply = handle_message(uid, "1")
        session = get_session(uid)
        self.assertIsNone(session.get("path"))
        self.assertEqual(session.get("journey_id"), "journey_1")
        self.assertEqual(session.get("phase"), "collect_profile")
        self.assertIn("state", reply.lower())

        uid = "iso-j2"
        _walk_to_menu(uid)
        reply = handle_message(uid, "2")
        session = get_session(uid)
        self.assertIsNone(session.get("path"))
        self.assertEqual(session.get("journey_id"), "journey_2")
        self.assertEqual(session.get("phase"), "collect_profile")
        self.assertIn("state", reply.lower())
        self.assertIn("household", reply.lower())

    def test_help_text_still_works_without_button_3(self):
        uid = "iso-help"
        _walk_to_menu(uid)
        reply = handle_message(uid, "I need help")
        self.assertEqual(get_session(uid)["phase"], "help_crm")
        self.assertIn("support", reply.lower())
        self.assertNotEqual(get_session(uid).get("path"), "category")


class CategoryWalkTests(unittest.TestCase):
    def test_menu_3_walks_language_state_hub_questions_numbered_results(self):
        uid = "cat-edu"
        _walk_to_menu(uid)
        reply = handle_message(uid, "3")
        session = get_session(uid)
        self.assertEqual(session.get("path"), "category")
        self.assertEqual(session.get("journey_id"), "schemes_by_category_v1")
        self.assertEqual(session.get("phase"), "cat_language")
        self.assertIn("1.", reply)
        self.assertIn("English", reply)

        reply = handle_message(uid, "1")  # English
        self.assertEqual(get_session(uid)["phase"], "cat_state_scope")
        self.assertIn("Central", reply)

        reply = handle_message(uid, "2")  # Karnataka
        self.assertEqual(get_session(uid)["phase"], "cat_hub")
        self.assertEqual(get_session(uid)["state_scope"], "karnataka")
        self.assertEqual(get_session(uid)["slots"].get("state"), "Karnataka")
        self.assertIn("10.", reply)
        self.assertIn("Education", reply)

        reply = handle_message(uid, "1")  # education
        self.assertEqual(get_session(uid)["category_id"], "education")
        self.assertEqual(get_session(uid)["phase"], "cat_collect")
        self.assertIn("1 of 3", reply)
        self.assertIn("School", reply)

        handle_message(uid, "1")  # school 1-10
        handle_message(uid, "1")  # SC
        reply = handle_message(uid, "1")  # <1L
        session = get_session(uid)
        self.assertEqual(session["phase"], "cat_results")
        self.assertLessEqual(len(cat.questions_for("education", session["slots"])), 4)
        self.assertRegex(reply, r"(?m)^1\. ")
        self.assertTrue(session.get("matched_schemes"))
        self.assertIn("Back to categories", reply)
        self.assertIn("Main menu", reply)
        for i, _scheme in enumerate(session["matched_schemes"], 1):
            self.assertIn(f"{i}. ", reply)
        self.assertNotRegex(reply, r"(?m)^• ")

        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["phase"], "cat_detail")
        self.assertIn("Benefit", reply)

        reply = handle_message(uid, "Back to categories")
        self.assertEqual(get_session(uid)["phase"], "cat_hub")
        self.assertIn("Education", reply)

    def test_hub_more_and_back(self):
        uid = "cat-hub2"
        _walk_to_menu(uid)
        handle_message(uid, "3")
        handle_message(uid, "1")
        handle_message(uid, "1")  # Central only
        reply = handle_message(uid, "10")  # More
        self.assertEqual(get_session(uid)["hub_screen"], 2)
        self.assertIn("Food", reply)
        self.assertIn("Labour", reply)
        reply = handle_message(uid, "4")  # Back
        self.assertEqual(get_session(uid)["hub_screen"], 1)
        self.assertIn("Education", reply)

    def test_who_first_pregnant_routes_to_women_child(self):
        uid = "cat-who"
        _walk_to_menu(uid)
        handle_message(uid, "3")
        handle_message(uid, "1")
        handle_message(uid, "4")  # State + Central
        handle_message(uid, "1")  # Karnataka + Central
        handle_message(uid, "10")
        reply = handle_message(uid, "3")  # family_who
        self.assertEqual(get_session(uid)["phase"], "cat_who")
        self.assertIn("Pregnant", reply)
        reply = handle_message(uid, "1")  # pregnant
        session = get_session(uid)
        self.assertEqual(session["category_id"], "women_child")
        self.assertEqual(session["slots"].get("who"), "pregnant_lactating")
        self.assertEqual(session["phase"], "cat_collect")
        # who is preset, so first asked question is ration_level (2 of remaining)
        self.assertNotIn("Pregnant / lactating", reply.split("\n")[0])
        self.assertIn("AAY", reply)

    def test_who_first_disabled_sets_pension_slice(self):
        uid = "cat-dis"
        _walk_to_menu(uid)
        handle_message(uid, "3")
        handle_message(uid, "English")
        handle_message(uid, "Karnataka")
        handle_message(uid, "10")
        handle_message(uid, "Find by who")
        handle_message(uid, "2")  # disability
        session = get_session(uid)
        self.assertEqual(session["category_id"], "disability")
        self.assertTrue(session.get("pension_slice"))
        self.assertEqual(session["phase"], "cat_collect")

    def test_labour_skips_board_state_when_karnataka_already_chosen(self):
        qs = cat.questions_for("labour_bocw", {"state": "Karnataka"})
        self.assertEqual([q["id"] for q in qs], ["board_registered", "labour_need", "who_claims"])
        qs_central = cat.questions_for("labour_bocw", {})
        self.assertEqual(
            [q["id"] for q in qs_central],
            ["board_registered", "labour_need", "who_claims", "board_state"],
        )

        uid = "cat-labour"
        _walk_to_menu(uid)
        handle_message(uid, "3")
        handle_message(uid, "1")
        handle_message(uid, "2")  # Karnataka
        handle_message(uid, "10")
        reply = handle_message(uid, "2")  # labour
        self.assertIn("1 of 3", reply)
        handle_message(uid, "1")
        handle_message(uid, "1")
        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["phase"], "cat_results")
        self.assertRegex(reply, r"(?m)^1\. ")

    def test_hindi_menu_and_hub(self):
        uid = "cat-hi"
        _walk_to_menu(uid, "Hindi")
        reply = handle_message(uid, "3")
        self.assertIn("भाषा", reply)
        reply = handle_message(uid, "2")  # हिंदी
        self.assertEqual(get_session(uid)["language"], "Hindi")
        self.assertIn("केंद्र", reply)
        reply = handle_message(uid, "2")
        self.assertIn("शिक्षा", reply)
        self.assertIn("10.", reply)

    def test_main_menu_from_results(self):
        uid = "cat-menu"
        _walk_to_menu(uid)
        handle_message(uid, "3")
        handle_message(uid, "1")
        handle_message(uid, "1")
        handle_message(uid, "8")  # agriculture
        for _ in range(4):
            handle_message(uid, "1")
        self.assertEqual(get_session(uid)["phase"], "cat_results")
        reply = handle_message(uid, "Main menu")
        session = get_session(uid)
        self.assertEqual(session["phase"], "main_menu")
        self.assertIsNone(session.get("path"))
        self.assertIsNone(session.get("journey_id"))
        self.assertIn("3.", reply)

    def test_shift_to_kannada_from_hindi_menu_after_category(self):
        uid = "cat-shift-kn"
        _walk_to_menu(uid, "Hindi")
        handle_message(uid, "3")
        handle_message(uid, "2")  # Hindi
        handle_message(uid, "2")  # Karnataka
        handle_message(uid, "1")  # education
        for _ in range(3):
            handle_message(uid, "1")
        self.assertEqual(get_session(uid)["phase"], "cat_results")
        self.assertEqual(get_session(uid)["language"], "Hindi")
        handle_message(uid, "main menu")
        self.assertEqual(get_session(uid)["phase"], "main_menu")
        reply = handle_message(uid, "shift to kannada")
        session = get_session(uid)
        self.assertEqual(session["language"], "Kannada")
        self.assertEqual(session["phase"], "main_menu")
        self.assertIsNone(session.get("path"))
        self.assertNotIn("हिन्दी में ही", reply)
        self.assertRegex(reply, r"[\u0C80-\u0CFF]")
        self.assertIn("1.", reply)

    def test_shift_to_kannada_on_category_hub(self):
        uid = "cat-hub-shift"
        _walk_to_menu(uid, "Hindi")
        handle_message(uid, "3")
        handle_message(uid, "2")
        handle_message(uid, "2")
        self.assertEqual(get_session(uid)["phase"], "cat_hub")
        reply = handle_message(uid, "shift to kannada")
        self.assertEqual(get_session(uid)["language"], "Kannada")
        self.assertEqual(get_session(uid)["phase"], "cat_hub")
        self.assertNotIn("हिन्दी में ही", reply)
        self.assertRegex(reply, r"[\u0C80-\u0CFF]")
        self.assertIn("1.", reply)
        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["category_id"], "education")
        self.assertEqual(get_session(uid)["language"], "Kannada")


class ExistingJourneyNumberingTests(unittest.TestCase):
    def test_journey1_results_are_numbered_not_bullets(self):
        uid = "j1-num"
        _walk_to_menu(uid)
        handle_message(uid, "individual schemes")
        for msg in ("Karnataka", "28", "salaried", "25000", "OBC", "married", "no"):
            handle_message(uid, msg)
        reply = handle_message(uid, "proceed")
        session = get_session(uid)
        self.assertEqual(session["phase"], "scheme_list")
        self.assertEqual(session.get("path"), None)
        self.assertEqual(session.get("journey_id"), "journey_1")
        self.assertRegex(reply, r"(?m)^1\. ")
        self.assertTrue(session.get("matched_schemes"))
        lines = [ln for ln in reply.splitlines() if re.match(r"^\d+\. ", ln)]
        self.assertGreaterEqual(len(lines), 1)
        self.assertEqual(lines[0][:2], "1.")

    def test_category_session_does_not_use_journey1_collect(self):
        uid = "no-mix"
        _walk_to_menu(uid)
        handle_message(uid, "3")
        handle_message(uid, "1")
        handle_message(uid, "2")
        session = get_session(uid)
        self.assertEqual(session["path"], "category")
        self.assertNotEqual(session["phase"], "collect_profile")
        self.assertNotIn("age_group", session.get("slots") or {})
        self.assertNotIn("occupation", session.get("slots") or {})


class MatcherScopeTests(unittest.TestCase):
    def test_central_scope_excludes_state_library(self):
        matched, note = eligibility.match_category_schemes(
            {"edu_level": "school_1_10", "caste": "SC", "income_annual": "lt_1l"},
            "education",
            scope="central",
        )
        self.assertIn("Central", note)
        self.assertTrue(matched)
        self.assertTrue(all(s.get("_library") == "Central" for s in matched))
        self.assertRegex("\n".join(eligibility.numbered_scheme_lines(matched)), r"(?m)^1\. ")

    def test_karnataka_scope_is_state_only(self):
        matched, note = eligibility.match_category_schemes(
            {"state": "Karnataka", "edu_level": "ug", "caste": "SC", "income_annual": "lt_1l"},
            "education",
            scope="karnataka",
        )
        self.assertIn("Karnataka", note)
        self.assertTrue(matched)
        self.assertTrue(all(s.get("_library") == "Karnataka" for s in matched))

    def test_journey1_pool_still_combines_central_and_state(self):
        schemes, note = eligibility.load_scheme_pool("Karnataka")
        self.assertIn("Central + Karnataka", note)
        libs = {s.get("_library") for s in schemes}
        self.assertIn("Central", libs)
        self.assertIn("Karnataka", libs)


if __name__ == "__main__":
    unittest.main()
