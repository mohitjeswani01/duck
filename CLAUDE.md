# Duck

A rubber duck that talks back. Built solo, voice-dictated via Wispr Flow, for the **No Hands Wispr Challenge** (WeMakeDevs × Wispr Flow). Submission deadline: **2026-10-30**.

This file is the full-context brief for any future session working on this repo. Read it before doing anything. Keep it updated at the end of every phase.

## Judging criteria (everything below is in service of these four)

1. Solves a real problem in the author's own work.
2. Wispr Flow is used meaningfully.
3. It actually works through a live public link.
4. The demo is clear.

## The problem

Rubber duck debugging works: explaining a bug out loud forces the clarity that finds it. A real duck can't respond, and typing out a full bug explanation is slow enough that the technique gets skipped under deadline pressure — including by the author, across hackathons and OSS contributions.

## The product

Duck is the duck that talks back.

1. Connect a public GitHub repo.
2. Describe the bug out loud — Wispr Flow dictates it into a large, inviting textarea captioned **"hold your Wispr key and just talk."** This textarea is the heart of the product; it must never feel like a cramped chat input.
3. Duck does not jump to a fix. It behaves like a sharp senior engineer:
   - Asks 1–3 focused questions to narrow the problem (capped at ~2 rounds).
   - Decides for itself which files in the repo are relevant and reads them.
   - States a hypothesis plus the evidence for it, before proposing anything.
   - Only then proposes a fix as a clear code diff.
4. If the user says the hypothesis or fix is wrong, Duck keeps digging rather than guessing again blindly.
5. Every session is saved to a searchable bug journal. A resolved session **is** a journal entry — recurring bugs get faster the second time.

**Hard requirement:** the live app opens with no login, and ships with a preloaded sample repo containing a real, planted bug, so a judge can run a full session in under a minute.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind, shadcn/ui |
| Backend | FastAPI, Python, async |
| Database | Postgres on Neon (free tier) |
| AI reasoning | Google Gemini via the official `google-genai` Python SDK |
| Repo access | GitHub REST API, public repos only |
| Hosting | Frontend → Vercel. Backend → Render free tier, kept warm by an external cron ping. |

### Gemini model — do not hardcode

No model name is ever hardcoded in source. It lives in the `GEMINI_MODEL` env var, defaulting to **`gemini-flash-latest`** — Google's official alias that always resolves to the current stable Flash model. This sidesteps guessing a specific version string (an earlier draft of this plan guessed `gemini-3.8-flash`, which could not be confirmed and was removed). Once real API keys are available, run `backend/scripts/list_gemini_models.py` to print the Flash models actually visible to the account, and set `GEMINI_MODEL` explicitly if a more specific pin is wanted.

Tool/function calling and client construction follow the current `google-genai` SDK docs (https://googleapis.github.io/python-genai/) — the API has changed significantly across SDK versions, so re-check docs rather than pattern-matching old examples when touching `gemini_client.py` in Phase 3.

## Key architectural decision: Gemini drives investigation, not hand-written rules

Gemini gets native tool-calling access to `list_files`, `read_file`, `search_code` against the connected repo and decides itself what to read and when it has enough evidence. The backend only executes whatever tool call comes back. An explicit `phase` field runs alongside this loop purely so the UI can render a clean step indicator — the investigation *inside* the "investigating" phase is model-driven, not scripted. This is also why repo connection (file tools) is built **before** the conversation engine: the engine has nothing to call otherwise.

## Session state flow

```
listening → clarifying → investigating → hypothesis → fix_proposed → resolved
               ↑               ↑ ↓            │ "no"        │ "no"
               └── loops ≤2x ──┘        back to investigating ──┘
```

- **listening** — session created, waiting for the first spoken bug description.
- **clarifying** — Duck asks 1–3 questions; capped at ~2 rounds before it must move on.
- **investigating** — Gemini tool-calling loop against the repo (`list_files` / `read_file` / `search_code`), hard-capped at `MAX_TOOL_CALLS_PER_SESSION` (default 15) calls.
- **hypothesis** — Duck states its theory + evidence; user confirms or rejects.
- **fix_proposed** — Duck returns a diff + explanation; user accepts or rejects.
- **resolved** — session closed, `resolution_summary` / `root_cause` / `tags` set, journal entry finalized.

Transitions are driven by Gemini reading the conversation inside a phase-aware system prompt — not UI buttons — so the product stays natural-language-first.

## Real-time streaming (SSE) — protocol designed in Phase 1, used in Phases 3–4

The best demo moment is watching Duck think live (phase changes, "Duck is reading `auth.ts`", "Duck is searching for `refresh token`") instead of a long silent wait. The backend streams a turn's events over **Server-Sent Events**. Event schema lives in `backend/app/schemas/events.py` (Pydantic, discriminated on `type`) and is mirrored in `frontend/src/lib/events.ts` (TypeScript). Event types:

| `type` | Payload | Meaning |
|---|---|---|
| `phase` | `session_id, phase, at` | Session moved to a new phase |
| `tool_call` | `session_id, tool, detail, at` | Gemini is calling `read_file`/`list_files`/`search_code`; `detail` is the path or query shown to the user |
| `assistant_message` | `session_id, phase, content, at` | A question, the hypothesis text, or the fix explanation |
| `diff` | `session_id, file_path, diff_text, at` | A proposed fix, routed to the diff viewer |
| `error` | `message, at` | A friendly, user-safe error (never a raw exception) |
| `done` | `session_id, at` | End of this turn's stream |

Wire format: standard SSE (`event: <type>\ndata: <json>\n\n`), with a heartbeat comment every ~15s to keep the connection alive through Render's proxy. The actual `/sessions/{id}/turn` streaming endpoint is built in Phase 3; Phase 1 only locks the schema so frontend and backend never drift.

## Database schema

A resolved **session** is the bug-journal entry — no separate journal table. Postgres full-text search (`search_vector`, a generated `tsvector` column) covers "search past bugs."

- **repos** — `id, github_url, owner, name, default_branch, file_tree_cache (jsonb), created_at`
- **sessions** — `id, repo_id FK, title, status (active/resolved/abandoned), current_phase (listening/clarifying/investigating/hypothesis/fix_proposed/resolved), resolution_summary, root_cause, tags (text[]), words_spoken_count (int, default 0), search_vector (generated tsvector), created_at, updated_at`
- **messages** — `id, session_id FK, role (user/assistant), phase_at_time, content, created_at`
- **file_reads** — `id, session_id FK, file_path, reason, created_at`
- **hypotheses** — `id, session_id FK, description, evidence (jsonb), confirmed (bool, nullable), created_at`
- **fixes** — `id, session_id FK, hypothesis_id FK, diff_text, file_path, explanation, accepted (bool, nullable), created_at`

`words_spoken_count` — total word count across a session's user messages. Added in Phase 1 specifically to avoid a later migration. Surfaced in the UI (per-session and aggregated across the journal) in a later phase, as evidence of how meaningfully Wispr is actually used.

## Gemini key pool — automatic multi-key failover

The free tier quota per Gemini API key is small, and Duck cannot go down mid-demo. The user supplies 2–3 keys from different accounts via one env var, `GEMINI_API_KEYS` (comma-separated). **No backend code ever talks to Gemini directly — every call goes through `backend/app/services/gemini_key_pool.py`.**

Behavior:
- **Round robin** — successive top-level calls start from the next key index, spreading load across all healthy keys.
- **429 / RESOURCE_EXHAUSTED** → that key is marked `cooling` for `GEMINI_KEY_COOLDOWN_SECONDS` (default 60s), and the pool immediately retries the same request on the next healthy key. The caller never sees the error.
- **401 / 403** → that key is marked `disabled` for the lifetime of the process, with a clear warning logged (never logging the key itself, not even partially — only its index).
- **All keys cooling or disabled** → raises `GeminiAllKeysExhaustedError`, which routers translate into a friendly message: *"Duck needs a short breather, try again in a minute."* Never a raw exception.
- Any other error (5xx, network, etc.) is not the pool's concern and propagates immediately — only quota/auth errors drive pool state.
- `GET /admin/gemini-health` reports how many keys are healthy / cooling / disabled, with remaining cooldown seconds — never the keys themselves.

Unit tests (`backend/tests/test_gemini_key_pool.py`) mock the Gemini call and cover: round robin ordering, 429 failover, 401 permanent disable, and the all-keys-exhausted path.

## Abuse protection (public, no-login app using the author's own quota)

- Per-IP: `RATE_LIMIT_SESSIONS_PER_IP_PER_HOUR` new sessions/hour (default 5), `RATE_LIMIT_MESSAGES_PER_SESSION` messages per session (default 40).
- Global: `GEMINI_DAILY_CALL_CAP` total Gemini calls/day across all users (default 500, in-memory counter — acceptable since Render free tier runs a single instance; resets on restart, which is a known/accepted simplification for a hackathon).
- `MAX_TOOL_CALLS_PER_SESSION` (default 15) — the investigation loop cap, doubles as abuse protection and a demo-stall guard.
- All of the above are env vars so they can be raised on demo day without a deploy.
- Hitting any limit returns a friendly message, never a crash or raw error.

## Hosting (decided now, not deferred to Phase 6)

- **Frontend** → Vercel.
- **Backend** → Render free tier. Free tier sleeps after 15 minutes idle, so an external free cron service pings `GET /health` every 10 minutes to keep it warm.
- `GET /health` does no DB, Gemini, or GitHub calls — it must return fast, always, including right after a cold start, so the cron ping is cheap and reliable. `GET /health/db` is a separate, heavier check (does a real `SELECT 1`) used for our own verification, not for the cron ping.
- Backend reads its port from the `PORT` env var Render injects — never a hardcoded port.
- CORS allow-list comes from `ALLOWED_ORIGINS` (comma-separated env var) — the deployed Vercel URL plus `localhost` origins for dev. Nothing else is allowed.

## Sample buggy repo (Phase 2, author's own repo — not a borrowed one)

A small, realistic app (Next.js or Express task manager) with 2–3 **planted, subtle** bugs — the kind that require Duck to actually read files and reason, not spot an obvious typo. Candidates: an auth token that doesn't refresh correctly, an off-by-one in pagination, a stale-state bug in React. Pushed to the author's own public GitHub. The expected root cause of each planted bug is written down separately so Duck's hypotheses can be checked against ground truth.

## Project rules

- Never commit secrets. All keys live in `.env` files (gitignored); `.env.example` files are kept up to date with every variable and a one-line comment explaining it.
- Typed everywhere: TypeScript on the frontend, Python type hints + Pydantic on the backend.
- Small commits, clear messages.
- Update this file at the end of every phase with what was built and what's next.

## Folder structure

```
/mnt/d/duck/
  CLAUDE.md
  .gitignore
  frontend/            # Next.js, TS, Tailwind, shadcn
  backend/
    app/
      main.py
      config.py             # pydantic settings, every env var
      db.py
      models/                # SQLAlchemy async models
      schemas/
        events.py            # SSE event schema
      routers/
      services/
        gemini_key_pool.py
        github_client.py      # Phase 2
        conversation_engine.py # Phase 3
      core/
        rate_limit.py
      migrations/            # Alembic (async template)
    scripts/
      list_gemini_models.py
    tests/
```

## Phase plan

1. **Scaffolding & architecture** — monorepo, Next.js + FastAPI skeletons, Neon connection, migrations for every table (including `words_spoken_count`), Gemini key pool + tests, rate limiting core, health endpoints, SSE schema, env examples.
2. **Repo connection & smart file selection** — GitHub client (tree fetch/cache, `read_file`, `search_code`), minimal connect-a-repo endpoint, sample buggy repo goes live on GitHub with documented root causes.
3. **Conversation engine** — Gemini tool-calling loop + phase state machine, wired to Phase 2's tools and the SSE schema from Phase 1, messages persisted.
4. **Frontend chat experience & diff view** — the big dictation-first input, chat thread, phase stepper, diff viewer, SSE consumption.
5. **Bug journal & search** — resolution summaries, Postgres full-text search, journal UI, `words_spoken_count` surfaced per-session and aggregated.
6. **Deployment & sample-repo polish** — Neon prod, Render + Vercel live, cron keep-alive wired, final pass on the planted bug's demo-readiness, no-login public access verified end-to-end.
7. **Polish & demo** — error/loading states, README, rehearsed demo script.

---

## Progress log

### Phase 1 — complete (2026-10-22)

Built:
- Monorepo at `/mnt/d/duck`, git initialized on `main`, `.gitignore` covers both apps plus all `.env*`.
- **Frontend**: Next.js 16 (App Router, TS, Tailwind v4, shadcn/ui initialized with the `neutral` base color). `next.config.ts` forces webpack + polling (`WATCHPACK_POLLING=true next dev --webpack`) because Turbopack does not support polling at all, and this repo's files live on a drvfs-mounted Windows drive where native file-change events don't propagate to WSL. Landing page is a placeholder proving the scaffold renders — the real chat UI is Phase 4.
- **Backend**: FastAPI skeleton with `config.py` (every env var below), async SQLAlchemy models for all six tables, a hand-written Alembic migration (`0001_initial`, async template) rather than autogenerated, since no live Neon connection existed yet to diff against. Verified with `alembic upgrade head --sql` (offline SQL compiles cleanly — note: Postgres enum types used by name across tables need `create_type=False` on the migration's local `ENUM(...)` objects plus one explicit `.create(checkfirst=True)` each, otherwise offline `--sql` mode double-emits `CREATE TYPE`, since checkfirst needs a live connection it doesn't have in that mode).
- **Gemini key pool** (`app/services/gemini_key_pool.py`): round robin, 429→cooldown, 401/403→permanent disable, `GeminiAllKeysExhaustedError` when all keys are down, `/admin/gemini-health` reports status without ever exposing keys. `scripts/list_gemini_models.py` ready to run once real keys exist. 5 unit tests, all passing, mocking Gemini via an injected `client_factory` (added specifically for testability — never touches the real SDK in tests).
- **Rate limiting** (`app/core/rate_limit.py`): slowapi `Limiter` keyed by IP, a dynamic per-IP session limit read live from settings, a friendly 429 handler, and an in-memory `GeminiUsageTracker` for the daily global cap. 3 unit tests passing. Not yet attached to a real session-creation route — that route doesn't exist until Phase 3. Per-session message cap is documented but enforced in Phase 3's turn endpoint, since it needs a DB-backed message count that doesn't exist yet either.
- **SSE event schema** (`app/schemas/events.py` + mirrored `frontend/lib/events.ts`): `phase`, `tool_call`, `assistant_message`, `diff`, `error`, `done` — locked now, streamed for real in Phase 3/4.
- `backend/.env.example` and `frontend/.env.local.example`, every var commented.
- Virtualenv deliberately lives at `~/.venvs/duck-backend`, **not** inside `backend/`: creating a venv directly on the drvfs-mounted `/mnt/d` timed out repeatedly (thousands of small files over the 9p protocol). Project code stays on `/mnt/d/duck` as required; only the venv itself is off that drive.

Verified: `pytest` → 8/8 passing. `python -c "import app.main"` → succeeds, all routes registered. `alembic upgrade head --sql` → compiles. `npm run build` → see below.

### Next: Phase 2

GitHub client (`list_files` / `read_file` / `search_code`), a real repo-connect endpoint, and the sample buggy repo (author's own, 2-3 planted subtle bugs, pushed to public GitHub with documented root causes).
