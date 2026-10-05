# Deslopify: notes for Claude Code

Detects likely AI-generated text and reconstructs the author's agenda. Backend: FastAPI + Anthropic. Frontend: React + Vite.

## Commands
- Backend (from `backend/`, venv active): `pytest` · `ruff check . && ruff format --check .` · `uvicorn app.main:app --reload`
- Frontend (from `frontend/`): `npm run lint` · `npm run build` · `npm run dev`
- Eval (spends real API money, needs `ANTHROPIC_API_KEY`): `python -m evals.run_eval --repeats 3`. Don't run it unprompted.

## Architecture rules (do not break)
- `app/pipeline.py` is the single analysis path, shared by API, evals and `investigate/`. Change behaviour there, not in callers.
- **Code, not the model, decides**: verdict thresholds (`pipeline.decide`), quote verification (`verification.py`), rate limits, spend cap, auth. Never move these into a prompt.
- Every agenda claim must carry a verbatim quote; unverifiable claims are dropped. Keep this invariant when touching schemas or prompts.
- Pasted text is untrusted data: always pass it through `prompts.wrap_untrusted`. Never put it in the system prompt, in logs, or in error responses.
- Never log request bodies or IPs. Sentry stays `send_default_pii=False`.
- Security controls fail closed (`/stats` 404 without `STATS_SECRET`; budget breaker blocks before the LLM call).

## Sharing
- `/share` must only accept server-signed tickets (`share.verify_ticket`); never accept a client-supplied result.
- Shared records must never contain the pasted text. Quotes are the only fragments, and `ShareRecord` has bounded field sizes.
- Shares live only in the durable store (`ResilientStore.durable` / `primary`); no silent in-memory fallback.
- Wording matters: results are "estimates", never "proof"; keep the banner and the creator acknowledgement. Changing the result shape means bumping `share.SCHEMA_VERSION` and keeping the share page able to read old versions.

## Prompts
Files `app/prompts/<name>.<version>.md`. Changing a prompt's wording = **new version file** (and the output schema in `schemas.py` only tracks the newest agenda version; `agenda.v1.md` is history) + bump `DEFAULT_VERSIONS` in `app/prompts.py`; never edit a released version in place (results are traced by version). Then run the eval and update the README table and `docs/MODEL_DECISION.md`.

## Tests
`tests/` fakes Anthropic (`FakeMessages` in `conftest.py`) and Redis (`MemoryStore`); no network. Add a test with every behaviour change. Honest reporting rule: never write eval numbers into docs that weren't produced by a real run.

## Models
Default `claude-haiku-4-5-20251001` (env `MODEL`). Don't send `temperature`/`top_p` or forced `tool_choice`: newer models reject them. Structured output is JSON-in-text validated by Pydantic for that reason.
