# SETU WhatsApp bot (Journey 1 + Journey 2 + category browse)

Conversation-first WhatsApp prototype for discovering government schemes (Central + Karnataka / Maharashtra).

## Hybrid design

- **Conversational by default** — users answer in free text; the bot extracts profile slots with lightweight NLU (and an optional LLM when configured).
- **Deterministic where required**
  - Eligibility matching against Central + state libraries (Karnataka / Maharashtra when selected)
  - Hard branches: Individual / Family / Browse category / Help → CRM, Proceed vs Edit, after-detail help / go back, Main Menu vs End Chat, feedback ratings
  - Confirmed slots used for matching
  - **Browse by category** is a structured, isolated tree (not LLM profile collection)

**Journey 1 — Individual Schemes:** age, occupation, income, social category, marital status, disability.

**Journey 2 — Family Schemes:** household size, children under 18, members 60+, family disability, pregnant/breastfeeding, primary occupation, income, housing, ration card, insurance, social category. Counts accept **0**.

**Category path (`schemes_by_category_v1`, `path=category`):** menu button 3 only. Language → state scope → category hub (two WhatsApp-list-sized screens) → ≤4 questions → numbered results. Existing Individual / Family sessions are untouched.

## Layout

- `app.py` — Meta webhook + WhatsApp send
- `setu/orchestrator.py` — Journey 1 + Journey 2 conversation flow (`session["journey_id"]`); dispatches `path=category` to the isolated handler
- `setu/category_path.py` — Browse-by-category tree (does not reuse Journey 1/2 collect phases)
- `setu/category_catalog.py` — hubs, ≤4-question packs, best-effort tag keywords
- `setu/nlu.py` — keyword/slot extraction (no LLM required; family counts including 0)
- `setu/eligibility.py` — deterministic matcher (family-aware scoring for Journey 2; `match_category_schemes` for the category path)
- `setu/llm.py` — optional OpenAI-compatible dialogue layer
- `setu/session.py` — in-memory sessions (reset on process restart)
- `data/journey1.json` — Individual slots + hard branches
- `data/journey2.json` — Family slots + hard branches
- `data/schemes_by_category_v1.json` — category workflow id / hub ids
- `data/schemes_central.json` — Central schemes (~108)
- `data/schemes_karnataka.json` — Karnataka schemes (~85)
- `data/schemes_maharashtra.json` — Maharashtra schemes (~95)
- `data/schemes_index.json` — library index

## Environment (Render)

Same as before:

- `VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `GRAPH_API_VERSION` (optional, default `v23.0`)
- `PORT` (Render sets this)

## Local smoke test (no WhatsApp)

Keyword NLU works without an API key. Individual, Family, and category paths:

```bash
python -m unittest tests.test_language_and_slots tests.test_category_path
```

```bash
python - <<'PY'
from setu.orchestrator import handle_message
from setu.session import reset_session

print("=== Journey 1 Individual ===")
uid = "test-individual"
reset_session(uid)
for msg in [
    "hi",
    "English",
    "individual schemes",
    "I live in Karnataka",
    "I'm 28",
    "salaried",
    "around 25000",
    "OBC",
    "married",
    "no",
    "proceed",
    "1",
]:
    print("U:", msg)
    print("B:", handle_message(uid, msg))
    print("---")

print("=== Journey 2 Family ===")
uid = "test-family"
reset_session(uid)
for msg in [
    "hi",
    "English",
    "family schemes",
    "Karnataka",
    "5",
    "2",
    "1",
    "no",
    "yes",
    "farmer",
    "10000",
    "kutcha",
    "BPL",
    "no",
    "SC",
    "proceed",
    "1",
    "go back",
    "2",
    "okay",
    "end chat",
    "4",
    "no thanks",
]:
    print("U:", msg)
    print("B:", handle_message(uid, msg))
    print("---")

print("=== Category path ===")
uid = "test-category"
reset_session(uid)
for msg in [
    "hi",
    "English",
    "3",
    "1",
    "2",
    "1",
    "1",
    "1",
    "1",
    "1",
    "Back to categories",
]:
    print("U:", msg)
    print("B:", handle_message(uid, msg))
    print("---")
PY
```

## Deploy

1. Push to `main` (or your Render deploy branch).
2. Redeploy on Render — existing Meta env vars keep working.
3. Message your WhatsApp number: say `hi`, then choose Individual, Family, or Browse category.

## Notes

- Interactive WhatsApp button/list replies are accepted if Meta sends them; the prototype mainly uses plain text for a conversational feel. Category hub is capped at 10 numbered rows (then More).
- Eligibility is heuristic guidance only — always re-verify on official department sites.
- In-memory sessions reset when Render restarts the service.
- Journey 2 after-detail options are *I need help* | *Go Back*. Feedback: ratings 1–2 end the chat; 3–5 offer a referral.
- Scheme results on every path use a running numbered list (`1. 2. 3.…`). Users reply with a number or scheme name.

## Conversational mode (LLM)

By default the bot uses keyword NLU (deterministic feel).

To make dialogue conversational, set on Render:

- `OPENAI_API_KEY` (required)
- `OPENAI_BASE_URL` (optional, default `https://api.openai.com/v1` — also works with Groq/xAI/OpenRouter-compatible endpoints)
- `OPENAI_MODEL` (optional, default `gpt-4o-mini`)

Aliases: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`.

Eligibility matching stays deterministic either way. Individual and Family journeys use the LLM for collection and explanations when a key is set, and fall back to keyword NLU if it is not. The category path stays structured/deterministic.
