"""Hard interrupts: farewells, greeting restart, What-next split, list format."""

from __future__ import annotations

import re
import unittest

from setu import eligibility, nlu
from setu.conversation_engine import is_hard_stop
from setu.greetings import is_pure_greeting
from setu.interactive import outbound_sends
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent

LIST_ROW_RE = re.compile(r"^\d+\. .+ \[.+\]$")


def _to_named_kisan_list(uid: str) -> str:
    reset_session(uid)
    handle_message(uid, "English")
    reply = handle_message(uid, "kisan")
    return reply


def _to_individual_collect(uid: str) -> None:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, "English")
    handle_message(uid, "individual schemes")
    handle_message(uid, "Karnataka")
    accept_consent(uid)


def _assert_ended(test: unittest.TestCase, uid: str, reply: str) -> None:
    session = get_session(uid)
    test.assertEqual(session["phase"], "feedback")
    test.assertFalse(session.get("matched_schemes"))
    low = reply.lower()
    test.assertIn("thank you", low)
    test.assertNotIn("please type a scheme name", low)
    test.assertNotRegex(reply, r"(?m)^1\. .+ \[")
    test.assertNotIn("kisan credit", low)


class FarewellLexiconTests(unittest.TestCase):
    def test_standalone_farewells_are_hard_stops(self):
        for text in (
            "bye",
            "BYE",
            "bye bye",
            "bye bye bye",
            "byebye",
            "goodbye",
            "good bye",
            "good night",
            "goodnight",
            "gn",
            "tata",
            "ciao",
            "ola",
            "see you",
            "cya",
            "later",
            "ttyl",
            "take care",
            "tc",
            "exit",
            "quit",
            "stop",
            "end",
            "end chat",
            "End Chat",
            "close",
            "dhanyavad",
            "dhanyawaad",
            "धन्यवाद",
            "धन्यवाद!",
            "shukriya",
            "शुक्रिया",
            "alvida",
            "अलविदा",
            "fir milenge",
            "फिर मिलेंगे",
            "निरोप",
            "dhanyavaada",
            "ಧನ್ಯವಾದ",
            "vidaya",
            "ವಿದಾಯ",
        ):
            self.assertTrue(nlu.is_farewell(text), msg=text)
            self.assertTrue(is_hard_stop(text), msg=text)

    def test_namaste_is_greeting_not_farewell(self):
        self.assertTrue(is_pure_greeting("namaste"))
        self.assertTrue(is_pure_greeting("namaskar"))
        self.assertFalse(nlu.is_farewell("namaste"))
        self.assertFalse(nlu.is_farewell("namaskar"))
        self.assertFalse(nlu.is_farewell("नमस्ते"))

    def test_scheme_sentence_with_ola_is_not_farewell(self):
        self.assertFalse(nlu.is_farewell("tell me about ola scholarship"))
        self.assertFalse(nlu.is_farewell("independent farmer"))


class NamedListFarewellTests(unittest.TestCase):
    def test_kisan_list_is_name_and_tag_only(self):
        uid = "farewell-list-fmt"
        reply = _to_named_kisan_list(uid)
        self.assertEqual(get_session(uid)["phase"], "named_scheme_list")
        rows = [ln for ln in reply.splitlines() if re.match(r"^\d+\. ", ln)]
        self.assertGreaterEqual(len(rows), 2)
        for ln in rows:
            self.assertRegex(ln, LIST_ROW_RE, msg=ln)
            self.assertNotIn(" — ", ln)
        self.assertIn("[Central]", reply)

    def test_mid_list_bye_ends_and_does_not_reprint(self):
        uid = "farewell-bye"
        _to_named_kisan_list(uid)
        reply = handle_message(uid, "bye")
        _assert_ended(self, uid, reply)

    def test_mid_list_tata_ciao_dhanyavad_ola(self):
        for i, text in enumerate(("tata", "ciao", "dhanyavad", "ola")):
            uid = f"farewell-{text}-{i}"
            listing = _to_named_kisan_list(uid)
            self.assertIn("kisan", listing.lower())
            reply = handle_message(uid, text)
            _assert_ended(self, uid, reply)
            self.assertNotIn("scholarship", reply.lower())

    def test_end_chat_button_on_named_list(self):
        uid = "farewell-end-chat"
        _to_named_kisan_list(uid)
        reply = handle_message(uid, "End Chat")
        _assert_ended(self, uid, reply)


class GreetingRestartTests(unittest.TestCase):
    def test_hi_mid_named_list_restarts_not_scheme_number(self):
        uid = "greet-list"
        listing = _to_named_kisan_list(uid)
        self.assertIn("kisan", listing.lower())
        reply = handle_message(uid, "hi")
        session = get_session(uid)
        self.assertEqual(session["phase"], "welcome_language")
        self.assertIsNone(session.get("language"))
        self.assertFalse(session.get("matched_schemes"))
        self.assertIn("language", reply.lower())
        self.assertNotIn("please type a scheme name", reply.lower())
        self.assertNotIn("kisan credit", reply.lower())

    def test_hi_mid_individual_slot_restarts(self):
        uid = "greet-slot"
        _to_individual_collect(uid)
        self.assertEqual(get_session(uid)["phase"], "collect_profile")
        reply = handle_message(uid, "hi")
        session = get_session(uid)
        self.assertEqual(session["phase"], "welcome_language")
        self.assertFalse(session.get("slots"))
        self.assertIn("language", reply.lower())
        self.assertNotIn("age group", reply.lower())

    def test_hi_mid_scheme_detail_restarts(self):
        uid = "greet-detail"
        reset_session(uid)
        handle_message(uid, "English")
        handle_message(uid, "tell me about ujjwala")
        self.assertEqual(get_session(uid)["phase"], "named_scheme")
        reply = handle_message(uid, "hi")
        self.assertEqual(get_session(uid)["phase"], "welcome_language")
        self.assertIn("language", reply.lower())
        self.assertNotIn("what next", reply.lower())


class WhatNextOutboundTests(unittest.TestCase):
    def test_named_detail_is_two_sends(self):
        uid = "what-next-named"
        reset_session(uid)
        handle_message(uid, "English")
        reply = handle_message(uid, "tell me about ujjwala")
        self.assertEqual(get_session(uid)["phase"], "named_scheme")
        self.assertIn("ujjwala", reply.lower())
        self.assertNotIn("what next", reply.lower())
        outbound = get_session(uid).get("outbound") or {}
        self.assertTrue(outbound.get("separate_menu"))
        self.assertFalse(outbound.get("options"))
        sends = outbound_sends(reply, outbound)
        self.assertEqual(len(sends), 2)
        self.assertFalse(sends[0].get("options"))
        self.assertNotIn("What next", sends[0]["body"])
        ids = [row["id"] for row in sends[1].get("options") or []]
        self.assertIn("another", ids)
        self.assertIn("End Chat", ids)
        self.assertIn("What next", sends[1]["body"])

    def test_journey_detail_is_two_sends(self):
        uid = "what-next-j1"
        _to_individual_collect(uid)
        handle_message(uid, "28")
        handle_message(uid, "salaried")
        handle_message(uid, "25000")
        handle_message(uid, "OBC")
        listing = handle_message(uid, "proceed")
        self.assertEqual(get_session(uid)["phase"], "scheme_list")
        self.assertRegex(listing, r"(?m)^1\. .+ \[")
        for ln in listing.splitlines():
            if re.match(r"^\d+\. ", ln):
                self.assertRegex(ln, LIST_ROW_RE, msg=ln)
                self.assertNotIn(" — ", ln)
        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["phase"], "scheme_detail")
        self.assertNotIn("What next", reply)
        outbound = get_session(uid).get("outbound") or {}
        self.assertTrue(outbound.get("separate_menu"))
        sends = outbound_sends(reply, outbound)
        self.assertEqual(len(sends), 2)
        ids = [row["id"] for row in sends[1].get("options") or []]
        self.assertIn("End Chat", ids)

        reply = handle_message(uid, "hi")
        self.assertEqual(get_session(uid)["phase"], "welcome_language")
        self.assertIn("language", reply.lower())


class SchemePoolTests(unittest.TestCase):
    def test_maharashtra_library_is_present(self):
        schemes, note = eligibility.load_scheme_pool("Maharashtra")
        self.assertIn("Central + Maharashtra", note)
        self.assertNotIn("no dedicated library", note.lower())
        libs = {s.get("_library") for s in schemes}
        self.assertIn("Maharashtra", libs)
        schemes2, note2 = eligibility.load_scheme_pool("Maharastra")
        self.assertNotIn("no dedicated library", note2.lower())
        self.assertTrue(schemes2)


if __name__ == "__main__":
    unittest.main()
