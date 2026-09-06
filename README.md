# SETU WhatsApp bot (Journey 1 hybrid)

Conversation-first WhatsApp prototype for discovering Karnataka government schemes.

## Hybrid design

- **Conversational by default** — users answer in free text; the bot extracts profile slots with lightweight NLU.
- **Deterministic where required**
  - Eligibility matching against Central + state libraries (Karnataka / Maharashtra when selected)
  - Hard branches: Individual / Family / Help → CRM, Proceed vs Edit, feedback ratings
  - Confirmed slots used for matching

Family Schemes (Journey 2) is stubbed as “coming soon”.

## Layout

- `app.py` — Meta webhook + WhatsApp send
- `setu/orchestrator.py` — Journey 1 conversation flow
- `setu/nlu.py` — keyword/slot extraction (no LLM required)
- `setu/eligibility.py` — deterministic matcher
- `setu/session.py` — in-memory sessions (reset on process restart)
- `data/journey1.json` — slots + hard branches from your workflow schema
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

Optional later: `OPENAI_API_KEY` / `LLM_API_KEY` (not required for this prototype).

## Local smoke test (no WhatsApp)

```bash
python - <<'PY'
from setu.orchestrator import handle_message
uid = "test-user"
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
PY
```

## Deploy

1. Copy these files into `rajat690/whatsapp-bot` (or merge the PR branch if published).
2. Push to `main` (or your Render deploy branch).
3. Redeploy on Render — existing Meta env vars keep working.
4. Message your WhatsApp number: say `hi` to start Journey 1.

## Notes

- Interactive WhatsApp button/list replies are accepted if Meta sends them; the prototype mainly uses plain text for a conversational feel.
- Eligibility is heuristic guidance only — always re-verify on official department sites.
- In-memory sessions reset when Render restarts the service.


## Conversational mode (LLM)

By default the bot uses keyword NLU (deterministic feel).

To make dialogue conversational, set on Render:

- `OPENAI_API_KEY` (required)
- `OPENAI_BASE_URL` (optional, default `https://api.openai.com/v1` — also works with Groq/xAI/OpenRouter-compatible endpoints)
- `OPENAI_MODEL` (optional, default `gpt-4o-mini`)

Aliases: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`.

Eligibility matching stays deterministic either way.
