"""Shared fixtures for Phase 3 tests that need a real database (Session,
Message, Hypothesis, Fix, RepoFile all use Postgres-specific column types —
UUID/ARRAY/JSONB/ENUM — that SQLite can't stand in for), with Gemini always
mocked so no quota is spent. Unlike the Phase 2 integration tests (gated
behind RUN_DB_INTEGRATION_TESTS, written when no DB existed yet), these
assume a working DATABASE_URL — true from Phase 3 onward for this project.
"""
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import FileRead, Fix, Hypothesis, Message, Repo, RepoFile
from app.models import Session as SessionModel

AUTH_JS_CONTENT = """function isTokenExpired(session) {
  return session.expiresAt - Date.now() <= 0;
}

function refreshIfNeeded(session) {
  if (isTokenExpired(session)) {
    return logout();
  }
}
"""

PAGINATION_JS_CONTENT = """function listTasks({ page, pageSize }) {
  const offset = page * pageSize;
  return tasks.slice(offset, offset + pageSize);
}
"""


@pytest.fixture(autouse=True)
async def _dispose_global_db_engine_after_test():
    """app.db.engine is a module-level singleton bound to whichever event
    loop first used it, but pytest-asyncio gives each test function a fresh
    loop. conversation_engine.run_turn uses that global engine (via
    AsyncSessionLocal), so without disposing its pool between tests, the
    next test's loop would try to reuse connections tied to a closed loop."""
    yield
    from app.db import engine as global_engine

    await global_engine.dispose()


@pytest.fixture
async def db_session_maker():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.fixture
async def repo_fixture(db_session_maker):
    """A throwaway repo with two small real files, so file tools have
    something to actually read during engine tests."""
    async with db_session_maker() as db:
        repo = Repo(id=uuid.uuid4(), github_url=f"https://github.com/test/{uuid.uuid4().hex[:8]}", owner="test", name="repo")
        db.add(repo)
        await db.flush()

        db.add(RepoFile(repo_id=repo.id, file_path="auth.js", content=AUTH_JS_CONTENT, size_bytes=len(AUTH_JS_CONTENT), language="JavaScript"))
        db.add(RepoFile(repo_id=repo.id, file_path="pagination.js", content=PAGINATION_JS_CONTENT, size_bytes=len(PAGINATION_JS_CONTENT), language="JavaScript"))
        await db.commit()

        repo_id = repo.id

    yield repo_id

    async with db_session_maker() as db:
        session_ids = (await db.execute(SessionModel.__table__.select().where(SessionModel.repo_id == repo_id))).fetchall()
        ids = [row.id for row in session_ids]
        if ids:
            await db.execute(delete(Fix).where(Fix.session_id.in_(ids)))
            await db.execute(delete(Hypothesis).where(Hypothesis.session_id.in_(ids)))
            await db.execute(delete(Message).where(Message.session_id.in_(ids)))
            await db.execute(delete(FileRead).where(FileRead.session_id.in_(ids)))
            await db.execute(delete(SessionModel).where(SessionModel.repo_id == repo_id))
        await db.execute(delete(RepoFile).where(RepoFile.repo_id == repo_id))
        await db.execute(delete(Repo).where(Repo.id == repo_id))
        await db.commit()


@pytest.fixture
async def session_fixture(db_session_maker, repo_fixture):
    """A fresh active session, already in the `investigating` phase (as the
    engine would set it right after the first user message)."""
    from app.models.enums import SessionPhase

    async with db_session_maker() as db:
        session = SessionModel(id=uuid.uuid4(), repo_id=repo_fixture, current_phase=SessionPhase.investigating)
        db.add(session)
        await db.commit()
        session_id = session.id

    yield session_id
