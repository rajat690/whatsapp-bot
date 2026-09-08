"""Strict numbered scheme lists + interactive scheme rows."""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from setu import eligibility, i18n
from setu.interactive import (
    LIST_ROW_TITLE_MAX,
    MAX_LIST_ROWS,
    build_interactive_payload,
    finalize,
    options_for_session,
    parse_inbound_message,
    scheme_option_rows,
    spec_mode,
)
from setu.nlu import match_scheme_choice
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent

LIST_ROW_RE = re.compile(r"^\d+\. .+ \[.+\]$")
LLM_BULLET_DUMP = (
    "आपके लिए कुछ उपयोगी योजनाएँ हैं।\n"
    "• Karnataka Rajyog Yojana\n"
    "• MGNREGA\n"
    "• Karnataka State Pension Scheme"
)


def _to_scheme_list(uid: str) -> str:
    reset_session(uid)
    handle_message(uid, "hi")
    handle_message(uid, "English")
    handle_message(uid, "individual schemes")
    handle_message(uid, "Karnataka")
    accept_consent(uid)
    for msg in ("28", "Female", "salaried", "25000"):
        handle_message(uid, msg)
    return handle_message(uid, "proceed")


def _fake_schemes(n: int) -> list[dict]:
    return [
        {
            "SN": str(i),
            "Scheme Name": f"Very Long Government Scheme Name Number {i} For Farmers",
            "_library": "Karnataka" if i % 2 else "Central",
            "Benefit": "Should never appear on a list row",
        }
        for i in range(1, n + 1)
    ]


class NumberedSchemeLinesTests(unittest.TestCase):
    def test_numbered_scheme_lines_are_name_and_tag_only(self):
        schemes = [
            {
                "SN": "9",
                "Scheme Name": "D. Devaraj Urs Self Employment Loan Schemes",
                "_library": "Karnataka",
                "Benefit": "Loan support for self employment",
            },
            {
                "SN": "1",
                "Scheme Name": "MGNREGA",
                "_library": "Central",
                "Benefit": "Wage employment",
            },
        ]
        lines = eligibility.numbered_scheme_lines(schemes, "Hindi")
        self.assertEqual(
            lines,
            [
                "1. D. Devaraj Urs Self Employment Loan Schemes [कर्नाटक]",
                "2. MGNREGA [केंद्र]",
            ],
        )
        self.assertNotIn("Loan support", "\n".join(lines))
        self.assertNotIn(" — ", lines[0])
        listing = eligibility.format_scheme_list(schemes, language="Hindi")
        self.assertRegex(listing, r"(?m)^1\. D\. Devaraj Urs Self Employment Loan Schemes \[कर्नाटक\]$")
        self.assertNotRegex(listing, r"(?m)^• ")


class MatchResultsNoBulletDumpTests(unittest.TestCase):
    def test_journey_match_outbound_has_no_bullet_list(self):
        uid = "sl-j1-bullets"
        reply = _to_scheme_list(uid)
        session = get_session(uid)
        self.assertEqual(session["phase"], "scheme_list")
        self.assertTrue(session.get("matched_schemes"))
        self.assertFalse(eligibility.has_bullet_scheme_list(reply))
        self.assertNotRegex(reply, r"(?m)^[ \t]*[•●▪‣*]\s+")
        numbered = [ln for ln in reply.splitlines() if LIST_ROW_RE.match(ln)]
        self.assertEqual(len(numbered), len(session["matched_schemes"]))
        self.assertGreaterEqual(len(numbered), 1)
        outbound = session.get("outbound") or {}
        self.assertEqual(outbound.get("body"), reply)
        self.assertFalse(eligibility.has_bullet_scheme_list(outbound.get("body")))

    def test_llm_bullet_intro_is_not_prepended(self):
        uid = "sl-j1-llm-dump"

        def boom_text(*_a, **_k):
            return LLM_BULLET_DUMP

        with (
            patch("setu.llm.llm_configured", return_value=True),
            patch("setu.orchestrator.llm.llm_configured", return_value=True),
            patch("setu.llm.chat_text", side_effect=boom_text),
            patch("setu.orchestrator.llm.chat_text", side_effect=boom_text),
            patch("setu.llm.chat_json", return_value=None),
            patch("setu.orchestrator.llm.chat_json", return_value=None),
        ):
            reply = _to_scheme_list(uid)
        self.assertNotIn("•", reply)
        self.assertNotIn("Rajyog", reply)
        self.assertNotIn("आपके लिए कुछ उपयोगी योजनाएँ हैं", reply)
        self.assertRegex(reply, r"(?m)^1\. .+ \[")
        numbered = [ln for ln in reply.splitlines() if LIST_ROW_RE.match(ln)]
        self.assertEqual(len(numbered), len(get_session(uid)["matched_schemes"]))

    def test_finalize_strips_duplicate_bullet_dump(self):
        schemes = _fake_schemes(3)
        listing = eligibility.format_scheme_list(
            schemes,
            scope_note="Matching Central + Karnataka schemes.",
            language="Hindi",
        )
        dumped = LLM_BULLET_DUMP + "\n\n" + listing
        session = {
            "phase": "scheme_list",
            "language": "Hindi",
            "matched_schemes": schemes,
        }
        body = finalize(session, dumped)
        self.assertNotIn("•", body)
        self.assertNotIn("Rajyog", body)
        numbered = [ln for ln in body.splitlines() if LIST_ROW_RE.match(ln)]
        self.assertEqual(len(numbered), 3)
        self.assertIn("ये योजनाएँ काम आ सकती हैं", body)


class SchemeInteractiveOptionsTests(unittest.TestCase):
    def test_scheme_list_options_are_1_through_n(self):
        uid = "sl-opts-j1"
        reply = _to_scheme_list(uid)
        session = get_session(uid)
        schemes = session["matched_schemes"]
        pairs = options_for_session(session)
        ids = [oid for oid, _title in pairs]
        expected = [str(i) for i in range(1, min(len(schemes), MAX_LIST_ROWS) + 1)]
        self.assertEqual(ids, expected)
        outbound_ids = [row["id"] for row in (session.get("outbound") or {}).get("options") or []]
        self.assertEqual(outbound_ids, expected)
        self.assertIn("Choose scheme", (session.get("outbound") or {}).get("list_button", ""))
        for i, (_oid, title) in enumerate(pairs, 1):
            self.assertTrue(title.startswith(f"{i}. "))
            self.assertLessEqual(len(title), LIST_ROW_TITLE_MAX)
        numbered = [ln for ln in reply.splitlines() if LIST_ROW_RE.match(ln)]
        self.assertEqual(len(numbered), len(schemes))
        self.assertNotRegex(reply, r"(?m)^\d+\. \d+\. ")

    def test_tapping_scheme_row_opens_detail(self):
        uid = "sl-tap-j1"
        _to_scheme_list(uid)
        session = get_session(uid)
        schemes = session["matched_schemes"]
        self.assertGreaterEqual(len(schemes), 2)
        inbound = parse_inbound_message(
            {
                "type": "interactive",
                "interactive": {
                    "type": "list_reply",
                    "list_reply": {
                        "id": "2",
                        "title": "2. Truncated…",
                    },
                },
            }
        )
        self.assertEqual(inbound, "2")
        reply = handle_message(uid, inbound)
        session = get_session(uid)
        self.assertEqual(session["phase"], "scheme_detail")
        self.assertEqual(str(session.get("selected_scheme_sn")), str(schemes[1].get("SN")))
        self.assertIn(schemes[1]["Scheme Name"], reply)
        self.assertIn("Benefit", reply)
        outbound = session.get("outbound") or {}
        self.assertTrue(outbound.get("separate_menu"))

    def test_match_scheme_choice_reads_truncated_title(self):
        schemes = _fake_schemes(3)
        chosen = match_scheme_choice("1. Very Long Government Scheme Name…", schemes)
        self.assertEqual(chosen, schemes[0])

    def test_interactive_rows_cap_at_ten_text_keeps_all(self):
        schemes = _fake_schemes(12)
        session = {
            "phase": "scheme_list",
            "language": "English",
            "matched_schemes": schemes,
        }
        listing = eligibility.format_scheme_list(schemes, language="English")
        body = finalize(session, listing)
        numbered = [ln for ln in body.splitlines() if LIST_ROW_RE.match(ln)]
        self.assertEqual(len(numbered), 12)
        rows = (session.get("outbound") or {}).get("options") or []
        self.assertEqual(len(rows), 10)
        self.assertEqual([row["id"] for row in rows], [str(i) for i in range(1, 11)])
        self.assertEqual(spec_mode(rows), "list")
        payload = build_interactive_payload("911", body, rows, list_button="Choose scheme")
        self.assertEqual(payload["interactive"]["type"], "list")
        self.assertEqual(len(payload["interactive"]["action"]["sections"][0]["rows"]), 10)
        self.assertEqual(payload["interactive"]["action"]["button"], "Choose scheme")
        self.assertTrue(payload["interactive"]["action"]["sections"][0]["rows"][0].get("description"))

    def test_three_or_fewer_use_reply_buttons(self):
        schemes = _fake_schemes(2)
        rows = scheme_option_rows({"language": "English"}, schemes)
        self.assertEqual(spec_mode(rows), "buttons")
        payload = build_interactive_payload("911", "Pick", rows)
        self.assertEqual(payload["interactive"]["type"], "button")
        self.assertEqual(len(payload["interactive"]["action"]["buttons"]), 2)

    def test_cat_results_and_named_list_expose_scheme_ids(self):
        uid = "sl-cat"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        handle_message(uid, "3")
        handle_message(uid, "1")
        handle_message(uid, "2")
        accept_consent(uid)
        handle_message(uid, "1")  # education
        for _ in range(4):
            handle_message(uid, "1")
        session = get_session(uid)
        self.assertEqual(session["phase"], "cat_results")
        ids = [row["id"] for row in (session.get("outbound") or {}).get("options") or []]
        n = min(len(session["matched_schemes"]), MAX_LIST_ROWS)
        self.assertEqual(ids, [str(i) for i in range(1, n + 1)])
        self.assertNotRegex((session.get("outbound") or {}).get("body") or "", r"(?m)^[ \t]*[•●]\s+")

        uid = "sl-named"
        reset_session(uid)
        handle_message(uid, "English")
        reply = handle_message(uid, "kisan")
        session = get_session(uid)
        if session["phase"] == "named_scheme_list":
            ids = [row["id"] for row in (session.get("outbound") or {}).get("options") or []]
            n = min(len(session["matched_schemes"]), MAX_LIST_ROWS)
            self.assertEqual(ids, [str(i) for i in range(1, n + 1)])
            self.assertRegex(reply, r"(?m)^1\. .+ \[")
            self.assertNotIn("•", reply)
            first = session["matched_schemes"][0]
            detail = handle_message(uid, "1")
            self.assertEqual(get_session(uid)["phase"], "named_scheme")
            self.assertIn(first["Scheme Name"].split()[0], detail)
            self.assertNotIn("What next", detail)


class LocalizedChooseSchemeTests(unittest.TestCase):
    def test_choose_scheme_button_follows_language(self):
        self.assertEqual(i18n.t("interactive_choose_scheme", "English"), "Choose scheme")
        self.assertIn("योजना", i18n.t("interactive_choose_scheme", "Hindi"))
        self.assertLessEqual(len(i18n.t("interactive_choose_scheme", "English")), 20)
        self.assertLessEqual(len(i18n.t("interactive_choose_scheme", "Hindi")), 20)


if __name__ == "__main__":
    unittest.main()
