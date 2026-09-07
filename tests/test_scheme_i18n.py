"""Session-language chrome and display-only scheme translation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from setu import catalog_i18n, category_catalog as cat
from setu import eligibility, i18n, lookup, translate
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent


def _walk_to_menu(uid: str, language: str = "English") -> None:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, language)


def _women_child_q4(uid: str) -> str:
    _walk_to_menu(uid)
    handle_message(uid, "3")
    handle_message(uid, "1")  # Central only
    handle_message(uid, "2")  # Karnataka
    accept_consent(uid)
    handle_message(uid, "5")  # women & child
    handle_message(uid, "1")
    handle_message(uid, "1")
    return handle_message(uid, "1")  # now Q4


class CatalogOverlayTests(unittest.TestCase):
    def test_women_child_pack_has_marathi_and_kannada(self):
        q = cat.PACKS["women_child"]["questions"][-1]
        self.assertEqual(cat.label_of("women_child", "Marathi"), "महिला आणि मूल")
        self.assertEqual(cat.label_of(q, "Marathi"), "सर्वात जास्त काय हवे आहे?")
        self.assertEqual(cat.label_of(q["options"][0], "Marathi"), "रोख मदत")
        self.assertIn("ಮಹಿಳೆ", cat.label_of("women_child", "Kannada"))
        self.assertIn("ಬೇಕಾಗಿರುವುದು", cat.label_of(q, "Kannada"))
        self.assertEqual(cat.label_of(q, "English"), "What is needed most?")
        self.assertEqual(cat.label_of(q, "Hindi"), "सबसे ज़्यादा क्या चाहिए?")

    def test_overlay_covers_question_and_option_english(self):
        missing = []
        skip = {
            "English",
            "हिंदी",
            "ಕನ್ನಡ",
            "मराठी",
            "SC",
            "ST",
            "OBC",
            "BPL",
            "APL",
            "AAY",
            "40–59",
            "60–79",
            "80+",
            "40–74%",
            "SC / ST",
            "AAY / BPL",
        }
        for pack in cat.PACKS.values():
            show = (pack.get("show_hint") or {}).get("English")
            if show and show not in skip and catalog_i18n.overlay_label(show, "Marathi") is None:
                missing.append(show)
            for q in pack.get("questions") or []:
                en = q.get("English")
                if en not in skip and catalog_i18n.overlay_label(en, "Marathi") is None:
                    missing.append(en)
                for opt in q.get("options") or []:
                    oen = opt.get("English")
                    if oen not in skip and catalog_i18n.overlay_label(oen, "Marathi") is None:
                        missing.append(oen)
        self.assertEqual(missing, [])


class FormatterChromeTests(unittest.TestCase):
    def setUp(self):
        translate.clear_cache()

    def test_scheme_list_chrome_follows_session_language_without_llm(self):
        scheme = {
            "SN": "1",
            "Scheme Name": "Sukanya Samriddhi Yojana",
            "_library": "Central",
            "Benefit": "High-interest small savings account for the girl child",
        }
        listing = eligibility.format_scheme_list(
            [scheme],
            scope_note="Matching Central + Karnataka schemes.",
            intro=i18n.t("cat_results_intro", "Marathi"),
            footer=i18n.t("cat_results_footer", "Marathi"),
            language="Marathi",
        )
        self.assertIn("केंद्र", listing)
        self.assertIn("कर्नाटक", listing)
        self.assertIn("या योजना उपयुक्त ठरू शकतात", listing)
        self.assertIn("क्रमांक किंवा योजनेचे नाव लिहा", listing)
        self.assertIn("Sukanya Samriddhi Yojana", listing)
        self.assertNotIn("High-interest small savings account", listing)
        self.assertNotIn(" — ", listing.split("Sukanya")[1].split("\n")[0] if "Sukanya" in listing else "")
        self.assertRegex(listing, r"(?m)^1\. Sukanya Samriddhi Yojana \[केंद्र\]$")
        self.assertNotIn("These schemes may be relevant", listing)
        self.assertNotIn("Matching Central + Karnataka", listing)

    def test_scheme_detail_labels_follow_language_body_stays_english_without_llm(self):
        scheme = {
            "SN": "1",
            "Scheme Name": "Sukanya Samriddhi Yojana",
            "_library": "Central",
            "Category": "Women / Girl child savings",
            "Benefit": "High-interest small savings account",
            "Age Criteria": "Girl child below 10 years",
            "Income Criteria": "No income cap",
            "Gender / Category Criteria": "Girl child",
            "Other Key Eligibility Criteria": "Account by parent/guardian",
            "Beneficiary Count — Source Note": "https://example.gov.in/",
        }
        card = eligibility.format_scheme_detail(scheme, language="Hindi")
        self.assertIn("श्रेणी:", card)
        self.assertIn("लाभ:", card)
        self.assertIn("आयु:", card)
        self.assertIn("High-interest small savings account", card)
        self.assertIn("Sukanya Samriddhi Yojana", card)
        self.assertNotIn("Category:", card)
        self.assertNotIn("Benefit:", card)

    def test_named_scheme_labels_follow_language(self):
        hits = lookup.search_schemes("ujjwala")
        self.assertTrue(hits)
        card = lookup.format_named_scheme_detail(hits[0], "What next?", language="Marathi")
        self.assertTrue(card.startswith("1. नाव:"))
        self.assertIn("2. माहिती:", card)
        self.assertIn("Ujjwala", hits[0]["Scheme Name"])
        self.assertIn("Ujjwala", card)
        self.assertNotIn("1. Name:", card)
        self.assertNotIn("2. About:", card)
        self.assertRegex(card, r"(?m)^1\. ")

    def test_english_formatters_keep_legacy_chrome(self):
        scheme = {
            "SN": "1",
            "Scheme Name": "Test Scheme",
            "_library": "Central",
            "Benefit": "Cash support",
            "Category": "Welfare",
            "Age Criteria": "18+",
            "Income Criteria": "BPL",
            "Gender / Category Criteria": "All",
            "Other Key Eligibility Criteria": "Aadhaar",
        }
        listing = eligibility.format_scheme_list([scheme])
        self.assertIn("Based on what you shared", listing)
        self.assertIn("[Central]", listing)
        detail = eligibility.format_scheme_detail(scheme)
        self.assertIn("Category:", detail)
        self.assertIn("Benefit:", detail)


class LlmTranslationTests(unittest.TestCase):
    def setUp(self):
        translate.clear_cache()

    def test_mocked_llm_translates_scheme_body(self):
        scheme = {
            "SN": "1",
            "Scheme Name": "Sukanya Samriddhi Yojana",
            "_library": "Central",
            "Benefit": "High-interest small savings account for the girl child",
            "Category": "Women / Girl child savings",
            "Age Criteria": "Girl child below 10 years",
            "Income Criteria": "No income cap",
            "Gender / Category Criteria": "Girl child",
            "Other Key Eligibility Criteria": "Account by parent/guardian",
        }

        def fake_json(_system, user, temperature=0.1):
            payload = __import__("json").loads(user)
            texts = payload.get("texts") or []
            mapping = {src: f"मराठी:{src[:24]}" for src in texts}
            return {"translations": mapping}

        with (
            patch("setu.translate.llm.llm_configured", return_value=True),
            patch("setu.translate.llm.chat_json", side_effect=fake_json),
        ):
            listing = eligibility.format_scheme_list([scheme], language="Marathi")
            detail = eligibility.format_scheme_detail(scheme, language="Marathi")
        self.assertNotIn("मराठी:High-interest small", listing)
        self.assertIn("Sukanya Samriddhi Yojana", listing)
        self.assertRegex(listing, r"(?m)^1\. Sukanya Samriddhi Yojana \[केंद्र\]$")
        self.assertIn("मराठी:High-interest small", detail)
        self.assertIn("लाभ:", detail)
        self.assertRegex(listing, r"(?m)^1\. ")


class MidFlowLanguageSwitchTests(unittest.TestCase):
    def test_shift_to_marathi_localizes_women_child_q4_and_results(self):
        uid = "i18n-mr-q4"
        q4 = _women_child_q4(uid)
        self.assertIn("What is needed most?", q4)
        self.assertEqual(get_session(uid)["phase"], "cat_collect")

        reply = handle_message(uid, "shift to marathi")
        self.assertEqual(get_session(uid)["language"], "Marathi")
        self.assertEqual(get_session(uid)["phase"], "cat_collect")
        self.assertIn("ठीक आहे", reply)
        self.assertIn("महिला आणि मूल", reply)
        self.assertIn("सर्वात जास्त काय हवे आहे?", reply)
        self.assertIn("रोख मदत", reply)
        self.assertIn("1.", reply)
        self.assertNotIn("What is needed most?", reply)
        self.assertNotIn("Cash support", reply)

        reply = handle_message(uid, "4")
        self.assertEqual(get_session(uid)["phase"], "cat_results")
        self.assertIn("या योजना उपयुक्त ठरू शकतात", reply)
        self.assertIn("क्रमांक किंवा योजनेचे नाव लिहा", reply)
        self.assertIn("कर्नाटक", reply)
        self.assertRegex(reply, r"(?m)^1\. ")
        self.assertNotIn("These schemes may be relevant", reply)
        self.assertNotIn("Matching Central", reply)
        self.assertNotIn("Matching Karnataka schemes.", reply)
        self.assertTrue(get_session(uid).get("matched_schemes"))
        first = get_session(uid)["matched_schemes"][0]
        self.assertIn(first["Scheme Name"], reply)

        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["phase"], "cat_detail")
        self.assertIn("लाभ:", reply)
        self.assertNotIn("Benefit:", reply)
        self.assertIn(first["Scheme Name"], reply)

    def test_hindi_and_kannada_category_questions(self):
        uid = "i18n-hi"
        _walk_to_menu(uid, "Hindi")
        handle_message(uid, "3")
        handle_message(uid, "2")
        handle_message(uid, "2")
        accept_consent(uid)
        reply = handle_message(uid, "5")
        self.assertEqual(get_session(uid)["language"], "Hindi")
        self.assertIn("महिला और बच्चा", reply)
        self.assertIn("यह किसके लिए है?", reply)
        self.assertIn("गर्भवती", reply)

        uid = "i18n-kn"
        _walk_to_menu(uid)
        handle_message(uid, "3")
        handle_message(uid, "1")
        handle_message(uid, "2")
        accept_consent(uid)
        handle_message(uid, "5")
        reply = handle_message(uid, "shift to kannada")
        self.assertEqual(get_session(uid)["language"], "Kannada")
        self.assertRegex(reply, r"[\u0C80-\u0CFF]")
        self.assertIn("ಮಹಿಳೆ", reply)
        self.assertNotIn("Who is this for?", reply)

    def test_named_scheme_after_marathi_keeps_official_name(self):
        uid = "i18n-named-mr"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "marathi")
        reply = handle_message(uid, "Tell me about ujjwala yojana")
        self.assertEqual(get_session(uid)["phase"], "named_scheme")
        self.assertIn("नाव:", reply)
        self.assertIn("Ujjwala", reply)
        self.assertNotIn("1. Name:", reply)
        self.assertRegex(reply, r"(?m)^1\. ")

    def test_journeys_still_work_after_localization(self):
        uid = "i18n-j1"
        _walk_to_menu(uid)
        reply = handle_message(uid, "1")
        self.assertEqual(get_session(uid)["journey_id"], "journey_1")
        self.assertIn("state", reply.lower())
        handle_message(uid, "Karnataka")
        accept_consent(uid)
        for msg in ("28", "salaried", "25000", "OBC"):
            handle_message(uid, msg)
        reply = handle_message(uid, "proceed")
        self.assertEqual(get_session(uid)["phase"], "scheme_list")
        self.assertRegex(reply, r"(?m)^1\. ")
        self.assertRegex(reply, r"\[(Central|Karnataka|केंद्र|कर्नाटक)\]")


if __name__ == "__main__":
    unittest.main()
