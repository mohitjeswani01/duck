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
listening → investigating → clarifying (optional, ≤2 rounds) → investigating
                 ↓ ↑                                                 ↑
            hypothesis ───────────────── "no" / low confidence ──────┘
                 ↓
           fix_proposed ──────────────────── "no" ──────────────────→ investigating
                 ↓ "yes"
             resolved
```

Changed in Phase 3 from the original plan: **Duck investigates first, before ever asking a clarifying question** — a real senior engineer glances at the code before interrogating the user. `listening` is transient (the engine flips straight to `investigating` the instant a session is created, before Gemini is even called once). Clarifying is optional and Gemini can skip it entirely if the user's own description is already enough to form a hypothesis.

- **listening** — exists for an instant between session creation and the first Gemini call.
- **investigating** — `list_files` / `read_file` / `search_code`, plus `ask_questions` and `state_hypothesis` become available. Hard-capped at `MAX_TOOL_CALLS_PER_TURN` (default 15) **per turn**, not per session (renamed from `MAX_TOOL_CALLS_PER_SESSION` in Phase 3 once this was clarified) — a long multi-turn session can rack up far more than 15 tool calls total, just not more than 15 in one back-and-forth.
- **clarifying** — Duck called `ask_questions` (1–3 questions); paused until the user answers. Capped at `MAX_CLARIFYING_ROUNDS` (default 2) — enforced in the tool handler, not just the prompt. The tool handler also refuses the *first* round unless Duck has already called a file tool at least once this session (derived from `file_reads`, no extra column needed) — the whole point of this phase is that the question references something Duck actually found.
- **hypothesis** — Duck called `state_hypothesis` (description + evidence with file/line citations + a confidence level). `medium`/`high` confidence falls straight through to `propose_fix` in the same turn; `low` confidence pauses so the user can confirm first. A user reply while paused here is treated exactly like a clarifying answer — phase flips back to `investigating` and Gemini decides from the message content whether that was a confirmation or a rejection.
- **fix_proposed** — Duck called `propose_fix`; paused for `POST /sessions/{id}/fixes/{fix_id}/accept` or `/reject`. Rejecting sends the phase back to `investigating` with the rejection (+ any feedback) as a synthetic user message.
- **resolved** — Duck called `mark_resolved`, only possible once the latest fix batch is accepted. Session closed; this **is** the bug-journal entry.

Transitions are driven entirely by **four control tools**, not parsed text — see "Conversation engine" below.

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

- **repos** — `id, github_url, owner, name, default_branch, last_indexed_at, created_at`
- **repo_files** — `id, repo_id FK, file_path, content, size_bytes, language, created_at` (Phase 2 — replaces the original `file_tree_cache` jsonb column, dropped in migration 0002; see "Repo connection" below)
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
- Any other error (5xx, network, etc.) is not the pool's concern and propagates immediately — only quota/auth errors drive pool state. **Observed live during Phase 3 testing:** a transient `503 UNAVAILABLE "high demand"` from Gemini propagates straight up and ends the turn with a generic error — see the Phase 3 progress log for why this is flagged as a real weak spot worth revisiting.
- `GET /admin/gemini-health` reports how many keys are healthy / cooling / disabled, with remaining cooldown seconds — never the keys themselves.
- **Phase 3 — model fallback:** key health is now tracked per `(key_index, model)` pair, not just per key, because quota is a separate bucket per model on Google's side. `GEMINI_FALLBACK_MODEL` (default `gemini-3.6-flash`, alongside `GEMINI_MODEL` defaulting to `gemini-3.8-flash` once real keys confirmed both exist and support `generateContent` — see `scripts/list_gemini_models.py`) is tried on *every* key only after every key is cooling/disabled for the primary model, via `GeminiKeyPool.execute_with_fallback()`. `GET /admin/gemini-health` now reports both models' key health separately.

Unit tests (`backend/tests/test_gemini_key_pool.py`) mock the Gemini call and cover: round robin ordering, 429 failover, 401 permanent disable, the all-keys-exhausted path, per-model state isolation, and `execute_with_fallback` (every key tried on the primary model before any key is retried on the fallback).

## Abuse protection (public, no-login app using the author's own quota)

- Per-IP: `RATE_LIMIT_SESSIONS_PER_IP_PER_HOUR` new sessions/hour (default 5), `RATE_LIMIT_MESSAGES_PER_SESSION` messages per session (default 40).
- Global: `GEMINI_DAILY_CALL_CAP` total Gemini calls/day across all users (default 500, in-memory counter — acceptable since Render free tier runs a single instance; resets on restart, which is a known/accepted simplification for a hackathon).
- `MAX_TOOL_CALLS_PER_TURN` (default 15, renamed from `MAX_TOOL_CALLS_PER_SESSION` in Phase 3 — it's enforced per turn) — the investigation loop cap, doubles as abuse protection and a demo-stall guard. Hitting it doesn't fail silently: the engine makes one final tools-disabled Gemini call asking it to summarize findings so far, then pauses for the user.
- All of the above are env vars so they can be raised on demo day without a deploy.
- Hitting any limit returns a friendly message, never a crash or raw error.

## Hosting (decided now, not deferred to Phase 6)

- **Frontend** → Vercel.
- **Backend** → Render free tier. Free tier sleeps after 15 minutes idle, so an external free cron service pings `GET /health` every 10 minutes to keep it warm.
- `GET /health` does no DB, Gemini, or GitHub calls — it must return fast, always, including right after a cold start, so the cron ping is cheap and reliable. `GET /health/db` is a separate, heavier check (does a real `SELECT 1`) used for our own verification, not for the cron ping.
- Backend reads its port from the `PORT` env var Render injects — never a hardcoded port.
- CORS allow-list comes from `ALLOWED_ORIGINS` (comma-separated env var) — the deployed Vercel URL plus `localhost` origins for dev. Nothing else is allowed.

## Repo connection (Phase 2 — tarball download, not per-file API calls)

Connecting a repo does **one** GitHub API call for metadata + **one** tarball download — never a per-file fetch, never the code search API (it needs a token and has a punishing rate limit that would break a live demo). `backend/app/services/github_client.py` validates the URL strictly (public `github.com` only, with/without `.git`, with/without a trailing slash), fetches `/repos/{owner}/{repo}` to confirm it's public and get the default branch, downloads `/repos/{owner}/{repo}/tarball/{branch}`, and extracts it in-memory with `tarfile`. The GitHub token (`GITHUB_TOKEN`) is optional and used automatically when present; unauthenticated requests just get the lower 60/hr GitHub rate limit, which is fine since each connect is 2 calls total.

Filtering during extraction (all caps are env vars):
- Skips directories: `node_modules, dist, build, .next, .git, vendor, .venv, venv, __pycache__, .cache, .turbo, coverage, .pytest_cache, target, .idea, .vscode, out`.
- Skips lock files (`package-lock.json`, `yarn.lock`, etc.), `*.min.js`/`*.min.css`, known binary/image/archive extensions, and anything that decodes as binary (null byte in the first 1KB, or a `UnicodeDecodeError`).
- Skips any single file over `REPO_MAX_FILE_BYTES` (default 200KB).
- Rejects the whole repo — before storing anything — if it exceeds `REPO_MAX_FILES` (default 500) or `REPO_MAX_TOTAL_BYTES` (default 5MB), with the friendly message "Duck works best on small to medium repos."

Filtered files are stored in the `repo_files` table (see schema above), keyed by `(repo_id, file_path)`. Reconnecting the same repo reuses the stored copy if `last_indexed_at` is within `REPO_CACHE_TTL_SECONDS` (default 1 hour); otherwise it re-downloads and replaces all rows for that repo. `list_files` / `read_file` / `search_code` (below) only ever query this table — GitHub is never touched again after connect.

Errors (invalid URL, repo not found/private, GitHub rate-limited, repo too large, GitHub unreachable) are all typed exceptions with a `friendly_message`, mapped to HTTP status codes in `app/routers/repos.py` — the frontend never sees a raw exception.

## File tools (Phase 2 — plain Python functions + Gemini function declarations)

`backend/app/services/file_tools.py` implements `list_files`, `read_file`, `search_code` as DB-backed async functions, with the actual matching/formatting logic factored into pure, DB-free functions (`list_files_pure`, `read_file_pure`, `search_code_pure`) so they're unit-testable without Postgres. They only ever read from `repo_files` — never the real filesystem, never GitHub again.

- **`list_files(pattern?)`** — directory-prefix or glob (via `fnmatch`, so `*` is not directory-scoped) match against stored paths, capped at `TOOL_LIST_FILES_MAX_RESULTS` (default 200), sorted, with a `truncated` flag.
- **`read_file(path, start_line?, end_line?)`** — every returned line is numbered. No range + short file → whole file. No range + long file → first `TOOL_READ_FILE_MAX_LINES` lines (default 300) plus a truncation note with the real total line count. A path containing `..`, a leading `/`, or an empty segment is rejected before any lookup (`PathTraversalError`) — defense in depth, even though stored paths can never actually contain `..` themselves.
- **`search_code(query, file_pattern?, is_regex?)`** — literal substring search is always safe (linear `in`); regex search skips any line longer than 300 chars before matching (bounds worst-case backtracking) and the whole call runs in a worker thread under an `asyncio.wait_for` timeout (`TOOL_SEARCH_TIMEOUT_SECONDS`, default 3s) — on timeout it returns `timed_out=True` with partial/no results rather than hanging the request. Results capped at `TOOL_SEARCH_MAX_RESULTS` (default 50), each with ~1 line of context on either side.
- All three tool outputs are additionally capped at `TOOL_OUTPUT_MAX_CHARS` (default 20,000) before being handed back, so one huge match can't blow up Gemini's context.
- `read_file` and `search_code`, when called with a `session_id`, write to `file_reads` (one row per file actually read/matched) and emit a `tool_call` SSE event via an injected `emit` callback — both optional, since Phase 2 has no live session/turn endpoint yet. Phase 3's conversation engine passes both. `list_files` only emits the SSE event (no single file was "read").
- Gemini-facing schemas live in `app/services/tool_declarations.py` as `types.FunctionDeclaration(..., parameters_json_schema={...})` — the plain-JSON-Schema form confirmed against the current `google-genai` docs — bundled into `FILE_TOOLS = types.Tool(function_declarations=[...])`, ready for Phase 3 to pass straight into `GenerateContentConfig(tools=[FILE_TOOLS])`.
- `POST /dev/tools/{list_files,read_file,search_code}` lets these be curl-tested directly against a connected repo, bypassing the (not-yet-built) conversation loop. Only registered in `app/main.py` when `ENABLE_DEV_TOOLS=true` — the routes don't exist at all otherwise, so there's nothing to accidentally expose in production.

## Sample buggy repo (Phase 2, author's own repo — not a borrowed one)

Built as a separate repo, `taskboard` — a small Express + React task manager, own git history, pushed to the author's own public GitHub (push commands are in the Phase 2 progress log below). 3 planted, subtle bugs: a seconds-vs-milliseconds unit mismatch in the frontend's token-refresh check (logs users out almost immediately instead of after an hour), an off-by-one in the backend's pagination offset (`page * pageSize` instead of `(page - 1) * pageSize`, so page 1 skips the first page's worth of tasks), and a stale closure in a `useEffect`-driven polling interval that doesn't depend on the filter state (so changing the status filter reverts a few seconds later). No bug is hinted at in code comments, names, or the README. The answer key — symptom, files, root cause, correct fix for each — lives at `docs/sample_bugs.md` in **this** repo, deliberately not in taskboard itself, so Duck can't read its own answer key.

## Conversation engine (Phase 3)

The Gemini tool-calling loop lives in `app/services/conversation_engine.py`, run as a background `asyncio` task per **turn** (one user message, or one accept/reject decision on a fix) — `POST /sessions`, `/sessions/{id}/messages`, and the fix accept/reject endpoints all just persist the trigger and `asyncio.create_task(run_turn(...))`, returning immediately; the caller watches progress via `GET /sessions/{id}/stream`.

**Four control tools**, not parsed text, drive the state machine — every one of Gemini's seven tools (3 file + 4 control) goes through a single `control_tools.dispatch()` entry point in the engine loop, so the engine itself never special-cases by tool name:

- **`ask_questions(questions: 1-3 strings)`** — saves the questions as an assistant message, flips phase to `clarifying`, pauses the turn. Rejected with a clear error (sent back to Gemini as the tool result, not surfaced to the user) if: more than `MAX_CLARIFYING_ROUNDS` rounds have been used, the count of questions is outside `MIN/MAX_QUESTIONS_PER_ROUND`, or — only on round 1 — no file tool has been called yet this session.
- **`state_hypothesis(description, evidence: [{file_path, line_number, note}], confidence: low|medium|high)`** — saves a `hypotheses` row, flips phase to `hypothesis`. Only pauses the turn if `confidence == "low"`; `medium`/`high` let Gemini continue straight on to `propose_fix` in the same turn.
- **`propose_fix(changes: [{file_path, start_line, end_line, new_code}], explanation)`** — **Gemini never writes a diff.** The backend reads the real file content via `file_tools.get_raw_file_content`, validates the line range actually exists, and builds the unified diff itself with `difflib.unified_diff`. One `fixes` row per file in `changes`, all sharing one explicit batch timestamp (not the DB default) so the accept/reject endpoint can identify and update "the whole proposal" as a unit without a new schema column. Always pauses the turn.
- **`mark_resolved(resolution_summary, root_cause, tags)`** — only dispatchable at all if the latest fix batch has `accepted == True` on every row (enforced by `allowed_tools_for_phase`, not inside the handler). Writes `resolution_summary`/`root_cause`/`tags` onto the session, flips `status` to `resolved`. This **is** the bug-journal entry.

**Phase enforcement, not phase scripting:** `control_tools.allowed_tools_for_phase(db, session)` computes the legal tool set for the session's current phase on every single tool call (not cached) — calling anything outside that set returns `{"error": "..."}` as the function result instead of executing, letting Gemini read the error and correct itself within the same turn. Verified in tests: a wrong-phase `propose_fix` attempt, and an out-of-range `propose_fix` line range, both get a same-turn second attempt that succeeds.

**System prompt** lives entirely in `app/services/system_prompt.py` — nothing else — so Duck's personality/rules can be tuned without touching control flow. Key rules: investigate before asking, cite file+line for every claim, keep responses short, reflect back what the user said, and interpret Wispr Flow's dictation quirks (mangled technical terms, filler words, rambling) charitably and silently — never comment on the transcription.

**Context management:** the exact Gemini `contents` list (including raw `function_call`/`function_response` parts, which plain-text `messages` rows can't capture) is kept in an in-memory per-session dict (`_ENGINE_STATE`), not persisted — the same "single Render instance" tradeoff already accepted for the SSE queue and the daily-call counter. `_compact_old_tool_results` replaces the payload of any tool result older than the `GEMINI_CONTEXT_KEEP_RECENT_TOOL_RESULTS` (default 6) most recent ones with a short placeholder before every Gemini call, so a long session's context/cost stays bounded without losing the human-readable conversation (only bulky tool *results* get compacted, never assistant/user text). If the process restarts mid-session, `_seed_contents_from_db` reconstructs a text-only history from the durable `messages` table — Duck just might re-read a file it already read, not crash.

**Per-call timeout + daily cap:** every Gemini call is wrapped in `asyncio.wait_for(timeout=GEMINI_CALL_TIMEOUT_SECONDS)` (default 45s) inside the operation passed to the key pool, and `GeminiUsageTracker.increment_and_check()` runs before every call in the loop (not just once per turn), so a long tool-calling turn is still bounded by the daily cap mid-turn.

**Tool-call cap doesn't fail silently:** hitting `MAX_TOOL_CALLS_PER_TURN` mid-loop triggers one final Gemini call with tools removed from the config entirely, asking it to summarize findings in 2-4 sentences, which gets saved/emitted like any other assistant message before the turn ends.

**Metrics:** `run_turn` returns a `TurnMetrics(gemini_calls, tool_calls, total_seconds)` and logs the same via `logger.info` on every turn (used by `scripts/evaluate.py` to track quota usage without scraping logs). `gemini_calls` increments *before* each call is made, not after it succeeds — a failed/timed-out attempt still spent real time (and sometimes real quota) and needs to show up in the count, discovered while live-testing this phase (see the bug below for why mocked tests alone wouldn't have caught this kind of gap).

**A real bug found only by testing against the live API, now fixed:** function-call results were sent back to Gemini wrapped in `types.Content(role="tool", parts=[...])` — matching the example in the *current* hosted `google-genai` docs fetched for Phase 2/3. Against the real Gemini Developer API, this raises `400 INVALID_ARGUMENT: Role 'tool' is not supported. Please use a valid role: SYSTEM, SYSTEM_1, USER, ASSISTANT, DEVELOPER, CONTEXT, USER_CONTEXT, MODEL, USER` — on literally the second Gemini call of any turn that uses a tool, i.e. almost every real turn. `test_conversation_engine.py`'s `ScriptedPool` returns canned responses regardless of what `Content`/`config` it's handed, so this was invisible to all 21 passing mocked tests; it only surfaced live, mid-Phase-3, while chasing down what first looked like pure Gemini-API instability. Fixed by sending function responses back as `role="user"` instead. Same root lesson as the Phase 2 `parameters_json_schema` bug: a mocked test proves the *state machine* is right, never that the *wire format* the real SDK/API actually accepts is right — there is no substitute for at least one real end-to-end call per phase before calling it done.

**A second real bug, same root cause, also fixed:** even after the `role="user"` fix, a *second* real tool-call turn (echoing the model's own prior `function_call` content back into history, unmodified, as required for multi-turn tool use) failed with `400 INVALID_ARGUMENT: Function call is missing a thought_signature in functionCall parts` (see https://ai.google.dev/gemini-api/docs/thought-signatures). This is a newer Gemini 3.x "thinking model" requirement — the model attaches a signature to each function call that must round-trip back unmodified on the next turn — and the `google-genai==1.3.0` pin from Phase 1 predates it entirely, silently dropping the field when re-serializing `response.candidates[0].content`. **Fixed by upgrading to `google-genai==2.33.0`** (pulling `pydantic` 2.10.4→2.14.1 along with it); re-verified `types.FunctionDeclaration` still accepts the `parameters=types.Schema(...)` form used everywhere (it also now accepts `parameters_json_schema`, so Phase 2's original code would've actually worked on *this* version — just not on 1.3.0), and all 92 tests still pass unchanged. Confirmed fixed live: an end-to-end run afterward got through 10 real tool calls across 11 Gemini calls with no thought_signature or role errors.

**SSE event mapping** — no changes to the Phase 1 event schema were needed; the four control tools map onto the existing types: `ask_questions`/`state_hypothesis` → `phase` + `assistant_message`; `propose_fix` → `phase` + one `diff` per file + `assistant_message`; `mark_resolved` → `phase` + `assistant_message`. `GET /sessions/{id}` (full durable state: messages, hypotheses, fixes, phase) is the reload-after-refresh path, independent of the live event queue — a refreshed page doesn't rely on replaying missed SSE events.

**Endpoints** (`app/routers/sessions.py`): `POST /sessions` (repo_id + first message → creates + kicks off the engine, rate-limited by `sessions_per_ip_limit`), `GET /sessions/{id}/stream` (SSE, 15s heartbeat), `POST /sessions/{id}/messages` (rate-limited by `RATE_LIMIT_MESSAGES_PER_SESSION`, counted from the real `messages` table), `POST /sessions/{id}/fixes/{fix_id}/accept` and `/reject` (optional `feedback` text on either), `GET /sessions/{id}` (full state for reload). Every real user message updates `words_spoken_count`; synthetic accept/reject notes do not. Session titles are generated locally (`app/services/title.py`, first-sentence heuristic) rather than with an extra Gemini call, to keep session creation free and fast.

**Weak spot found during live testing, not yet fixed:** Gemini's `generateContent` endpoint returned a transient `503 "high demand"` once and otherwise hung (confirmed via raw `curl`, not an SDK bug) for sustained periods while testing this phase — see the Phase 3 progress log entry for the investigation and a proposed fix (treating 5xx like 429 — short cooldown + failover — which the pool deliberately does not do today).

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
      models/                # SQLAlchemy async models (incl. repo_file.py Phase 2, hypothesis.confidence Phase 3)
      schemas/
        events.py            # SSE event schema
        repo.py              # repo connect/list request+response schemas (Phase 2)
        session.py            # session create/message/fix-decision/state schemas (Phase 3)
      routers/
        repos.py             # connect + list-files endpoints (Phase 2)
        dev_tools.py         # curl-testable tool endpoints, ENABLE_DEV_TOOLS-gated (Phase 2)
        sessions.py           # create/stream/message/accept/reject/get-state (Phase 3)
      services/
        gemini_key_pool.py
        github_client.py      # tarball download + extraction/filtering (Phase 2)
        repo_service.py       # connect/cache/refresh orchestration (Phase 2)
        file_tools.py          # list_files/read_file/search_code (Phase 2)
        tool_declarations.py   # Gemini FunctionDeclaration schemas, file + control tools (Phase 2/3)
        control_tools.py        # ask_questions/state_hypothesis/propose_fix/mark_resolved + dispatch (Phase 3)
        conversation_engine.py  # the Gemini tool-calling loop + phase enforcement (Phase 3)
        session_events.py       # in-memory per-session SSE queue (Phase 3)
        system_prompt.py        # Duck's personality/rules, nothing else (Phase 3)
        title.py                 # local session-title heuristic, no Gemini call (Phase 3)
      core/
        rate_limit.py
      migrations/            # Alembic (async template)
    scripts/
      list_gemini_models.py
      chat.py                 # talk to Duck from the terminal against a real repo (Phase 3)
      evaluate.py              # runs all 3 taskboard bugs end-to-end, prints a report (Phase 3)
    tests/
```

```
/mnt/d/taskboard/        # separate repo, own git history — the sample buggy app
  backend/                # Express API, in-memory store
  frontend/               # React + Vite UI
```

## Phase plan

1. **Scaffolding & architecture** — monorepo, Next.js + FastAPI skeletons, Neon connection, migrations for every table (including `words_spoken_count`), Gemini key pool + tests, rate limiting core, health endpoints, SSE schema, env examples.
2. **Repo connection & smart file selection** — GitHub client (one-shot tarball download + extraction, not per-file fetches or code search), `list_files`/`read_file`/`search_code` tools, connect-a-repo endpoint, sample buggy repo goes live on GitHub with documented root causes.
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

### Phase 2 — complete (2026-10-22)

Built:
- **GitHub client** (`app/services/github_client.py`): strict public-`github.com`-only URL validation (with/without `.git`, with/without trailing slash); `fetch_repo_metadata` (1 call, also rejects private repos even if a token could see them) + `download_tarball` (1 call, follows the redirect to codeload); `extract_text_files` filters directories/lock-files/minified/binary/oversized content and rejects the whole repo over the file-count or total-byte cap before storing anything. All caps and the GitHub timeout are env vars (see `.env.example`). No per-file API calls, no code search API — exactly the pivot requested, since both are slow/rate-limited in ways that would break a live demo.
- **`repo_files` table** (migration `0002_repo_files`): `repo_id, file_path, content, size_bytes, language, created_at`, unique on `(repo_id, file_path)`. `repos.file_tree_cache` (unused under the new approach) dropped; `repos.last_indexed_at` added to drive cache reuse/refresh.
- **`repo_service.connect_repo`**: reuses the stored copy if `last_indexed_at` is within `REPO_CACHE_TTL_SECONDS` (default 1h), otherwise re-downloads and replaces all `repo_files` rows for that repo atomically. Dedupes by a canonicalized `https://github.com/{owner}/{repo}` URL so `.git`/trailing-slash variants of the same repo don't create duplicates.
- **File tools** (`app/services/file_tools.py`): `list_files` / `read_file` / `search_code`, DB-backed async wrappers over DB-free pure functions (`*_pure`) for unit testability. Line-numbered `read_file` with truncation + total line count; glob/prefix matching via `fnmatch` for `list_files`; `search_code` with literal (always-safe) or regex search, a per-line length cap before regex matching, and a worker-thread + `asyncio.wait_for` timeout so a pathological pattern can't hang a request. Path-traversal strings (`..`, leading `/`, empty segments) are rejected before any DB lookup. Every tool output is capped at `TOOL_OUTPUT_MAX_CHARS`. `read_file`/`search_code` optionally take `session_id` + an `emit` callback to write `file_reads` rows and emit `tool_call` SSE events — both unused for now (no session/turn endpoint exists until Phase 3) but the call sites are ready.
- **Gemini tool declarations** (`app/services/tool_declarations.py`): `types.FunctionDeclaration` for all three tools, bundled as `FILE_TOOLS`, ready for Phase 3's `GenerateContentConfig(tools=[FILE_TOOLS])`. **Correction from Phase 3:** this originally used `parameters_json_schema={...}` (confirmed against the *current* hosted SDK docs at the time) — but nothing actually instantiated it until Phase 3 wired up real tool-calling, which immediately failed: the pinned `google-genai==1.3.0` in `requirements.txt` predates that field and only accepts `parameters=types.Schema(...)`. Fixed in Phase 3 across all seven tool declarations (file + control). Lesson: "confirmed against current docs" isn't the same as "confirmed against the installed version" — a declaration that's never instantiated in a test can hide a breaking SDK mismatch indefinitely.
- **Endpoints**: `POST /repos/connect`, `GET /repos/{repo_id}/files`, and dev-only `POST /dev/tools/{list_files,read_file,search_code}` — the dev router is only imported/registered in `main.py` when `ENABLE_DEV_TOOLS=true`, so it's structurally absent (not just 403'd) when that's unset.
- **Sample buggy repo**: a separate repo at `/mnt/d/taskboard` (own git history, 4 commits, MIT licensed), Express backend + React/Vite frontend, 22 tracked files. Three planted bugs (seconds/milliseconds unit mismatch in the frontend token-expiry check, an off-by-one pagination offset on the backend, a stale-closure polling interval in a React hook) — verified by hand: ran the Express server and confirmed `GET /api/tasks?page=1` actually skips the first 5 seeded tasks; `npm run build` on the frontend succeeds. Answer key at `docs/sample_bugs.md` in **this** repo (not in taskboard, so Duck can't read its own answers).
- Everything DB-dependent is exercised through pure functions + fixture tarballs in the default unit-test run (no network, no DB). Two integration tests are skipped by default: `test_integration_github.py` (real network, needs `RUN_GITHUB_INTEGRATION_TESTS=1` + `TASKBOARD_GITHUB_OWNER` once taskboard is pushed) and `test_integration_db.py` (real Postgres, needs `RUN_DB_INTEGRATION_TESTS=1` + a migrated `DATABASE_URL`; GitHub itself is mocked in this one so it only exercises our DB code).

Verified: `pytest` → 68 passed, 2 skipped by design (the integration tests above). `alembic upgrade head --sql` → compiles (0001 + 0002). `python -c "import app.main"` → succeeds. taskboard: `npm start` (backend) + manual curl confirmed the pagination bug; `npm run build` (frontend) succeeds.

### Phase 3 — complete (2026-10-23)

Built (see "Conversation engine" section above for the architecture in full):
- **Four control tools** (`ask_questions`, `state_hypothesis`, `propose_fix`, `mark_resolved`) in `app/services/control_tools.py`, dispatched alongside the three file tools through one `control_tools.dispatch()` entry point. Phase legality is computed fresh on every call via `allowed_tools_for_phase` — never cached, never scripted — so a wrong-phase or invalid call gets a same-turn correctable error instead of either executing wrongly or crashing the loop.
- **Diffs are backend-built, never model-written**: `propose_fix` validates the file and line range against the real stored content, then `difflib.unified_diff` produces the actual diff. Verified in `test_control_tools.py` with a real invalid-range rejection and a real diff byte-for-byte check.
- **State machine change from the original plan**: Duck investigates before it's ever allowed to ask a clarifying question (`listening` flips to `investigating` immediately on session creation, before Gemini is called once). Clarifying is optional, capped at 2 rounds, and gated on having read at least one file first. A rejected hypothesis (low-confidence pause) and a rejected fix both route back through `investigating`.
- **`conversation_engine.py`**: the Gemini tool-calling loop as a background task per turn. Per-call timeout (`GEMINI_CALL_TIMEOUT_SECONDS`), the daily-cap check inside the loop (not just once per turn), context compaction for old tool results (`GEMINI_CONTEXT_KEEP_RECENT_TOOL_RESULTS`), and a forced tools-disabled wrap-up call when `MAX_TOOL_CALLS_PER_TURN` is hit instead of failing silently.
- **Model fallback**: `GeminiKeyPool` now tracks health per `(key, model)`; `execute_with_fallback` retries every key on `GEMINI_FALLBACK_MODEL` only after every key is exhausted on `GEMINI_MODEL`. Confirmed via `scripts/list_gemini_models.py` that both `gemini-3.8-flash` and `gemini-3.6-flash` exist and support `generateContent` on the real account before pinning them as defaults.
- **In-memory per-session SSE queue** (`session_events.py`) and **in-memory Gemini-turn context** (`_ENGINE_STATE` in `conversation_engine.py`) — both explicit, documented instances of the same "Render's free tier is a single instance" tradeoff already accepted for the daily-call counter in Phase 1. `GET /sessions/{id}` is the durable, DB-backed reload path and doesn't depend on either.
- **Endpoints** (`app/routers/sessions.py`): create, SSE stream, send message, accept/reject fix, get full state — all wired to the existing rate limiter (`sessions_per_ip_limit` on create, the real per-session message count on send-message).
- **Local title generation** (`app/services/title.py`) — a first-sentence heuristic, deliberately not an extra Gemini call, to keep session creation instant and free.
- **`scripts/chat.py`** — talks to Duck from the terminal against a real connected repo, bypassing HTTP entirely (direct DB + engine calls, same pattern as `list_gemini_models.py`), printing the same SSE events nicely.
- **`scripts/evaluate.py`** — runs all three taskboard bugs end-to-end against the real `https://github.com/mohitjeswani01/taskboard`, using the exact symptom quotes from `docs/sample_bugs.md`, answering clarifying questions with a canned *observational* detail (timing/reproduction only — never file names or root cause), auto-accepting the proposed fix, and printing a per-bug report (resolved?, right file found?, root cause matched?, clarifying rounds, tool calls, Gemini calls, wall time). Budgeted to ~10 Gemini calls/bug (~30 total) via `--max-calls-per-bug`.
- **Testing**: `test_control_tools.py` (13 tests, real Neon DB, zero Gemini calls — exercises every handler, the phase gate, the round cap, the investigate-first gate, and real diff building) and `test_conversation_engine.py` (8 tests, a `ScriptedPool` stand-in for `GeminiKeyPool` returning scripted function-call sequences, zero Gemini calls) covering: the full happy path including skipped clarification, an explicit clarifying round that pauses and resumes, a low-confidence hypothesis rejected and re-investigated, a fix rejected and re-investigated, a wrong-phase tool call self-correcting within the turn, an invalid line range self-correcting within the turn, the tool-call cap forcing a wrap-up instead of failing silently, and all-keys-exhausted producing a friendly error. (Fallback-model *mechanics* — every key tried on the primary model before any key retries the fallback — are unit-tested at the pool level in `test_gemini_key_pool.py`, not re-mocked at the engine level.)
- **One schema change**: migration `0003_hypothesis_confidence` adds `hypotheses.confidence` (enum: low/medium/high, not stuffed into the existing `evidence` jsonb, since it drives backend control flow and should be typed/queryable). Applied to the real Neon DB.
- **One rename**: `MAX_TOOL_CALLS_PER_SESSION` → `MAX_TOOL_CALLS_PER_TURN` once the user clarified the cap is per-turn, not per-session (the default value didn't change, so nothing broke).
- **One bug found and fixed from Phase 2**: `tool_declarations.py`'s `parameters_json_schema` field doesn't exist on the pinned SDK version — see the corrected Phase 2 bullet above.
- **Two real bugs found only by testing live, both fixed** (see "Conversation engine" section above for full detail): function-call results sent with `role="tool"` (the real API rejects it — valid roles don't include `tool`; fixed to `role="user"`), and a `thought_signature` requirement from newer Gemini 3.x "thinking" models that `google-genai==1.3.0` predates entirely (fixed by upgrading to `google-genai==2.33.0`, which also pulled `pydantic` to 2.14.1 — re-verified all 92 tests pass unchanged on the new SDK).

**A real weak spot found live, not fixed:** while testing this phase against the live Gemini API, `generateContent` returned 503s ("high demand") and 429s, and otherwise hung for sustained periods — up to **803 seconds** on one isolated call — confirmed via raw `curl` too (not an SDK or code bug; `GET` requests to the same host returned instantly throughout, so this was real `generateContent`-specific load, not a local network issue). The key pool's Phase-1 design deliberately does **not** fail over on 5xx or on a timeout ("not the pool's concern, propagates immediately — only quota/auth errors drive pool state"), so a single struggling/hung key currently eats the full `GEMINI_CALL_TIMEOUT_SECONDS` and ends the turn with a generic error instead of trying the next key. Worth reconsidering before the demo: treating 503/504/timeout like 429 (short cooldown + same-call failover to the next key) would very plausibly have papered over most of what was observed live. Not changed in this phase since it reverses an explicit earlier design decision without being asked — flagged for a decision, not silently fixed.

**Live verification, not just mocks:** once both real bugs above were fixed, an end-to-end run against the actual `taskboard` repo and the real Gemini API (`gemini-3.8-flash`) correctly investigated the auth-expiry bug unprompted — called `list_files`, read all six relevant files (`session.js`, `auth.js`, `tokenService.js`, `App.jsx`, `authenticate.js`, `client.js`) without being told which ones, searched for `expiresAt`, skipped clarifying questions entirely since the symptom was already clear, and stated the hypothesis *"The backend sets `expiresAt` in seconds (Unix epoch seconds), but `millisecondsUntilExpiry` in `frontend/src/auth/session.js` directly subtracts `Date.now()` (in milliseconds) without converting..."* — the exact planted root cause, with the exact right file. It didn't reach `mark_resolved` within the run's 10-Gemini-call budget because the API kept timing out on subsequent calls (see weak spot above) — this is a quota/availability limit, not a reasoning or control-flow failure. The other two bugs' sessions never got a single successful response in their respective runs, for the same reason.

Verified: `pytest` → 92 passed, 2 skipped by design (the Phase 2 integration tests), unchanged across the `google-genai` upgrade. `alembic upgrade head` → applied `0003` to the real Neon DB. `python -c "import app.main"` → succeeds, all routes registered including `/sessions/*`. `scripts/list_gemini_models.py` → confirmed both pinned model names exist and support `generateContent`. Four live end-to-end attempts via `scripts/evaluate.py` against the real API across this phase's testing window, the first two of which surfaced the two real bugs above; the fourth (post-fix) produced the correct live investigation and hypothesis described above, cut short only by Gemini's own sustained instability during this specific window — re-running `scripts/evaluate.py` once that clears should go further.

### Next: Phase 4

Frontend chat experience: the big dictation-first textarea, the chat thread consuming `GET /sessions/{id}/stream`, the phase stepper, the diff viewer wired to `POST /sessions/{id}/fixes/{fix_id}/accept|reject`, and `POST /sessions` + `/sessions/{id}/messages` driving it all from the UI.
