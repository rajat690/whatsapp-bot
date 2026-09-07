"""Free-text reply map: named scheme, category, profile story, role shortcuts, vague."""

from __future__ import annotations

import unittest

from setu import profile_intent
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session

FARMER = (
    "i am 50 yr old farmer i have 2 kids in family 2 girls 8th class wife is "
    "ahouse wife i am a dlaily wage labouror, i have a small farm, what scheme "
    "and subsidy can i recieve"
)


class ClassifyOrderTests(unittest.TestCase):
    def test_farmer_story_is_who_first_not_named_scheme(self):
        self.assertTrue(profile_intent.is_profile_story(FARMER))
        self.assertTrue(profile_intent.mentions_multiple_people(FARMER))
        self.assertTrue(profile_intent.block_named_lookup(FARMER))
        self.assertFalse(profile_intent.looks_like_scheme_name_query(FARMER))
        self.assertIsNone(profile_intent.detect_role_shortcut(FARMER))
        self.assertEqual(profile_intent.classify_free_text(FARMER), "who_first")

    def test_ujjwala_is_named_scheme(self):
        q = "Tell me about pradhan mantri ujjwala yojana"
        self.assertTrue(profile_intent.looks_like_scheme_name_query(q))
        self.assertEqual(profile_intent.classify_free_text(q), "named_scheme")

    def test_scholarship_is_category(self):
        self.assertEqual(profile_intent.classify_free_text("scholarship"), "category")

    def test_widow_is_pension_shortcut(self):
        self.assertEqual(profile_intent.detect_role_shortcut("I am a widow, what can I get"), "pension")
        self.assertEqual(profile_intent.classify_free_text("I am a widow, what can I get"), "shortcut")

    def test_vague_subsidy(self):
        self.assertTrue(profile_intent.is_vague_subsidy("help me get subsidy"))
        self.assertEqual(profile_intent.classify_free_text("help me get subsidy"), "vague")


class ProfileStoryFlowTests(unittest.TestCase):
    def test_farmer_example_opens_who_menu_not_lookup_miss(self):
        uid = "story-farmer"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(uid, FARMER)
        session = get_session(uid)
        self.assertEqual(session["phase"], "who_first")
        self.assertNotIn("could not find a matching scheme named", reply.lower())
        self.assertNotIn(FARMER.lower(), reply.lower())
        self.assertIn("schemes for me", reply.lower())
        self.assertIn("wife", reply.lower())
        self.assertIn("children", reply.lower())
        self.assertIn("whole family", reply.lower())
        self.assertIn("1.", reply)
        self.assertIn("6.", reply)
        ids = [row["id"] for row in (session.get("outbound") or {}).get("options") or []]
        self.assertEqual(
            ids,
            [
                "who_me",
                "who_wife",
                "who_children",
                "who_family",
                "who_category",
                "who_menu",
            ],
        )

        reply = handle_message(uid, "4")  # whole family
        session = get_session(uid)
        self.assertEqual(session["journey_id"], "journey_2")
        self.assertEqual(session["phase"], "collect_profile")
        self.assertIn("state", reply.lower())

    def test_farmer_me_with_mixed_roles_starts_individual(self):
        uid = "story-me"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, FARMER)
        reply = handle_message(uid, "1")  # me — farmer+labour → Individual
        session = get_session(uid)
        self.assertEqual(session["journey_id"], "journey_1")
        self.assertIsNone(session.get("path"))
        self.assertIn("state", reply.lower())

    def test_widow_routes_to_pension_pack(self):
        uid = "story-widow"
        reset_session(uid)
        handle_message(uid, "English")
        reply = handle_message(uid, "I am a widow, what can I get")
        session = get_session(uid)
        self.assertEqual(session.get("path"), "category")
        self.assertEqual(session.get("category_id"), "pension")
        self.assertEqual(session.get("phase"), "cat_state_scope")
        self.assertIn("Pension", reply)
        self.assertNotIn("could not find a matching scheme named", reply.lower())

    def test_scholarship_still_category(self):
        uid = "story-schol"
        reset_session(uid)
        handle_message(uid, "English")
        reply = handle_message(uid, "scholarship")
        session = get_session(uid)
        self.assertEqual(session.get("category_id"), "scholarship")
        self.assertEqual(session.get("path"), "category")
        self.assertIn("Scholarship", reply)

    def test_ujjwala_still_named_scheme(self):
        uid = "story-ujj"
        reset_session(uid)
        handle_message(uid, "English")
        reply = handle_message(uid, "Tell me about pradhan mantri ujjwala yojana")
        session = get_session(uid)
        self.assertEqual(session["phase"], "named_scheme")
        self.assertIn("ujjwala", reply.lower())
        self.assertIn("lpg", reply.lower())

    def test_vague_subsidy_asks_who(self):
        uid = "story-vague"
        reset_session(uid)
        handle_message(uid, "English")
        reply = handle_message(uid, "help me get subsidy")
        session = get_session(uid)
        self.assertEqual(session["phase"], "who_clarify")
        self.assertNotEqual(session["phase"], "help_crm")
        self.assertIn("who", reply.lower())
        self.assertIn("schemes for me", reply.lower())
        self.assertNotIn("could not find a matching scheme named", reply.lower())

    def test_pregnant_shortcut_women_child(self):
        uid = "story-preg"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "I am pregnant, what support is there")
        session = get_session(uid)
        self.assertEqual(session.get("category_id"), "women_child")
        self.assertEqual(session.get("path"), "category")

    def test_disability_shortcut(self):
        uid = "story-dis"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "I have 80% handicap, which schemes")
        session = get_session(uid)
        self.assertEqual(session.get("category_id"), "disability")
        self.assertTrue(session.get("pension_slice"))

    def test_bocw_shortcut(self):
        uid = "story-bocw"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "I am a construction labourer registered with BOCW")
        session = get_session(uid)
        self.assertEqual(session.get("category_id"), "labour_bocw")


if __name__ == "__main__":
    unittest.main()
