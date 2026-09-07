"""Isolated schemes_by_category_v1 catalog: hubs, ≤4-question packs, matching keywords.

Individual (journey_1) and Family (journey_2) catalogs are not used here.
Kannada / Marathi labels fall back to English when a translation is missing.
"""

from __future__ import annotations

from typing import Any

WORKFLOW_ID = "schemes_by_category_v1"
PATH_FLAG = "category"

# Hub 1 — WhatsApp list max 10 rows
HUB_1: list[str] = [
    "education",
    "scholarship",
    "housing",
    "pension",
    "women_child",
    "livelihood",
    "health",
    "agriculture",
    "disability",
    "more",
]

# Hub 2 — after More
HUB_2: list[str] = [
    "food_ration",
    "labour_bocw",
    "family_who",
    "back",
]

NAV_IDS = {"more", "back"}
SPECIAL_IDS = {"family_who"}

LANGUAGES: list[dict[str, str]] = [
    {"id": "English", "English": "English", "Hindi": "English"},
    {"id": "Hindi", "English": "हिंदी", "Hindi": "हिंदी"},
    {"id": "Kannada", "English": "ಕನ್ನಡ", "Hindi": "ಕನ್ನಡ"},
    {"id": "Marathi", "English": "मराठी", "Hindi": "मराठी"},
]

STATE_SCOPES: list[dict[str, str]] = [
    {
        "id": "central",
        "English": "Central only",
        "Hindi": "केवल केंद्र",
    },
    {
        "id": "karnataka",
        "English": "Karnataka",
        "Hindi": "कर्नाटक",
    },
    {
        "id": "maharashtra",
        "English": "Maharashtra",
        "Hindi": "महाराष्ट्र",
    },
    {
        "id": "state_central",
        "English": "State + Central",
        "Hindi": "राज्य + केंद्र",
    },
]

STATE_PLUS_CENTRAL: list[dict[str, str]] = [
    {
        "id": "karnataka",
        "English": "Karnataka + Central",
        "Hindi": "कर्नाटक + केंद्र",
    },
    {
        "id": "maharashtra",
        "English": "Maharashtra + Central",
        "Hindi": "महाराष्ट्र + केंद्र",
    },
]

HUB_LABELS: dict[str, dict[str, str]] = {
    "education": {"English": "Education", "Hindi": "शिक्षा"},
    "scholarship": {"English": "Scholarship", "Hindi": "छात्रवृत्ति"},
    "housing": {"English": "Housing", "Hindi": "आवास"},
    "pension": {"English": "Pension", "Hindi": "पेंशन"},
    "women_child": {"English": "Women & child", "Hindi": "महिला और बच्चा"},
    "livelihood": {"English": "Livelihood / MSME", "Hindi": "आजीविका / MSME"},
    "health": {"English": "Health", "Hindi": "स्वास्थ्य"},
    "agriculture": {"English": "Agriculture", "Hindi": "कृषि"},
    "disability": {"English": "Disability", "Hindi": "दिव्यांगजन"},
    "more": {"English": "More", "Hindi": "और श्रेणियाँ"},
    "food_ration": {"English": "Food & ration", "Hindi": "राशन / खाद्य"},
    "labour_bocw": {"English": "Labour / BOCW", "Hindi": "श्रम / BOCW"},
    "family_who": {"English": "Find by who", "Hindi": "किसके लिए खोजें"},
    "back": {"English": "Back", "Hindi": "वापस"},
}

WHO_FIRST: list[dict[str, Any]] = [
    {
        "id": "pregnant",
        "route": "women_child",
        "preset": {"who": "pregnant_lactating"},
        "English": "Pregnant / lactating",
        "Hindi": "गर्भवती / स्तनपान",
    },
    {
        "id": "disabled",
        "route": "disability",
        "preset": {"disability": "Yes"},
        "pension_slice": True,
        "English": "Person with disability",
        "Hindi": "दिव्यांग व्यक्ति",
    },
    {
        "id": "senior",
        "route": "pension",
        "preset": {"pension_type": "old_age", "age_band": "60_79"},
        "English": "Senior (60+)",
        "Hindi": "वरिष्ठ नागरिक (60+)",
    },
    {
        "id": "girl_child",
        "route": "women_child",
        "preset": {"who": "girl_child"},
        "English": "Girl child (under 18)",
        "Hindi": "बालिका (18 से कम)",
    },
    {
        "id": "child",
        "route": "education",
        "preset": {},
        "English": "Child / student",
        "Hindi": "बच्चा / विद्यार्थी",
    },
    {
        "id": "farmer",
        "route": "agriculture",
        "preset": {},
        "English": "Farmer",
        "Hindi": "किसान",
    },
    {
        "id": "labour",
        "route": "labour_bocw",
        "preset": {},
        "English": "Construction / labour worker",
        "Hindi": "निर्माण / श्रमिक",
    },
    {
        "id": "adult_woman",
        "route": "women_child",
        "preset": {"who": "adult_woman"},
        "English": "Adult woman",
        "Hindi": "वयस्क महिला",
    },
    {
        "id": "who_back",
        "route": "back",
        "preset": {},
        "English": "Back to categories",
        "Hindi": "श्रेणियों पर वापस",
    },
]


def _opt(oid: str, en: str, hi: str) -> dict[str, str]:
    return {"id": oid, "English": en, "Hindi": hi}


def _q(qid: str, en: str, hi: str, options: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "id": qid,
        "English": en,
        "Hindi": hi,
        "options": options,
    }


# Packs: hard cap of 4 questions after Language + State.
PACKS: dict[str, dict[str, Any]] = {
    "education": {
        "questions": [
            _q(
                "edu_level",
                "What is the education level?",
                "शिक्षा का स्तर क्या है?",
                [
                    _opt("school_1_10", "School (classes 1–10)", "स्कूल (कक्षा 1–10)"),
                    _opt("class_11_12", "Classes 11–12", "कक्षा 11–12"),
                    _opt("ug", "Undergraduate", "स्नातक (UG)"),
                    _opt("pg", "Postgraduate", "स्नातकोत्तर (PG)"),
                    _opt("diploma_iti", "Diploma / ITI", "डिप्लोमा / ITI"),
                    _opt("competitive", "Competitive exam", "प्रतियोगी परीक्षा"),
                    _opt("dropout", "School dropout / left studies", "पढ़ाई छोड़ दी"),
                ],
            ),
            _q(
                "caste",
                "Which social category?",
                "सामाजिक श्रेणी कौन सी है?",
                [
                    _opt("SC", "SC", "SC"),
                    _opt("ST", "ST", "ST"),
                    _opt("OBC", "OBC", "OBC"),
                    _opt("General", "General", "सामान्य"),
                    _opt("Minority", "Minority", "अल्पसंख्यक"),
                ],
            ),
            _q(
                "income_annual",
                "What is the annual household income?",
                "वार्षिक पारिवारिक आय कितनी है?",
                [
                    _opt("lt_1l", "Below ₹1 lakh", "₹1 लाख से कम"),
                    _opt("1_2_5l", "₹1–2.5 lakh", "₹1–2.5 लाख"),
                    _opt("2_5_8l", "₹2.5–8 lakh", "₹2.5–8 लाख"),
                    _opt("above_8l", "Above ₹8 lakh", "₹8 लाख से अधिक"),
                ],
            ),
        ],
        "show_hint": {
            "English": "Looking at fee reimbursement, hostels, mid-day meals, skill+education, and minority/SC-ST education schemes.",
            "Hindi": "शुल्क प्रतिपूर्ति, छात्रावास, मध्याह्न भोजन, कौशल+शिक्षा, और अल्पसंख्यक/SC-ST शिक्षा योजनाएँ देख रहे हैं।",
        },
    },
    "scholarship": {
        "questions": [
            _q(
                "schol_level",
                "Which scholarship level?",
                "छात्रवृत्ति किस स्तर की चाहिए?",
                [
                    _opt("pre_matric", "Pre-matric", "प्री-मैट्रिक"),
                    _opt("class_11_12", "Classes 11–12", "कक्षा 11–12"),
                    _opt("ug", "Undergraduate", "स्नातक (UG)"),
                    _opt("pg", "Postgraduate", "स्नातकोत्तर (PG)"),
                    _opt("professional", "Professional / technical", "व्यावसायिक / तकनीकी"),
                    _opt("overseas", "Overseas", "विदेश अध्ययन"),
                ],
            ),
            _q(
                "caste",
                "Which social category?",
                "सामाजिक श्रेणी कौन सी है?",
                [
                    _opt("SC", "SC", "SC"),
                    _opt("ST", "ST", "ST"),
                    _opt("OBC", "OBC", "OBC"),
                    _opt("General", "General", "सामान्य"),
                    _opt("Minority", "Minority", "अल्पसंख्यक"),
                ],
            ),
            _q(
                "income_annual",
                "What is the annual household income?",
                "वार्षिक पारिवारिक आय कितनी है?",
                [
                    _opt("lt_1l", "Below ₹1 lakh", "₹1 लाख से कम"),
                    _opt("1_2_5l", "₹1–2.5 lakh", "₹1–2.5 लाख"),
                    _opt("2_5_8l", "₹2.5–8 lakh", "₹2.5–8 लाख"),
                    _opt("above_8l", "Above ₹8 lakh", "₹8 लाख से अधिक"),
                ],
            ),
        ],
    },
    "housing": {
        "questions": [
            _q(
                "area",
                "Is the house in a rural or urban area?",
                "घर ग्रामीण है या शहरी?",
                [
                    _opt("rural", "Rural", "ग्रामीण"),
                    _opt("urban", "Urban", "शहरी"),
                ],
            ),
            _q(
                "housing_status",
                "What best describes the housing situation?",
                "आवास की स्थिति क्या है?",
                [
                    _opt("houseless", "Houseless / no house", "बेघर / घर नहीं"),
                    _opt("kutcha", "Kutcha house", "कच्चा घर"),
                    _opt("upgrade", "Need upgrade / pucca", "अपग्रेड / पक्का घर"),
                    _opt("has_site", "Have a site, need construction", "जमीन है, निर्माण चाहिए"),
                ],
            ),
            _q(
                "caste",
                "Which social category?",
                "सामाजिक श्रेणी कौन सी है?",
                [
                    _opt("SC", "SC", "SC"),
                    _opt("ST", "ST", "ST"),
                    _opt("OBC", "OBC", "OBC"),
                    _opt("General", "General", "सामान्य"),
                    _opt("Minority", "Minority", "अल्पसंख्यक"),
                ],
            ),
            _q(
                "housing_income",
                "Which income group?",
                "आय समूह कौन सा है?",
                [
                    _opt("ews", "EWS (below ₹3 lakh)", "EWS (₹3 लाख से कम)"),
                    _opt("lig", "LIG (₹3–6 lakh)", "LIG (₹3–6 लाख)"),
                    _opt("mig", "MIG (₹6–12 lakh)", "MIG (₹6–12 लाख)"),
                    _opt("above", "Above ₹12 lakh", "₹12 लाख से अधिक"),
                ],
            ),
        ],
    },
    "pension": {
        "questions": [
            _q(
                "pension_type",
                "Which pension type?",
                "किस प्रकार की पेंशन?",
                [
                    _opt("old_age", "Old age (60+)", "वृद्धावस्था (60+)"),
                    _opt("widow", "Widow", "विधवा"),
                    _opt("disability", "Disability", "दिव्यांगता"),
                    _opt("other", "Other", "अन्य"),
                ],
            ),
            _q(
                "age_band",
                "Which age band?",
                "आयु वर्ग क्या है?",
                [
                    _opt("under_40", "Under 40", "40 से कम"),
                    _opt("40_59", "40–59", "40–59"),
                    _opt("60_79", "60–79", "60–79"),
                    _opt("80_plus", "80+", "80+"),
                ],
            ),
            _q(
                "already_pension",
                "Already receiving a pension?",
                "क्या पहले से पेंशन मिल रही है?",
                [
                    _opt("yes", "Yes", "हाँ"),
                    _opt("no", "No", "नहीं"),
                ],
            ),
            _q(
                "income_annual",
                "What is the annual household income?",
                "वार्षिक पारिवारिक आय कितनी है?",
                [
                    _opt("lt_1l", "Below ₹1 lakh", "₹1 लाख से कम"),
                    _opt("1_2_5l", "₹1–2.5 lakh", "₹1–2.5 लाख"),
                    _opt("2_5_8l", "₹2.5–8 lakh", "₹2.5–8 लाख"),
                    _opt("above_8l", "Above ₹8 lakh", "₹8 लाख से अधिक"),
                ],
            ),
        ],
    },
    "women_child": {
        "questions": [
            _q(
                "who",
                "Who is this for?",
                "यह किसके लिए है?",
                [
                    _opt("pregnant_lactating", "Pregnant / lactating", "गर्भवती / स्तनपान"),
                    _opt("girl_child", "Girl child (under 18)", "बालिका (18 से कम)"),
                    _opt("adult_woman", "Adult woman", "वयस्क महिला"),
                    _opt("mother_infant", "Mother of an infant", "शिशु की माँ"),
                ],
            ),
            _q(
                "ration_level",
                "Ration / poverty status?",
                "राशन / गरीबी की स्थिति?",
                [
                    _opt("AAY", "AAY (Antyodaya)", "AAY (अंत्योदय)"),
                    _opt("BPL", "BPL", "BPL"),
                    _opt("APL", "APL", "APL"),
                    _opt("None", "None of these", "इनमें से कोई नहीं"),
                ],
            ),
            _q(
                "caste",
                "Which social category?",
                "सामाजिक श्रेणी कौन सी है?",
                [
                    _opt("SC", "SC", "SC"),
                    _opt("ST", "ST", "ST"),
                    _opt("OBC", "OBC", "OBC"),
                    _opt("General", "General", "सामान्य"),
                    _opt("Minority", "Minority", "अल्पसंख्यक"),
                ],
            ),
            _q(
                "need",
                "What is needed most?",
                "सबसे ज़्यादा क्या चाहिए?",
                [
                    _opt("cash", "Cash support", "नकद सहायता"),
                    _opt("nutrition_health", "Nutrition / health", "पोषण / स्वास्थ्य"),
                    _opt("livelihood_shg", "Livelihood / SHG", "आजीविका / स्वयं सहायता समूह"),
                    _opt("girl_incentive", "Girl-child incentive", "बालिका प्रोत्साहन"),
                ],
            ),
        ],
    },
    "livelihood": {
        "questions": [
            _q(
                "work_status",
                "What is the current work status?",
                "वर्तमान काम की स्थिति क्या है?",
                [
                    _opt("unemployed", "Unemployed", "बेरोजगार"),
                    _opt("wage", "Wage worker", "मजदूरी"),
                    _opt("self_employed", "Self-employed", "स्वरोजगार"),
                    _opt("start_grow", "Start / grow a business", "व्यवसाय शुरू / बढ़ाएँ"),
                ],
            ),
            _q(
                "focus",
                "What is the main focus?",
                "मुख्य ज़रूरत क्या है?",
                [
                    _opt("job_mgnrega", "Job / MGNREGA", "रोज़गार / मनरेगा"),
                    _opt("skill", "Skill training", "कौशल प्रशिक्षण"),
                    _opt("mudra", "Micro-enterprise / Mudra", "सूक्ष्म उद्यम / मुद्रा"),
                    _opt("street_vendor", "Street vendor", "स्ट्रीट वेंडर"),
                ],
            ),
            _q(
                "profile",
                "Which profile fits best?",
                "कौन सा प्रोफ़ाइल सही है?",
                [
                    _opt("women_ent", "Women entrepreneur", "महिला उद्यमी"),
                    _opt("sc_st", "SC / ST", "SC / ST"),
                    _opt("general_obc", "General / OBC", "सामान्य / OBC"),
                    _opt("minority", "Minority", "अल्पसंख्यक"),
                ],
            ),
            _q(
                "area",
                "Rural or urban?",
                "ग्रामीण या शहरी?",
                [
                    _opt("rural", "Rural", "ग्रामीण"),
                    _opt("urban", "Urban", "शहरी"),
                ],
            ),
        ],
    },
    "health": {
        "questions": [
            _q(
                "health_need",
                "What kind of health support?",
                "किस तरह की स्वास्थ्य मदद?",
                [
                    _opt("hospital", "Hospital / secondary care", "अस्पताल"),
                    _opt("primary", "Primary / clinic", "प्राथमिक / क्लिनिक"),
                    _opt("maternal", "Maternal / newborn", "मातृत्व / नवजात"),
                    _opt("long_term", "Long-term / chronic", "दीर्घकालिक"),
                ],
            ),
            _q(
                "insurance_status",
                "Existing health cover?",
                "क्या स्वास्थ्य बीमा है?",
                [
                    _opt("pmjay_state", "PM-JAY or state scheme", "PM-JAY या राज्य योजना"),
                    _opt("private", "Private insurance only", "केवल निजी बीमा"),
                    _opt("none", "None", "कोई नहीं"),
                ],
            ),
            _q(
                "ration_level",
                "Ration / income status?",
                "राशन / आय की स्थिति?",
                [
                    _opt("AAY_BPL", "AAY / BPL", "AAY / BPL"),
                    _opt("APL", "APL", "APL"),
                    _opt("Above", "Above APL", "APL से ऊपर"),
                ],
            ),
            _q(
                "health_who",
                "Who needs care?",
                "किसे देखभाल चाहिए?",
                [
                    _opt("self", "Self", "स्वयं"),
                    _opt("senior", "Senior", "वरिष्ठ"),
                    _opt("pregnant", "Pregnant", "गर्भवती"),
                    _opt("child", "Child", "बच्चा"),
                ],
            ),
        ],
    },
    "agriculture": {
        "questions": [
            _q(
                "land",
                "How much land is held?",
                "कितनी ज़मीन है?",
                [
                    _opt("landless", "Landless", "भूमिहीन"),
                    _opt("marginal", "Marginal (under 1 ha)", "सीमांत (1 हेक्टेयर से कम)"),
                    _opt("small", "Small (1–2 ha)", "छोटे किसान (1–2 हेक्टेयर)"),
                    _opt("above", "Above 2 ha", "2 हेक्टेयर से अधिक"),
                ],
            ),
            _q(
                "role",
                "What is the farming role?",
                "कृषि में भूमिका क्या है?",
                [
                    _opt("owner", "Owner cultivator", "मालिक किसान"),
                    _opt("tenant", "Tenant / sharecropper", "किरायेदार / बटाईदार"),
                    _opt("agri_labour", "Agricultural labour", "कृषि मज़दूर"),
                ],
            ),
            _q(
                "agri_need",
                "What is needed most?",
                "सबसे ज़्यादा क्या चाहिए?",
                [
                    _opt("income_support", "Income support", "आय सहायता"),
                    _opt("crop_insurance", "Crop insurance", "फसल बीमा"),
                    _opt("irrigation_solar", "Irrigation / solar", "सिंचाई / सोलर"),
                    _opt("credit_equip", "Credit / equipment", "ऋण / उपकरण"),
                ],
            ),
            _q(
                "crop",
                "Main crop / activity?",
                "मुख्य फसल / गतिविधि?",
                [
                    _opt("foodgrain", "Foodgrain", "अनाज"),
                    _opt("horticulture", "Horticulture", "बागवानी"),
                    _opt("dairy_livestock", "Dairy / livestock", "डेयरी / पशुपालन"),
                    _opt("fisheries", "Fisheries", "मत्स्य पालन"),
                ],
            ),
        ],
    },
    "disability": {
        "questions": [
            _q(
                "disability_pct",
                "Disability percentage (if known)?",
                "दिव्यांगता प्रतिशत (यदि पता हो)?",
                [
                    _opt("below_40", "Below 40%", "40% से कम"),
                    _opt("40_74", "40–74%", "40–74%"),
                    _opt("75_plus", "75% or more", "75% या अधिक"),
                    _opt("not_sure", "Not sure", "पता नहीं"),
                ],
            ),
            _q(
                "dis_need",
                "What is needed most?",
                "सबसे ज़्यादा क्या चाहिए?",
                [
                    _opt("pension", "Pension", "पेंशन"),
                    _opt("aids", "Aids / appliances", "सहायक उपकरण"),
                    _opt("edu_skill", "Education / skill", "शिक्षा / कौशल"),
                    _opt("travel_other", "Travel / other", "यातायात / अन्य"),
                ],
            ),
            _q(
                "caste",
                "Which social category?",
                "सामाजिक श्रेणी कौन सी है?",
                [
                    _opt("SC", "SC", "SC"),
                    _opt("ST", "ST", "ST"),
                    _opt("OBC", "OBC", "OBC"),
                    _opt("General", "General", "सामान्य"),
                    _opt("Minority", "Minority", "अल्पसंख्यक"),
                ],
            ),
            _q(
                "income_annual",
                "What is the annual household income?",
                "वार्षिक पारिवारिक आय कितनी है?",
                [
                    _opt("lt_1l", "Below ₹1 lakh", "₹1 लाख से कम"),
                    _opt("1_2_5l", "₹1–2.5 lakh", "₹1–2.5 लाख"),
                    _opt("2_5_8l", "₹2.5–8 lakh", "₹2.5–8 लाख"),
                    _opt("above_8l", "Above ₹8 lakh", "₹8 लाख से अधिक"),
                ],
            ),
        ],
    },
    "food_ration": {
        "questions": [
            _q(
                "ration_card",
                "What ration card does the household have?",
                "किस तरह का राशन कार्ड है?",
                [
                    _opt("AAY", "AAY", "AAY"),
                    _opt("BPL", "BPL", "BPL"),
                    _opt("APL", "APL", "APL"),
                    _opt("no_card", "No card", "कार्ड नहीं"),
                ],
            ),
            _q(
                "food_need",
                "What is needed?",
                "क्या चाहिए?",
                [
                    _opt("monthly", "Monthly ration", "मासिक राशन"),
                    _opt("topup", "Top-up food support", "अतिरिक्त खाद्यान्न"),
                    _opt("onorc", "ONORC / portability", "ONORC / पोर्टेबिलिटी"),
                    _opt("nutrition", "Nutrition", "पोषण"),
                ],
            ),
            _q(
                "household_shape",
                "Who is in the household?",
                "घर में कौन है?",
                [
                    _opt("single", "Single person", "अकेला व्यक्ति"),
                    _opt("with_children", "With children", "बच्चे हैं"),
                    _opt("with_senior", "With a senior", "वरिष्ठ सदस्य हैं"),
                    _opt("pregnant", "Pregnant member", "गर्भवती सदस्य"),
                ],
            ),
            _q(
                "area",
                "Rural or urban?",
                "ग्रामीण या शहरी?",
                [
                    _opt("rural", "Rural", "ग्रामीण"),
                    _opt("urban", "Urban", "शहरी"),
                ],
            ),
        ],
    },
    "labour_bocw": {
        "questions": [
            _q(
                "board_registered",
                "Registered with the construction workers board?",
                "क्या निर्माण श्रमिक बोर्ड में पंजीकृत हैं?",
                [
                    _opt("yes", "Yes", "हाँ"),
                    _opt("no", "No", "नहीं"),
                    _opt("not_sure", "Not sure", "पता नहीं"),
                ],
            ),
            _q(
                "labour_need",
                "What support is needed?",
                "किस मदद की ज़रूरत है?",
                [
                    _opt("education", "Education", "शिक्षा"),
                    _opt("marriage_maternity", "Marriage / maternity", "विवाह / मातृत्व"),
                    _opt("medical", "Medical", "चिकित्सा"),
                    _opt("pension_tools_housing", "Pension / tools / housing", "पेंशन / उपकरण / आवास"),
                ],
            ),
            _q(
                "who_claims",
                "Who is claiming?",
                "दावा कौन कर रहा है?",
                [
                    _opt("worker", "Worker", "श्रमिक"),
                    _opt("spouse", "Spouse", "पति / पत्नी"),
                    _opt("children", "Children", "बच्चे"),
                ],
            ),
            _q(
                "board_state",
                "Which state's construction workers board?",
                "किस राज्य का निर्माण श्रमिक बोर्ड?",
                [
                    _opt("Karnataka", "Karnataka", "कर्नाटक"),
                    _opt("Maharashtra", "Maharashtra", "महाराष्ट्र"),
                    _opt("Other", "Other / not sure", "अन्य / पता नहीं"),
                ],
            ),
        ],
        "skip_board_state_if_state_in": ["Karnataka", "Maharashtra"],
    },
}

# Keyword filters against Category + Scheme Name + Benefit + eligibility blob.
# Best-effort mapping onto existing scheme tags (no dedicated topic tags in the libraries).
CATEGORY_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "education": {
        "any": (
            "education",
            "school",
            "scholarship",
            "hostel",
            "student",
            "vidya",
            "shiksha",
            "fee reimbursement",
            "shulkh",
            "mid-day",
            "mid day",
            "pm poshan",
            "samagra shiksha",
            "fellowship",
            "iti",
            "skill",
            "kaushal",
            "coaching",
            "pre-matric",
            "post-matric",
            "matric",
        ),
        "boost_show": (
            "fee",
            "reimbursement",
            "hostel",
            "vasatigruh",
            "mid-day",
            "poshan",
            "skill",
            "kaushal",
            "sc ",
            "st ",
            "minority",
            "scheduled",
        ),
    },
    "scholarship": {
        "any": (
            "scholarship",
            "shishyavrutti",
            "fellowship",
            "stipend",
            "pre-matric",
            "post-matric",
            "merit",
            "means",
            "vidya nidhi",
            "fee reimbursement",
        ),
    },
    "housing": {
        "any": (
            "housing",
            "awas",
            "pmay",
            "gruh",
            "gruha",
            "shelter",
            "vasati",
            "house",
        ),
    },
    "pension": {
        "any": (
            "pension",
            "maandhan",
            "old age",
            "widow",
            "nsap",
            "ignoaps",
            "ignwps",
            "igndps",
            "sandhya",
            "niradhar",
        ),
    },
    "women_child": {
        "any": (
            "women",
            "woman",
            "girl",
            "maternal",
            "maternity",
            "pregnant",
            "lactat",
            "child",
            "anganwadi",
            "icds",
            "poshan",
            "pmmvy",
            "ladki",
            "lakshmi",
            "shakti",
            "sukanya",
            "beti",
            "kishori",
            "bhagyalakshmi",
            "stree",
            "mahila",
        ),
    },
    "livelihood": {
        "any": (
            "livelihood",
            "msme",
            "mudra",
            "employment",
            "skill",
            "kaushal",
            "mgnrega",
            "nrega",
            "nrlm",
            "nulm",
            "street vendor",
            "svanidhi",
            "standup",
            "stand-up",
            "pmegp",
            "udyam",
            "entrepreneur",
            "self-employment",
            "self employment",
            "shg",
            "yuva nidhi",
            "rozgar",
            "vishwakarma",
        ),
    },
    "health": {
        "any": (
            "health",
            "healthcare",
            "hospital",
            "ayushman",
            "pmjay",
            "pm-jay",
            "arogya",
            "maternal",
            "janani",
            "clinic",
            "medicine",
            "tb support",
            "immunis",
            "ayush",
        ),
    },
    "agriculture": {
        "any": (
            "agricultur",
            "farmer",
            "kisan",
            "crop",
            "horticultur",
            "irrigation",
            "fisher",
            "dairy",
            "livestock",
            "animal husbandry",
            "pm-kisan",
            "pmfby",
            "soil health",
            "kusum",
            "shetkari",
            "raitha",
        ),
    },
    "disability": {
        "any": (
            "disabilit",
            "disabled",
            "divyang",
            "pwd",
            "igndps",
            "adip",
            "assistive",
            "wheelchair",
        ),
    },
    "food_ration": {
        "any": (
            "food",
            "ration",
            "pds",
            "nfsa",
            "antyodaya",
            "aay",
            "foodgrain",
            "anna",
            "onorc",
            "portability",
            "nutrition",
            "poshan",
            "icds",
            "anganwadi",
            "mid-day",
            "mid day",
        ),
    },
    "labour_bocw": {
        "any": (
            "bocw",
            "mbocwwb",
            "construction worker",
            "construction workers",
            "labour",
            "karmika",
            "unorganised worker",
            "e-shram",
            "building and other construction",
        ),
    },
}

ANSWER_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "edu_level:school_1_10": ("pre-matric", "school", "class 1", "1-10", "mid-day", "mid day", "poshan", "foundational"),
    "edu_level:class_11_12": ("11", "12", "higher secondary", "post-matric", "plus two", "pre-university", "puc"),
    "edu_level:ug": ("undergrad", "college", "post-matric", "university", "graduate", "degree"),
    "edu_level:pg": ("post graduate", "postgraduate", "fellowship", "masters", "research", "phd"),
    "edu_level:diploma_iti": ("iti", "diploma", "vocational", "skill", "polytechnic", "industrial training"),
    "edu_level:competitive": ("coaching", "competitive", "exam training", "upsc", "kpsc"),
    "edu_level:dropout": ("skill", "kaushal", "dropout", "open school", "nios", "adult"),
    "schol_level:pre_matric": ("pre-matric", "pre matric", "school"),
    "schol_level:class_11_12": ("11", "12", "post-matric", "higher secondary"),
    "schol_level:ug": ("post-matric", "college", "university", "graduate"),
    "schol_level:pg": ("fellowship", "post graduate", "research", "phd"),
    "schol_level:professional": ("professional", "technical", "engineering", "medical", "merit-cum-means"),
    "schol_level:overseas": ("overseas", "abroad", "foreign", "international"),
    "area:rural": ("rural", "gramin", "gramin", "pds"),
    "area:urban": ("urban", "mhada", "city"),
    "housing_status:houseless": ("homeless", "houseless", "shelter", "pmay"),
    "housing_status:kutcha": ("kutcha", "pmay", "housing"),
    "housing_status:upgrade": ("upgrade", "pucca", "pmay", "housing"),
    "housing_status:has_site": ("construction", "site", "pmay", "housing"),
    "pension_type:old_age": ("old age", "senior", "ignoaps", "sandhya", "60+", "65+"),
    "pension_type:widow": ("widow", "ignwps", "destitute widow"),
    "pension_type:disability": ("disability", "igndps", "divyang"),
    "pension_type:other": ("pension", "family benefit", "nfbs"),
    "age_band:under_40": ("18–40", "18-40", "working age"),
    "age_band:40_59": ("40", "widow", "disability"),
    "age_band:60_79": ("60", "old age", "senior", "65"),
    "age_band:80_plus": ("80", "old age", "senior"),
    "who:pregnant_lactating": ("maternal", "pregnant", "lactat", "pmmvy", "janani", "mathru", "thayi", "prasooti"),
    "who:girl_child": ("girl", "beti", "ladki", "sukanya", "kishori", "bhagyalakshmi", "adolescent"),
    "who:adult_woman": ("women", "woman", "mahila", "ladki bahin", "gruha lakshmi", "shakti"),
    "who:mother_infant": ("maternal", "newborn", "infant", "poshan", "icds", "madilu"),
    "need:cash": ("cash", "dbt", "transfer", "lakshmi", "ladki bahin"),
    "need:nutrition_health": ("nutrition", "poshan", "health", "anganwadi", "icds", "maternal"),
    "need:livelihood_shg": ("shg", "livelihood", "nrlm", "stree shakti", "udyogini"),
    "need:girl_incentive": ("girl", "beti", "sukanya", "ladki", "kishori"),
    "work_status:unemployed": ("unemployment", "yuva", "job", "rozgar", "ncs"),
    "work_status:wage": ("mgnrega", "wage", "nrega", "labour"),
    "work_status:self_employed": ("self-employment", "mudra", "pmegp", "livelihood"),
    "work_status:start_grow": ("mudra", "msme", "startup", "pmegp", "standup"),
    "focus:job_mgnrega": ("mgnrega", "nrega", "wage", "employment"),
    "focus:skill": ("skill", "kaushal", "pmkvy", "apprentice", "ddu-gky"),
    "focus:mudra": ("mudra", "micro", "msme", "pmegp", "credit"),
    "focus:street_vendor": ("street vendor", "svanidhi"),
    "profile:women_ent": ("women", "udyogini", "standup", "mahila"),
    "profile:sc_st": ("sc ", "st ", "scheduled", "tribal"),
    "profile:general_obc": ("obc", "backward", "ebc"),
    "profile:minority": ("minority",),
    "health_need:hospital": ("hospital", "insurance", "ayushman", "pmjay", "arogya", "jan arogya"),
    "health_need:primary": ("clinic", "wellness", "primary", "namma clinic", "hwc"),
    "health_need:maternal": ("maternal", "pregnant", "janani", "pmmvy", "newborn"),
    "health_need:long_term": ("tb", "chronic", "elderly", "long"),
    "insurance_status:none": ("ayushman", "pmjay", "insurance", "arogya"),
    "insurance_status:pmjay_state": ("ayushman", "arogya", "pmjay"),
    "health_who:senior": ("elderly", "senior", "old age"),
    "health_who:pregnant": ("maternal", "pregnant", "janani"),
    "health_who:child": ("child", "immunis", "nutrition"),
    "land:landless": ("landless", "labour", "tenant"),
    "land:marginal": ("small and marginal", "pm-kisan", "2 hectare", "2 ha"),
    "land:small": ("small", "pm-kisan", "2 hectare"),
    "role:tenant": ("tenant", "sharecropper", "cultivator"),
    "role:agri_labour": ("labour", "agricultural labour"),
    "agri_need:income_support": ("income support", "pm-kisan", "samman", "nidhi"),
    "agri_need:crop_insurance": ("crop insurance", "fasal bima", "pmfby"),
    "agri_need:irrigation_solar": ("irrigation", "solar", "kusum", "sinchayee", "pump"),
    "agri_need:credit_equip": ("credit", "kcc", "loan", "equipment", "mechanis", "tractor"),
    "crop:foodgrain": ("foodgrain", "nfsm", "rice", "wheat", "crop"),
    "crop:horticulture": ("horticultur", "midh"),
    "crop:dairy_livestock": ("dairy", "livestock", "animal", "pashu", "goat", "milk"),
    "crop:fisheries": ("fisher", "fish"),
    "dis_need:pension": ("pension", "igndps"),
    "dis_need:aids": ("aids", "appliance", "adip", "assistive", "vayoshree"),
    "dis_need:edu_skill": ("education", "scholarship", "skill", "fellowship"),
    "dis_need:travel_other": ("travel", "transport", "other"),
    "food_need:monthly": ("pds", "ration", "nfsa", "foodgrain", "anna"),
    "food_need:topup": ("anna bhagya", "free foodgrain", "top"),
    "food_need:onorc": ("onorc", "portability", "ration portability"),
    "food_need:nutrition": ("nutrition", "poshan", "icds", "mid-day", "anganwadi"),
    "household_shape:with_children": ("child", "nutrition", "icds", "mid-day"),
    "household_shape:with_senior": ("old age", "senior", "pension"),
    "household_shape:pregnant": ("maternal", "pregnant", "poshan"),
    "labour_need:education": ("education", "scholarship", "ms-cit"),
    "labour_need:marriage_maternity": ("marriage", "maternity", "delivery"),
    "labour_need:medical": ("medical", "health", "ailment"),
    "labour_need:pension_tools_housing": ("pension", "tool", "housing", "funeral"),
    "who_claims:children": ("education", "girl child", "children"),
    "who_claims:spouse": ("maternity", "marriage", "spouse"),
}


def _display(english: str, language: str, packed: dict[str, Any] | None = None) -> str:
    packed = packed or {}
    direct = packed.get(language)
    if direct:
        return str(direct)
    if language in ("Marathi", "Kannada"):
        from .catalog_i18n import overlay_label

        over = overlay_label(english, language)
        if over:
            return over
    return str(packed.get("English") or english)


def label_of(item: dict[str, Any] | str, language: str | None, catalog: dict[str, dict[str, str]] | None = None) -> str:
    lang = language if language in ("English", "Hindi", "Marathi", "Kannada") else "English"
    if isinstance(item, str):
        packed = (catalog or HUB_LABELS).get(item) or {}
        return _display(str(packed.get("English") or item), lang, packed)
    english = str(item.get("English") or item.get("id") or "")
    return _display(english, lang, item)


def questions_for(category_id: str, slots: dict[str, str] | None = None) -> list[dict[str, Any]]:
    pack = PACKS.get(category_id) or {}
    questions = list(pack.get("questions") or [])
    if category_id != "labour_bocw":
        return questions
    skip_states = set(pack.get("skip_board_state_if_state_in") or [])
    state = (slots or {}).get("state") or ""
    if state in skip_states:
        return [q for q in questions if q["id"] != "board_state"]
    return questions


def pack_ids() -> tuple[str, ...]:
    return tuple(PACKS.keys())
