"""Runs Duck against all three planted taskboard bugs end-to-end, using the
exact symptom descriptions from docs/sample_bugs.md (in the duck repo, not
taskboard — Duck never sees this file). Clarifying questions get a canned,
purely observational answer drawn from that same answer key (never the file
names, line numbers, or root cause — only things a real user could notice),
or "please investigate" if Duck asks a second round. Proposed fixes are
auto-accepted. Prints a report per bug.

Budgeted to stay around ~30 Gemini calls total across all three bugs by
default (10/bug) — pass --max-calls-per-bug to change it.

Usage (from backend/, venv active):
    python scripts/evaluate.py --repo-url https://github.com/<owner>/taskboard
"""
import argparse
import asyncio
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import AsyncSessionLocal  # noqa: E402
from app.models import FileRead, Fix, Repo  # noqa: E402
from app.models import Session as SessionModel  # noqa: E402
from app.models.enums import SessionPhase, SessionStatus  # noqa: E402
from app.services import session_events  # noqa: E402
from app.services.conversation_engine import TurnTrigger, run_turn  # noqa: E402
from app.services.repo_service import connect_repo  # noqa: E402
from app.services.title import generate_title  # noqa: E402

_MAX_TURNS_PER_BUG = 20  # safety valve, independent of the Gemini-call budget


@dataclass
class BugSpec:
    key: str
    symptom: str
    extra_details: str
    expected_file_substrings: list[str]
    expected_root_cause_keywords: list[str]


BUGS = [
    BugSpec(
        key="auth-expiry",
        symptom=(
            "I log in and then like fifteen seconds later I'm back at the login screen. "
            "It's supposed to keep me logged in for an hour, I didn't even get to look at anything."
        ),
        extra_details=(
            "It happens every single time, really fast, within 15 to 20 seconds of logging in, "
            "nowhere close to an hour. It's completely consistent, not random."
        ),
        expected_file_substrings=["session.js", "tokenService.js", "App.jsx"],
        expected_root_cause_keywords=["second", "millisecond", "unit", "expiresat", "date.now"],
    ),
    BugSpec(
        key="pagination-offset",
        symptom=(
            "Pagination is broken, when I load page 1 it's missing the first five tasks. "
            "They only show up if... actually they never show up, page 1 just starts in the wrong place."
        ),
        extra_details=(
            "Page 1 skips the first 5 tasks entirely, it shows what should be page 2's tasks instead. "
            "It's consistently off by one page's worth, every page."
        ),
        expected_file_substrings=["taskStore.js"],
        expected_root_cause_keywords=["off-by-one", "offset", "page", "index"],
    ),
    BugSpec(
        key="stale-filter",
        symptom=(
            "I click 'Done' to filter the list, I see the done tasks for a second, and then it just "
            "goes back to showing everything. I didn't touch anything."
        ),
        extra_details=(
            "It reverts after about 5 seconds, every time, no matter which filter I pick. The filter "
            "button still looks selected, but the list itself goes back to showing all tasks."
        ),
        expected_file_substrings=["useTaskPolling.js"],
        expected_root_cause_keywords=["stale", "closure", "useeffect", "dependency", "interval"],
    ),
]


@dataclass
class BugResult:
    key: str
    resolved: bool
    found_expected_file: bool
    matched_root_cause: bool
    clarifying_rounds: int
    tool_calls: int
    gemini_calls: int
    seconds: float
    root_cause_text: str
    files_read: set = field(default_factory=set)


async def _drain_and_print(session_id: uuid.UUID, settings) -> None:
    while True:
        event = await session_events.next_event(session_id, settings.session_event_queue_max_size, timeout=0.5)
        if event is None:
            continue
        if event.type == "tool_call":
            print(f"    [tool] {event.tool}: {event.detail}")
        elif event.type == "assistant_message":
            print(f"    Duck: {event.content[:220]}")
        elif event.type == "phase":
            print(f"    -> phase: {event.phase.value}")
        elif event.type == "error":
            print(f"    !! {event.message}")
        if event.type == "done":
            return


async def run_bug(repo: Repo, bug: BugSpec, settings, max_calls: int) -> BugResult:
    async with AsyncSessionLocal() as db:
        session = SessionModel(id=uuid.uuid4(), repo_id=repo.id, title=generate_title(bug.symptom))
        db.add(session)
        await db.commit()
        session_id = session.id

    print(f"\n=== {bug.key} ===\n> {bug.symptom}")

    total_gemini_calls = 0
    total_tool_calls = 0
    clarifying_rounds = 0
    start = time.monotonic()
    trigger = TurnTrigger(kind="user_message", text=bug.symptom)

    for _ in range(_MAX_TURNS_PER_BUG):
        watcher = asyncio.create_task(_drain_and_print(session_id, settings))
        metrics = await run_turn(session_id, trigger)
        await watcher
        total_gemini_calls += metrics.gemini_calls
        total_tool_calls += metrics.tool_calls

        if total_gemini_calls >= max_calls:
            print(f"    [eval] hit the {max_calls}-call budget for this bug, stopping here")
            break

        async with AsyncSessionLocal() as db:
            session = await db.get(SessionModel, session_id)
            phase, status = session.current_phase, session.status

        if status != SessionStatus.active:
            break

        if phase == SessionPhase.clarifying:
            clarifying_rounds += 1
            answer = bug.extra_details if clarifying_rounds == 1 else (
                "Please investigate, I've told you everything I've noticed on my end."
            )
            trigger = TurnTrigger(kind="user_message", text=answer)
            continue

        if phase == SessionPhase.hypothesis:
            trigger = TurnTrigger(kind="user_message", text="Yes, that matches what I'm seeing.")
            continue

        if phase == SessionPhase.fix_proposed:
            async with AsyncSessionLocal() as db:
                fixes = (
                    (await db.execute(select(Fix).where(Fix.session_id == session_id).order_by(Fix.created_at.desc())))
                    .scalars()
                    .all()
                )
                if fixes:
                    latest_time = fixes[0].created_at
                    for f in fixes:
                        if f.created_at == latest_time:
                            f.accepted = True
                    await db.commit()
            trigger = TurnTrigger(kind="fix_accepted")
            continue

        # No phase change and nothing left to drive this turn — done or stuck.
        break

    seconds = time.monotonic() - start

    async with AsyncSessionLocal() as db:
        session = await db.get(SessionModel, session_id)
        resolved = session.status == SessionStatus.resolved
        root_cause_text = f"{session.root_cause or ''} {session.resolution_summary or ''}".strip()

        file_reads = (await db.execute(select(FileRead).where(FileRead.session_id == session_id))).scalars().all()
        files_read = {fr.file_path for fr in file_reads}

    found_expected_file = any(any(sub in path for path in files_read) for sub in bug.expected_file_substrings)
    matched_root_cause = any(kw in root_cause_text.lower() for kw in bug.expected_root_cause_keywords)

    return BugResult(
        key=bug.key,
        resolved=resolved,
        found_expected_file=found_expected_file,
        matched_root_cause=matched_root_cause,
        clarifying_rounds=clarifying_rounds,
        tool_calls=total_tool_calls,
        gemini_calls=total_gemini_calls,
        seconds=seconds,
        root_cause_text=root_cause_text,
        files_read=files_read,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-url", required=True, help="Public GitHub URL of the taskboard repo.")
    parser.add_argument("--max-calls-per-bug", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        connect_result = await connect_repo(db, args.repo_url, settings)
        repo = connect_result.repo
        print(
            f"Connected {repo.owner}/{repo.name}: {connect_result.file_count} files "
            f"(cached={connect_result.reused_cached_copy})"
        )

    results = [await run_bug(repo, bug, settings, args.max_calls_per_bug) for bug in BUGS]

    print("\n" + "=" * 72)
    print("EVALUATION REPORT")
    print("=" * 72)
    total_calls = 0
    for r in results:
        total_calls += r.gemini_calls
        print(f"\n[{r.key}]")
        print(f"  resolved:            {r.resolved}")
        print(f"  found expected file: {r.found_expected_file}  (read: {sorted(r.files_read)})")
        print(f"  root cause matched:  {r.matched_root_cause}")
        print(f"  root cause/summary:  {r.root_cause_text[:200]!r}")
        print(f"  clarifying rounds:   {r.clarifying_rounds}")
        print(f"  tool calls:          {r.tool_calls}")
        print(f"  gemini calls:        {r.gemini_calls}")
        print(f"  time:                {r.seconds:.1f}s")

    print(f"\nTOTAL Gemini calls across all bugs: {total_calls}")


if __name__ == "__main__":
    asyncio.run(main())
