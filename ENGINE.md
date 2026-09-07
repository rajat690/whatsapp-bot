# SETU conversational engine

Every discovery / collect turn follows this loop. **Rules own gates; the LLM only owns wording.**

1. **Hard interrupts** (always win, before LLM collect, list picks, and named lookup)  
   End Chat / farewells (bye, tata, ciao, ola, dhanyavad, stop, …), Main menu, explicit restart, help, language switch, named scheme, category keyword, wife/spouse schemes, resume.  
   On hit: leave the current slot immediately — never append the old question or reprint a scheme list.

2. **Greeting / activation** (`setu/greetings.py`)  
   Short lexicon match in English, Hindi, Marathi, Kannada (plus typos, hiya, and 👋/🙏-only).  
   A pure greeting **restarts the whole workflow** (fresh session → language picker), same as a brand-new `hi`.  
   A greeting that also carries a scheme name, category, or profile story yields to that stronger intent.

3. **Scheme detail + What next?**  
   After a named or journey scheme card, WhatsApp gets **two messages**: (1) detail only, (2) “What next?” with interactive options.  

4. **Multi-slot extraction**  
   Every collect turn extracts **all** present fields (option tap + NLU + implied household composition).  
   Write into `session["slots"]` and merge into `session["known_profile"]`. Skip filled slots.  
   Ask only the next missing field within the post-consent budget of **4**.  
   Exact age (`age 54` / `I am 54`) is stored as `slots["age"]` **and** the coarse `age_group` bucket. Religion/community words (`muslim`, …) map to `social_category=Minority`.  
   A one-shot dump with **age + occupation + community** (and “what schemes”) is enough to rank — leftover budget asks (usually income) are skipped.

5. **Heard-you**  
   If two or more new facts landed, open with a short confirmation, then one next ask — or confirm/match if the budget is done.

6. **Soft buttons**  
   Consent, yes/no, menus, and closed-choice collect slots: reply buttons (≤3) or a list (4–10), plus numbered text. Free-text slots stay chat.

7. **Scheme lists (strict)**  
   `scheme_list` / `cat_results` / `named_scheme_list` outbound body is **only** the deterministic formatter: scope note + intro + `N. Name [Central|State]` + footer. No LLM prose, no bullets (`•`), no second parallel list. Interactive rows (first 10; buttons if ≤3) use the same numbers; tapping a row opens detail. After detail, What next? stays a separate message.

8. **Park / resume**  
   Leaving Family/Individual mid-collect for named / category / wife snapshots `session["parked"]`. User can say *Resume family profile*.

9. **known_profile**  
   Survives Individual ↔ Family ↔ Category. Seeded into new journeys. Wiped only on explicit restart (`restart`, `/start`, `start over`).

## ≤4 post-consent asks

Language, state, and consent do not count. Then at most four prompted questions:

- **Individual:** age group, occupation, household income, social category  
- **Family:** household size, children under 18, members 60+, household income  

Volunteered extras (marital, disability, ration, exact age, gender, …) are stored and used for matching but never asked beyond the cap.

## Eligibility: hard gates vs soft score

`setu/eligibility.py` ranks schemes in two layers:

1. **Hard gates** (exclude, do not rank) when the user fact is known and the scheme text has a clear window:
   - **Age:** parse `Age Criteria` ranges (`18–40`, `entry 18-40`, `up to 40`, `below 40`, `60+`, `16–59`). Exact `slots["age"]` outside the **entry** window (ignore “pension from 60”) drops the scheme. Age-group buckets only exclude when the *entire* bucket is incompatible (e.g. `60+` vs max 40; `18–59` vs strict `60+` only). An `18–59` bucket without an exact age does **not** drop an 18–40 entry scheme.
   - **Income / gender / category / occupation:** monthly ceilings, women-only, minority-only, student-only, farmer-only — only when the criterion is explicit.
2. **Soft score** (occupation keywords, minority boost, flagships) runs **only** if the scheme survived hard gates. A labourer keyword must not salvage PM-SYM for a 54-year-old.

Minority/muslim boosts community schemes; they never invent eligibility or override a hard age/income fail.
