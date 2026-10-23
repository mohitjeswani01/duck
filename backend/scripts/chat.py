"""Talk to Duck from the terminal against a real, connected repo — no
frontend needed. Streams the same SSE events the real API would send,
printed as plain text.

Usage (from backend/, with the venv active and a real .env in place):

    python scripts/chat.py --repo-url https://github.com/owner/taskboard
    python scripts/chat.py --repo-id <uuid-of-an-already-connected-repo>

Then just talk. When Duck proposes a fix you'll be asked whether it worked;
answering "y" accepts it (continuing on to mark_resolved), "n" rejects it
(back to investigating), or type anything else as rejection feedback.
"""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import AsyncSessionLocal  # noqa: E402
from app.models import Fix, Repo  # noqa: E402
from app.models import Session as SessionModel  # noqa: E402
from app.models.enums import SessionPhase, SessionStatus  # noqa: E402
from app.services import session_events  # noqa: E402
from app.services.conversation_engine import TurnTrigger, run_turn  # noqa: E402
from app.services.repo_service import connect_repo  # noqa: E402
from app.services.title import generate_title  # noqa: E402

_TOOL_VERB = {"read_file": "reading", "search_code": "searching", "list_files": "listing"}


def _print_event(event) -> None:
    if event.type == "phase":
        print(f"\n--- phase: {event.phase.value} ---")
    elif event.type == "tool_call":
        print(f"  [Duck is {_TOOL_VERB.get(event.tool, event.tool)}: {event.detail}]")
    elif event.type == "assistant_message":
        print(f"\nDuck: {event.content}")
    elif event.type == "diff":
        print(f"\n--- proposed fix: {event.file_path} ---\n{event.diff_text}\n")
    elif event.type == "error":
        print(f"\n!! {event.message}")


async def _watch_until_done(session_id: uuid.UUID, settings) -> None:
    while True:
        event = await session_events.next_event(session_id, settings.session_event_queue_max_size, timeout=0.5)
        if event is None:
            continue
        _print_event(event)
        if event.type == "done":
            return


async def _run_and_wait(session_id: uuid.UUID, trigger: TurnTrigger, settings) -> None:
    watcher = asyncio.create_task(_watch_until_done(session_id, settings))
    await run_turn(session_id, trigger)
    await watcher


async def _set_latest_fix_batch_accepted(session_id: uuid.UUID, accepted: bool) -> None:
    async with AsyncSessionLocal() as db:
        fixes = (
            (await db.execute(select(Fix).where(Fix.session_id == session_id).order_by(Fix.created_at.desc())))
            .scalars()
            .all()
        )
        if not fixes:
            return
        latest_time = fixes[0].created_at
        for fix in fixes:
            if fix.created_at == latest_time:
                fix.accepted = accepted
        await db.commit()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-url", help="Public GitHub repo URL to connect (or reuse if already connected).")
    parser.add_argument("--repo-id", help="An already-connected repo's id, instead of --repo-url.")
    args = parser.parse_args()

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        if args.repo_id:
            repo = await db.get(Repo, uuid.UUID(args.repo_id))
            if repo is None:
                print(f"No repo with id {args.repo_id}. Connect one with --repo-url first.")
                return
        elif args.repo_url:
            result = await connect_repo(db, args.repo_url, settings)
            repo = result.repo
            print(f"Connected {repo.owner}/{repo.name}: {result.file_count} files (cached={result.reused_cached_copy})")
        else:
            parser.print_help()
            return

        first_message = input("\nDescribe the bug to Duck:\n> ").strip()
        if not first_message:
            print("Nothing to debug.")
            return

        title = generate_title(first_message)
        session = SessionModel(id=uuid.uuid4(), repo_id=repo.id, title=title)
        db.add(session)
        await db.commit()
        session_id = session.id

    print(f'\n[session {session_id} — "{title}"]')
    await _run_and_wait(session_id, TurnTrigger(kind="user_message", text=first_message), settings)

    while True:
        async with AsyncSessionLocal() as db:
            session = await db.get(SessionModel, session_id)
            phase, status = session.current_phase, session.status

        if status != SessionStatus.active:
            print("\n[session resolved — start a new one for a different bug]")
            break

        if phase == SessionPhase.fix_proposed:
            answer = input("\nDid that fix actually work? [y/n/say more]: ").strip()
            lowered = answer.lower()
            if lowered in ("y", "yes"):
                await _set_latest_fix_batch_accepted(session_id, True)
                await _run_and_wait(session_id, TurnTrigger(kind="fix_accepted"), settings)
            elif lowered in ("n", "no"):
                await _set_latest_fix_batch_accepted(session_id, False)
                await _run_and_wait(session_id, TurnTrigger(kind="fix_rejected"), settings)
            else:
                await _set_latest_fix_batch_accepted(session_id, False)
                await _run_and_wait(session_id, TurnTrigger(kind="fix_rejected", text=answer), settings)
            continue

        message = input("\nYou: ").strip()
        if message.lower() in ("quit", "exit"):
            break
        if not message:
            continue
        await _run_and_wait(session_id, TurnTrigger(kind="user_message", text=message), settings)


if __name__ == "__main__":
    asyncio.run(main())
