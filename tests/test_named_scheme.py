"""Named-scheme lookup and anti-hallucination routing."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from setu import lookup, nlu
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session


class LookupTests(unittest.TestCase):
    def test_ujjwala_english_variants(self):
        for q in (
            "Tell me about pradhan mantri ujjwala yojana",
            "pmuy",
            "ujjwala yojana",
            "ujjvala yojana",
            "PM Ujjwala",
        ):
            hits = lookup.search_schemes(q)
            self.assertTrue(hits, msg=q)
            names = " ".join(s.get("Scheme Name", "") for s in hits).lower()
            self.assertIn("ujjwala", names, msg=q)

    def test_stree_shakti_variants(self):
        for q in (
            "stree shakti scheme",
            "stree sakti",
            "stri shakti",
            "स्त्री शक्ति",
        ):
            hits = lookup.search_schemes(q)
            self.assertTrue(hits, msg=q)
            names = " ".join(s.get("Scheme Name", "") for s in hits).lower()
            self.assertIn("stree shakti", names, msg=q)

    def test_hindi_ujjwala_query(self):
        hits = lookup.search_schemes("प्रधानमंत्री उज्ज्वला योजना के बारे में बताओ")
        self.assertTrue(hits)
        self.assertIn("ujjwala", hits[0]["Scheme Name"].lower())

    def test_unknown_scheme_is_empty(self):
        self.assertFalse(lookup.search_schemes("tell me about totally fake yojana xyz123"))

    def test_detail_is_numbered_and_library_only(self):
        hits = lookup.search_schemes("ujjwala")
        card = lookup.format_named_scheme_detail(hits[0], "What next?")
        self.assertTrue(card.startswith("1. Name:"))
        self.assertIn("2. About:", card)
        self.assertIn("lpg", card.lower())
        self.assertNotIn("End Chat", card)
        self.assertIn("pmuy.gov.in", card.lower())


class NluSchemeAskTests(unittest.TestCase):
    def test_plain_menu_is_not_a_scheme_ask(self):
        for msg in ("individual", "family", "individual schemes", "help", "1", "2"):
            self.assertTrue(nlu.is_plain_menu_choice(msg), msg=msg)
            self.assertFalse(nlu.looks_like_scheme_ask(msg), msg=msg)

    def test_named_scheme_phrases_are_asks(self):
        self.assertTrue(nlu.looks_like_scheme_ask("Tell me about ujjwala yojana"))
        self.assertTrue(nlu.looks_like_scheme_ask("stree shakti scheme"))
        self.assertFalse(nlu.is_plain_menu_choice("stree shakti scheme"))


class NamedSchemeFlowTests(unittest.TestCase):
    def test_welcome_named_scheme_does_not_force_journey(self):
        uid = "ns-welcome-ujjwala"
        reset_session(uid)
        reply = handle_message(uid, "Tell me about pradhan mantri ujjwala yojana")
        low = reply.lower()
        self.assertIn("ujjwala", low)
        self.assertIn("lpg", low)
        self.assertIn("1. name:", low)
        self.assertNotIn("end chat", low)
        self.assertNotEqual(get_session(uid)["phase"], "collect_profile")
        self.assertEqual(get_session(uid)["phase"], "named_scheme")

    def test_stree_shakti_after_hindi_does_not_dead_end(self):
        uid = "ns-stree"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "hindi")
        reply = handle_message(uid, "stree shakti scheme")
        self.assertIn("stree shakti", reply.lower())
        self.assertNotIn("End Chat", reply)
        self.assertEqual(get_session(uid)["phase"], "named_scheme")

        reply = handle_message(uid, "individual")
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        self.assertEqual(get_session(uid)["journey_id"], "journey_1")
        self.assertNotIn("End Chat", reply)
        self.assertRegex(reply.lower(), r"state|राज्य")

    def test_honest_miss_does_not_invent(self):
        uid = "ns-miss"
        reset_session(uid)
        handle_message(uid, "English")
        reply = handle_message(uid, "tell me about totally fake yojana xyz123")
        low = reply.lower()
        self.assertIn("could not find", low)
        self.assertIn("will not guess", low)
        self.assertNotIn("end chat", low)
        self.assertIn("individual", low)
        self.assertIn("family", low)

    def test_individual_family_menu_paths_still_work(self):
        uid = "ns-j1"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(uid, "individual schemes")
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        self.assertIn("state", reply.lower())

        uid = "ns-j2"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(uid, "family schemes")
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        self.assertEqual(get_session(uid)["journey_id"], "journey_2")
        self.assertIn("state", reply.lower())

    def test_llm_cannot_route_named_scheme_to_help_or_end_chat(self):
        uid = "ns-llm-trap"
        reset_session(uid)
        handle_message(uid, "English")

        def boom(*_args, **_kwargs):
            raise AssertionError("LLM should not classify a named-scheme ask")

        with (
            patch("setu.llm.llm_configured", return_value=True),
            patch("setu.orchestrator.llm.llm_configured", return_value=True),
            patch("setu.llm.chat_json", side_effect=boom),
            patch("setu.orchestrator.llm.chat_json", side_effect=boom),
            patch("setu.llm.chat_text", side_effect=boom),
            patch("setu.orchestrator.llm.chat_text", side_effect=boom),
        ):
            reply = handle_message(uid, "stree shakti scheme")
        self.assertIn("stree shakti", reply.lower())
        self.assertNotIn("end chat", reply.lower())
        self.assertEqual(get_session(uid)["phase"], "named_scheme")

        reply = handle_message(uid, "individual")
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        self.assertNotIn("end chat", reply.lower())

    def test_help_phase_named_scheme_does_not_end_chat(self):
        uid = "ns-help"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "help")
        self.assertEqual(get_session(uid)["phase"], "help_crm")
        reply = handle_message(uid, "Tell me about pradhan mantri ujjwala yojana")
        self.assertIn("ujjwala", reply.lower())
        self.assertNotIn("End Chat", reply)
        self.assertEqual(get_session(uid)["phase"], "named_scheme")

    def test_numbered_next_action_starts_family(self):
        uid = "ns-next"
        reset_session(uid)
        handle_message(uid, "Tell me about ujjwala yojana")
        # 1 another, 2 individual, 3 family, 4 main menu (no category module on main)
        reply = handle_message(uid, "3")
        self.assertEqual(get_session(uid)["journey_id"], "journey_2")
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        self.assertIn("state", reply.lower())


if __name__ == "__main__":
    unittest.main()
