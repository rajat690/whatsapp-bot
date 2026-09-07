"""Greeting / activation lexicon (EN, HI, MR, KN)."""

from __future__ import annotations

import unittest

from setu import greetings
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session


class GreetingDetectorTests(unittest.TestCase):
    def test_pure_greetings(self):
        for text in (
            "hi",
            "hello",
            "hey",
            "hiya",
            "hii",
            "radhe radhe",
            "namaskar",
            "नमस्ते",
            "ನಮಸ್ಕಾರ",
            "🙏",
            "👋",
            "namaste",
            "राम राम",
            "good morning",
        ):
            self.assertTrue(greetings.is_pure_greeting(text), msg=text)

    def test_farmer_hello_is_not_pure_greeting(self):
        text = "i am a farmer hello what schemes"
        self.assertFalse(greetings.is_pure_greeting(text))


class GreetingActivationTests(unittest.TestCase):
    def test_greetings_activate_welcome(self):
        for i, text in enumerate(
            (
                "radhe radhe",
                "namaskar",
                "नमस्ते",
                "ನಮಸ್ಕಾರ",
                "hey",
                "hello",
                "hiii",
                "🙏",
            )
        ):
            uid = f"greet-{i}"
            reset_session(uid)
            reply = handle_message(uid, text)
            session = get_session(uid)
            self.assertEqual(session["phase"], "welcome_language", msg=text)
            self.assertIn("language", reply.lower())
            self.assertIn("SETU", reply)

    def test_farmer_hello_does_not_restart(self):
        uid = "greet-farmer"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "individual")
        handle_message(uid, "Karnataka")
        from tests.helpers import accept_consent

        accept_consent(uid)
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        reply = handle_message(uid, "i am a farmer hello what schemes")
        session = get_session(uid)
        self.assertNotEqual(session["phase"], "welcome_language")
        self.assertEqual(session["phase"], "collect_profile")
        self.assertEqual(session["slots"].get("state"), "Karnataka")
        self.assertNotIn("which language", reply.lower())

    def test_hello_mid_collect_restarts_workflow(self):
        uid = "greet-mid"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "individual")
        handle_message(uid, "Karnataka")
        from tests.helpers import accept_consent

        accept_consent(uid)
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        reply = handle_message(uid, "hello")
        session = get_session(uid)
        self.assertEqual(session["phase"], "welcome_language")
        self.assertIsNone(session.get("language"))
        self.assertFalse(session.get("slots"))
        self.assertIn("language", reply.lower())
        self.assertNotIn("which age group", reply.lower())
        self.assertNotIn("individual schemes", reply.lower())


if __name__ == "__main__":
    unittest.main()
