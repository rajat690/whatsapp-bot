"""Conversational engine: interrupts, ≤4 collect, known_profile, slot buttons."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from setu.interactive import spec_mode
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent

FARMER = (
    "i am 50 yr old farmer i have 2 kids in family 2 girls 8th class wife is "
    "ahouse wife i am a dlaily wage labouror, i have a small farm, what scheme "
    "and subsidy can i recieve"
)


def _start_individual(uid: str) -> str:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, "English")
    handle_message(uid, "individual schemes")
    handle_message(uid, "Karnataka")
    return accept_consent(uid) or ""


def _start_family(uid: str) -> str:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, "English")
    handle_message(uid, "family schemes")
    handle_message(uid, "Karnataka")
    return accept_consent(uid) or ""


class CollectInteractiveTests(unittest.TestCase):
    def test_age_group_options_are_interactive_buttons(self):
        uid = "eng-age-btns"
        reply = _start_individual(uid)
        self.assertIn("age", reply.lower())
        outbound = get_session(uid).get("outbound") or {}
        opts = outbound.get("options") or []
        ids = [row["id"] for row in opts]
        self.assertEqual(ids, ["0–17", "18–59", "60+"])
        self.assertEqual(spec_mode(opts), "buttons")
        self.assertIn("1.", reply)
        self.assertIn("2.", reply)
        self.assertIn("3.", reply)

        reply = handle_message(uid, "2")
        self.assertEqual(get_session(uid)["slots"].get("age_group"), "18–59")
        outbound = get_session(uid).get("outbound") or {}
        occ_ids = [row["id"] for row in outbound.get("options") or []]
        self.assertIn("Farmer", occ_ids)
        self.assertIn("Retired", occ_ids)
        self.assertEqual(spec_mode(outbound.get("options") or []), "list")
        self.assertIn("occupation", reply.lower() + " ".join(occ_ids).lower())


class FourQuestionCapTests(unittest.TestCase):
    def test_individual_asks_at_most_four_post_consent_then_confirm(self):
        uid = "eng-j1-cap"
        _start_individual(uid)
        asks = []
        replies = []
        for msg in ("28", "salaried", "25000", "OBC"):
            session = get_session(uid)
            self.assertEqual(session["phase"], "collect_profile", msg=msg)
            asks.append(session.get("collect_slot_id"))
            replies.append(handle_message(uid, msg))
        session = get_session(uid)
        self.assertEqual(session["phase"], "confirm_profile")
        self.assertEqual(asks, ["age_group", "occupation", "household_income", "social_category"])
        self.assertNotIn("marital", (replies[-1] or "").lower())
        self.assertIsNone(session["slots"].get("marital_status"))
        self.assertIn("18–59", session["slots"].get("age_group", ""))
        reply = handle_message(uid, "proceed")
        self.assertEqual(get_session(uid)["phase"], "scheme_list")
        self.assertRegex(reply, r"(?m)^1\. ")
        self.assertTrue(get_session(uid).get("matched_schemes"))

    def test_fifth_question_is_not_asked(self):
        uid = "eng-j1-no-fifth"
        _start_individual(uid)
        handle_message(uid, "28")
        handle_message(uid, "farmer")
        handle_message(uid, "10000")
        reply = handle_message(uid, "SC")
        session = get_session(uid)
        self.assertEqual(session["phase"], "confirm_profile")
        low = reply.lower()
        self.assertNotIn("marital", low)
        self.assertNotIn("disability", low)
        self.assertNotIn("do you have a disability", low)


class FarmerMultiSlotTests(unittest.TestCase):
    def test_farmer_family_text_fills_size_and_children_skips_size_ask(self):
        uid = "eng-farmer-family"
        reply = _start_family(uid)
        self.assertIn("people", reply.lower())
        reply = handle_message(uid, FARMER)
        session = get_session(uid)
        self.assertEqual(session["slots"].get("children_under_18"), "2")
        self.assertTrue(session["slots"].get("household_size"))
        self.assertNotEqual(session["slots"].get("household_size"), "50")
        low = reply.lower()
        self.assertNotIn("how many people live in your household", low)
        self.assertNotIn("including you", low)
        self.assertEqual(session["phase"], "collect_profile")
        self.assertNotEqual(session.get("collect_slot_id"), "household_size")
        self.assertNotEqual(session.get("collect_slot_id"), "children_under_18")


class MainMenuInterruptTests(unittest.TestCase):
    def test_main_menu_mid_collect_leaves_immediately(self):
        uid = "eng-menu-mid"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "family")
        handle_message(uid, "Maharashtra")
        accept_consent(uid)
        handle_message(uid, "5")
        session = get_session(uid)
        self.assertEqual(session["phase"], "collect_profile")
        last_slot = session.get("collect_slot_id")
        self.assertTrue(last_slot)
        reply = handle_message(uid, "main menu")
        session = get_session(uid)
        self.assertEqual(session["phase"], "main_menu")
        low = reply.lower()
        self.assertNotIn("pregnan", low)
        self.assertNotIn("disability", low)
        self.assertNotIn("breastfeed", low)
        self.assertIn("individual", low)
        self.assertNotEqual(session.get("collect_slot_id"), last_slot)

    def test_main_menu_mid_collect_skips_llm_reask(self):
        uid = "eng-menu-llm"
        _start_individual(uid)

        def boom(*_a, **_k):
            raise AssertionError("main menu must not go to LLM collect")

        with (
            patch("setu.llm.llm_configured", return_value=True),
            patch("setu.orchestrator.llm.llm_configured", return_value=True),
            patch("setu.llm.chat_json", side_effect=boom),
            patch("setu.orchestrator.llm.chat_json", side_effect=boom),
        ):
            reply = handle_message(uid, "main menu")
        self.assertEqual(get_session(uid)["phase"], "main_menu")
        self.assertNotIn("age group", reply.lower())
        self.assertNotIn("disability", reply.lower())


class KnownProfileTests(unittest.TestCase):
    def test_known_profile_survives_individual_to_category(self):
        uid = "eng-known"
        _start_individual(uid)
        handle_message(uid, "28")
        session = get_session(uid)
        self.assertEqual(session["known_profile"].get("state"), "Karnataka")
        self.assertTrue(session["known_profile"].get("age_group"))
        reply = handle_message(uid, "scholarship")
        session = get_session(uid)
        self.assertEqual(session.get("path"), "category")
        self.assertEqual(session["known_profile"].get("state"), "Karnataka")
        self.assertTrue(session["known_profile"].get("age_group"))
        self.assertIn("Scholarship", reply)


class VolunteerExtrasTests(unittest.TestCase):
    def test_volunteered_occupation_is_not_reasked(self):
        uid = "eng-volunteer"
        _start_individual(uid)
        reply = handle_message(uid, "I'm 28 and I work as a salaried employee")
        session = get_session(uid)
        self.assertEqual(session["slots"].get("age_group"), "18–59")
        self.assertEqual(session["slots"].get("occupation"), "Salaried")
        self.assertNotEqual(session.get("collect_slot_id"), "occupation")
        self.assertNotIn("what best describes your current occupation", reply.lower())


if __name__ == "__main__":
    unittest.main()
