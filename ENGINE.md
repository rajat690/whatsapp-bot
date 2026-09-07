# SETU conversational engine

Every discovery / collect turn follows this loop. **Rules own gates; the LLM only owns wording.**

1. **Hard interrupts** (always win, before LLM collect)  
   Main menu, explicit restart, stop, help, language switch, named scheme, category keyword, wife/spouse schemes, resume.  
   On hit: leave the current slot immediately — never append the old question after an ack.

2. **Greeting / activation** (`setu/greetings.py`)  
   Short lexicon match in English, Hindi, Marathi, Kannada (plus typos and 👋/🙏-only).  
   No language → welcome. Language set + idle → main menu. Mid-collect → main menu interrupt.  
   A greeting that also carries a scheme name, category, or profile story yields to that stronger intent.

3. **Multi-slot extraction**  
   Every collect turn extracts **all** present fields (option tap + NLU + implied household composition).  
   Write into `session["slots"]` and merge into `session["known_profile"]`. Skip filled slots.  
   Ask only the next missing field within the post-consent budget of **4**.

4. **Heard-you**  
   If two or more new facts landed, open with a short confirmation, then one next ask — or confirm/match if the budget is done.

5. **Soft buttons**  
   Consent, yes/no, menus, and closed-choice collect slots: reply buttons (≤3) or a list (4–10), plus numbered text. Free-text slots stay chat.

6. **Park / resume**  
   Leaving Family/Individual mid-collect for named / category / wife snapshots `session["parked"]`. User can say *Resume family profile*.

7. **known_profile**  
   Survives Individual ↔ Family ↔ Category. Seeded into new journeys. Wiped only on explicit restart (`restart`, `/start`, `start over`).

## ≤4 post-consent asks

Language, state, and consent do not count. Then at most four prompted questions:

- **Individual:** age group, occupation, household income, social category  
- **Family:** household size, children under 18, members 60+, household income  

Volunteered extras (marital, disability, ration, …) are stored and used for matching but never asked beyond the cap.
