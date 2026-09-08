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
   A one-shot dump with **age + occupation + community** (and “what schemes”) is enough to rank — leftover budget asks (usually income, or gender if still unknown) are skipped. Self-identified gender (`I am a woman/man/female/male` and HI/KN/MR equivalents) is stored as `slots["gender"]` and is not re-asked.

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

Language, state, and consent do not count. Then at most four prompted questions.

**Gender** is a first-class collect slot on Individual, Family, and category packs when unknown. Canonical stored values (buttons + `slots["gender"]` / `known_profile`):

- `Male`
- `Female`
- `Prefer not to say`

Free-text may also store `Transgender` (not a button). For hard gates it is treated like Prefer not to say.

Ask order (when gender is **unknown**):

- **Individual:** age group, gender, occupation, household income  
  (social category is dropped from the prompted 4 so gender can fire women-only / male-only gates)
- **Family:** household size, gender, children under 18, household income  
  (members 60+ is the slot that yields). Self path asks once (`gender_subject=self`). Wife / adult-woman / pregnant / girl-child presets infer `Female` and skip. Ask the relevant person only when `gender_subject=member` and gender is still unknown.
- **Category packs:** append gender when the pack has room; if the pack is already at 4, replace the last pack question. Skip when gender is already known or inferred from `who` / widow pension.

If gender is **already known** (free text, known_profile, or inference), the original four asks stay (Individual: age / occupation / income / social category; Family: size / children / 60+ / income). Oneshot age + occupation + community still skips leftover budget asks.

Gender buttons use the same interactive pattern as age / profession / income / social category (3 reply buttons + numbered text). List-button copy is “choose gender” / लिंग चुनें / लिंग निवडा / ಲಿಂಗ ಆಯ್ಕೆ — never a bare “Choose”.

## Eligibility: hard gates vs soft score

`setu/eligibility.py` ranks schemes in two layers:

1. **Hard gates** (exclude, do not rank) when the user fact is known and the scheme text has a clear window:
   - **Age:** parse `Age Criteria` ranges (`18–40`, `entry 18-40`, `up to 40`, `below 40`, `60+`, `16–59`). Exact `slots["age"]` outside the **entry** window (ignore “pension from 60”) drops the scheme. Age-group buckets only exclude when the *entire* bucket is incompatible (e.g. `60+` vs max 40; `18–59` vs strict `60+` only). An `18–59` bucket without an exact age does **not** drop an 18–40 entry scheme.
   - **Income / gender / category / occupation:** monthly ceilings, women-only, minority-only, student-only, farmer-only — only when the criterion is explicit. **Male hard-fails women-only** (and Female hard-fails male-only). **Prefer not to say does not hard-exclude** gender-restricted schemes; they stay in the pool with a soft down-rank (`gender-unconfirmed`) so the user can still open them (official eligibility is on the scheme card).
2. **Soft score** (occupation keywords, minority boost, flagships, matching gender boost) runs **only** if the scheme survived hard gates. A labourer keyword must not salvage PM-SYM for a 54-year-old.

Minority/muslim boosts community schemes; they never invent eligibility or override a hard age/income fail.
