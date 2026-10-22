# taskboard — planted bugs (answer key)

**Do not reference this file from, or link it anywhere near, the taskboard repo
itself.** Duck only ever reads what it fetches from GitHub, so this staying
inside the duck repo is what keeps it an honest test. Used for checking Duck's
hypotheses during Phase 3 testing and for the demo script in later phases.

Repo: `https://github.com/<owner>/taskboard` (public, pushed separately — see
the push commands given at the end of Phase 2).

---

## Bug 1 — users get logged out almost immediately after logging in

**Symptom, as a frustrated user would say it out loud:**
"I log in and then like fifteen seconds later I'm back at the login screen.
It's supposed to keep me logged in for an hour — I didn't even get to look at
anything."

**Files involved:**
- `backend/src/services/tokenService.js` — issues `expiresAt` as
  `Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS`, i.e. **seconds** since
  the epoch (the same convention as a JWT `exp` claim).
- `frontend/src/auth/session.js` — `millisecondsUntilExpiry()` computes
  `session.expiresAt - Date.now()`. `Date.now()` is **milliseconds** since the
  epoch. Subtracting a seconds-epoch number from a milliseconds-epoch number
  gives a huge negative result.
- `frontend/src/App.jsx` — polls `getSessionAction(session)` every 15 seconds
  and acts on it; since `getSessionAction` sees `remaining <= 0` immediately,
  it always returns `"logout"`, never `"refresh"`.

**Root cause:** unit mismatch between a seconds-based expiry timestamp from
the backend and a milliseconds-based clock read on the frontend. The session
looks expired the instant it's checked, so the refresh path never fires and
the user is logged out on the next 15-second poll tick — not actually at the
one-hour mark.

**Correct fix:** convert consistently at the boundary. Either have the
backend return `expiresAt` in milliseconds (`Date.now() + SESSION_TTL_SECONDS * 1000`),
or convert on the frontend before comparing:

```js
export function millisecondsUntilExpiry(session) {
  return session.expiresAt * 1000 - Date.now();
}
```

The second is the smaller, more localized fix and doesn't change the API
contract (seconds-based expiry is the more conventional shape for a token
payload).

---

## Bug 2 — the first page of tasks is missing items

**Symptom:**
"Pagination is broken — when I load page 1, it's missing the first five
tasks. They only show up if I... actually they never show up, page 1 just
starts in the wrong place."

**Files involved:**
- `backend/src/services/taskStore.js` — `listTasks({ page, pageSize })`
  computes `const offset = page * pageSize;`.

**Root cause:** `page` is 1-indexed everywhere else in the API (and in the
frontend, which always requests `page=1` first), but the offset math treats it
as 0-indexed. For `page=1, pageSize=5`, `offset` evaluates to `5`, so the
first 5 tasks (indices 0–4) are permanently skipped — page 1 actually returns
what should be page 2's items, page 2 returns page 3's items, and the last
page of real data is dropped entirely.

**Correct fix:**

```js
const offset = (page - 1) * pageSize;
```

**How to verify:** with the 12 seeded tasks and the default `pageSize=5`,
`GET /api/tasks?page=1` currently returns tasks `t6`–`t10`; after the fix it
should return `t1`–`t5`.

---

## Bug 3 — changing the status filter works for a few seconds, then reverts

**Symptom:**
"I click 'Done' to filter the list, I see the done tasks for a second, and
then it just... goes back to showing everything. I didn't touch anything."

**Files involved:**
- `frontend/src/hooks/useTaskPolling.js` — two `useEffect` hooks:
  - one depends on `[token, filter]` and calls `load(filter)` immediately
    when the filter changes (this part works correctly).
  - the other depends on `[token]` only, and sets up a `setInterval` that
    calls `load(filter)` every 5 seconds.

**Root cause:** classic stale closure. The interval-creating effect only
re-runs when `token` changes (i.e., once, at login), so the `load` call inside
`setInterval`'s callback closes over whatever `filter` was at that time —
typically `{ status: "" }` (the "All" filter from initial load). Changing the
filter updates state and triggers the *first* effect to show the right list
immediately, but within 5 seconds the still-running interval from the *second*
effect fires with the stale `filter` and overwrites the task list with the
unfiltered results.

**Correct fix:** add `filter` to the second effect's dependency array (or
unify both effects into one that depends on `[token, filter]`, recreating the
interval whenever the filter changes):

```js
useEffect(() => {
  const interval = setInterval(() => {
    load(filter);
  }, POLL_INTERVAL_MS);

  return () => clearInterval(interval);
}, [token, filter]);
```

An equally valid fix is a `useRef` holding the latest `filter` that the
interval callback reads from, avoiding recreating the interval on every
filter change — either is acceptable; the test is whether Duck identifies the
missing dependency as the root cause.
