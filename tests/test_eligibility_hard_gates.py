"""Hard eligibility gates + one-shot free-text profile extraction."""

from __future__ import annotations

import unittest

from setu import conversation_engine as engine
from setu import eligibility, nlu, profile_intent
from setu.orchestrator import handle_message
from setu.session import get_session, reset_session
from tests.helpers import accept_consent

QUERY_54 = "i am a muslim age 54 and work as daily labourer. what schemes will i get?"

PM_SYM = "pradhan mantri shram yogi maandhan"
APY = "atal pension yojana"
IGNOAPS = "ignoaps"
ESHRAM = "e-shram"


def _names(schemes: list[dict]) -> list[str]:
    return [(s.get("Scheme Name") or "").lower() for s in schemes]


def _has(schemes: list[dict], needle: str) -> bool:
    return any(needle in n for n in _names(schemes))


class ExtractExactAgeTests(unittest.TestCase):
    def test_age_54_from_free_text(self):
        self.assertEqual(nlu.detect_age_years("age 54"), 54)
        self.assertEqual(nlu.detect_age_years("I am 54"), 54)
        self.assertEqual(nlu.detect_age_years("i am a muslim age 54 and work as daily labourer"), 54)
        self.assertEqual(nlu.detect_age(QUERY_54), "18–59")

    def test_extract_slots_keeps_age_and_minority(self):
        slots = nlu.extract_slots(QUERY_54, engine.load_journey("journey_1")["slots"])
        self.assertEqual(slots.get("age"), "54")
        self.assertEqual(slots.get("age_group"), "18–59")
        self.assertEqual(slots.get("occupation"), "Labourer")
        self.assertEqual(slots.get("social_category"), "Minority")

    def test_facts_from_signals_store_exact_age(self):
        facts = engine.facts_from_signals(QUERY_54, profile_intent.extract_signals(QUERY_54))
        self.assertEqual(facts.get("age"), "54")
        self.assertEqual(facts.get("occupation"), "Labourer")
        self.assertEqual(facts.get("social_category"), "Minority")
        self.assertTrue(engine.has_enough_match_profile(facts))

    def test_bare_number_is_not_age_unless_asking(self):
        self.assertIsNone(nlu.detect_age_years("family of 5"))
        self.assertEqual(nlu.detect_age_years("28", prefer=True), 28)


class AgeWindowParseTests(unittest.TestCase):
    def test_entry_18_40_ignores_pension_from_60(self):
        win = eligibility.parse_age_window("Entry 18–40 years; pension from 60")
        self.assertEqual(win["min"], 18)
        self.assertEqual(win["max"], 40)

    def test_range_and_senior(self):
        self.assertEqual(eligibility.parse_age_window("18–70 years")["max"], 70)
        self.assertEqual(eligibility.parse_age_window("Below Poverty Line persons aged 60+")["min"], 60)
        self.assertEqual(eligibility.parse_age_window("Unorganised workers typically 16–59 at registration")["max"], 59)


class MatchHardAgeTests(unittest.TestCase):
    def test_age_54_labourer_minority_excludes_pm_sym(self):
        slots = {
            "age": "54",
            "age_group": "18–59",
            "occupation": "Labourer",
            "social_category": "Minority",
            "state": "Karnataka",
        }
        matched, _ = eligibility.match_schemes(slots)
        self.assertFalse(_has(matched, PM_SYM), _names(matched))
        self.assertFalse(_has(matched, APY), _names(matched))
        # Other labour / registry schemes in the 16–59 window may still appear.
        if matched:
            self.assertFalse(any("18–40" in (s.get("Age Criteria") or "") and "entry" in (s.get("Age Criteria") or "").lower() for s in matched if PM_SYM in (s.get("Scheme Name") or "").lower()))

    def test_age_54_excludes_all_entry_max_40(self):
        slots = {"age": "54", "age_group": "18–59", "occupation": "Labourer"}
        matched, _ = eligibility.match_schemes(slots, limit=20)
        for scheme in matched:
            win = eligibility.parse_age_window(scheme.get("Age Criteria"))
            if win and win.get("max") is not None and win["max"] <= 40:
                self.fail(f"{scheme.get('Scheme Name')} max={win['max']} should be excluded")

    def test_age_30_labourer_may_include_pm_sym(self):
        slots = {
            "age": "30",
            "age_group": "18–59",
            "occupation": "Labourer",
            "household_income": "Up to ₹10,000",
        }
        matched, _ = eligibility.match_schemes(slots, limit=12)
        self.assertTrue(_has(matched, PM_SYM), _names(matched))

    def test_age_65_excludes_18_40_allows_60_plus(self):
        slots = {"age": "65", "age_group": "60+", "occupation": "Labourer"}
        matched, _ = eligibility.match_schemes(slots, limit=16)
        self.assertFalse(_has(matched, PM_SYM), _names(matched))
        self.assertTrue(_has(matched, IGNOAPS) or any("60" in (s.get("Age Criteria") or "") for s in matched), _names(matched))
        for scheme in matched:
            win = eligibility.parse_age_window(scheme.get("Age Criteria"))
            if not win:
                continue
            if win.get("max") is not None and win["max"] <= 40:
                self.fail(f"{scheme.get('Scheme Name')} entry max {win['max']} shown to age 65")

    def test_age_group_only_18_59_does_not_drop_18_40(self):
        slots = {"age_group": "18–59", "occupation": "Labourer"}
        matched, _ = eligibility.match_schemes(slots, limit=12)
        self.assertTrue(_has(matched, PM_SYM), _names(matched))

    def test_age_group_60_plus_drops_entry_40(self):
        slots = {"age_group": "60+", "occupation": "Retired"}
        matched, _ = eligibility.match_schemes(slots, limit=16)
        self.assertFalse(_has(matched, PM_SYM), _names(matched))


class IncomeGenderHardFailTests(unittest.TestCase):
    def test_high_income_excludes_pm_sym_ceiling(self):
        slots = {
            "age": "30",
            "age_group": "18–59",
            "occupation": "Labourer",
            "household_income": "Above ₹50,000",
        }
        matched, _ = eligibility.match_schemes(slots, limit=16)
        self.assertFalse(_has(matched, PM_SYM), _names(matched))

    def test_male_excluded_from_women_only_ujjwala(self):
        scheme = {
            "Scheme Name": "Pradhan Mantri Ujjwala Yojana (PMUY)",
            "Category": "Energy / Clean cooking fuel",
            "Age Criteria": "Adult woman applicant",
            "Income Criteria": "Targeted to women from poor households",
            "Gender / Category Criteria": "Woman of the household as connection holder; priority categories as notified",
            "Other Key Eligibility Criteria": "No existing LPG connection",
            "Benefit": "LPG connection",
        }
        self.assertTrue(
            eligibility.is_hard_ineligible(scheme, {"gender": "Male", "age": "30", "age_group": "18–59"})
        )
        self.assertFalse(
            eligibility.is_hard_ineligible(scheme, {"gender": "Female", "age": "30", "age_group": "18–59"})
        )

    def test_labourer_boost_does_not_salvage_age_fail(self):
        scheme = {
            "Scheme Name": "Pradhan Mantri Shram Yogi Maandhan (PM-SYM)",
            "Category": "Social security / Unorganised worker pension",
            "Age Criteria": "Entry 18–40 years; pension from 60",
            "Income Criteria": "Monthly income ≤ ₹15,000 and not an income-tax payer",
            "Gender / Category Criteria": "Unorganised sector workers; no gender restriction",
            "Other Key Eligibility Criteria": "",
            "Benefit": "Pension",
        }
        score, _ = eligibility._score_scheme(
            scheme, {"age": "54", "age_group": "18–59", "occupation": "Labourer"}
        )
        self.assertEqual(score, 0)
        self.assertTrue(eligibility.is_hard_ineligible(scheme, {"age": "54", "occupation": "Labourer"}))


class MinorityBoostTests(unittest.TestCase):
    def test_minority_scheme_outranks_generic_when_signal_set(self):
        minority = {
            "Scheme Name": "Post-Matric Scholarship for Minorities",
            "Category": "Education / Minority welfare",
            "Age Criteria": "Adult",
            "Income Criteria": "No income restriction",
            "Gender / Category Criteria": "Minority communities; no gender restriction",
            "Other Key Eligibility Criteria": "Minority certificate",
            "Benefit": "Scholarship",
        }
        generic = {
            "Scheme Name": "Generic Worker Registry",
            "Category": "Social security / Worker registry",
            "Age Criteria": "Adult",
            "Income Criteria": "No income restriction",
            "Gender / Category Criteria": "Unorganised workers; no gender restriction",
            "Other Key Eligibility Criteria": "",
            "Benefit": "UAN",
        }
        slots = {
            "age": "30",
            "age_group": "18–59",
            "occupation": "Student",
            "social_category": "Minority",
        }
        # Adult + scholarship + student occupation: minority scheme is not student-hard-failed
        # because occupation is Student. Compare scores.
        s_min, reasons = eligibility._score_scheme(minority, slots)
        s_gen, _ = eligibility._score_scheme(generic, slots)
        self.assertIn("Minority", reasons)
        self.assertGreater(s_min, s_gen)

    def test_hard_age_wins_over_minority_boost(self):
        scheme = {
            "Scheme Name": "Minority Youth Pension",
            "Category": "Social security / Minority pension",
            "Age Criteria": "Entry 18–40 years; pension from 60",
            "Income Criteria": "No income restriction",
            "Gender / Category Criteria": "Minority communities; no gender restriction",
            "Other Key Eligibility Criteria": "",
            "Benefit": "Pension",
        }
        self.assertTrue(
            eligibility.is_hard_ineligible(
                scheme, {"age": "54", "occupation": "Labourer", "social_category": "Minority"}
            )
        )


class CategoryPathHardAgeTests(unittest.TestCase):
    def test_labour_pack_excludes_pm_sym_for_age_54(self):
        matched, _ = eligibility.match_category_schemes(
            {"age": "54", "age_group": "18–59", "occupation": "Labourer", "work_status": "wage"},
            "labour_bocw",
            scope="central",
            limit=12,
        )
        self.assertFalse(_has(matched, PM_SYM), _names(matched))


class OneshotProfileFlowTests(unittest.TestCase):
    def test_muslim_age_54_labourer_skips_to_list_without_pm_sym(self):
        uid = "oneshot-54"
        reset_session(uid)
        handle_message(uid, "hi")
        handle_message(uid, "English")
        reply = handle_message(uid, QUERY_54)
        session = get_session(uid)
        self.assertEqual(session.get("known_profile", {}).get("age"), "54")
        self.assertEqual(session.get("known_profile", {}).get("occupation"), "Labourer")
        self.assertEqual(session.get("known_profile", {}).get("social_category"), "Minority")
        self.assertTrue(session.get("oneshot_profile"))
        # State is still required (pre-consent).
        self.assertIn("state", reply.lower())
        handle_message(uid, "Karnataka")
        accept_consent(uid)
        session = get_session(uid)
        self.assertEqual(session["phase"], "scheme_list")
        names = _names(session.get("matched_schemes") or [])
        self.assertFalse(any(PM_SYM in n for n in names), names)
        reply = handle_message(uid, "1") if session.get("matched_schemes") else ""
        if reply:
            self.assertNotIn("What next?", reply)
            # Detail is a separate message; What-next is attached as outbound options.
            outbound = session.get("outbound") or {}
            self.assertTrue(outbound.get("options") or session.get("phase") == "scheme_detail")


if __name__ == "__main__":
    unittest.main()
