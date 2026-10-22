"""End-to-end repo connect + file tools against a real Postgres database.
Skipped by default — set RUN_DB_INTEGRATION_TESTS=1 and a real DATABASE_URL
(e.g. Neon, after `alembic upgrade head`) to run. GitHub itself is mocked via
an httpx.MockTransport so this only exercises our DB code, not the network.
"""
import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.models import Repo, RepoFile
from app.services import file_tools, repo_service

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_INTEGRATION_TESTS") != "1",
    reason="set RUN_DB_INTEGRATION_TESTS=1 and DATABASE_URL to a real, migrated Postgres to run",
)

FAKE_TARBALL_OWNER_REPO = ("demo-owner", "demo-repo")


def _fake_tarball() -> bytes:
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path, content in {"index.js": b"console.log('hi');", "README.md": b"# demo"}.items():
            info = tarfile.TarInfo(name=f"demo-repo-sha/{path}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_connect_repo_and_run_tools_against_real_db(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def fake_fetch_repo_metadata(owner, repo, settings):
        return {"default_branch": "main", "private": False}

    async def fake_download_tarball(owner, repo, ref, settings):
        return _fake_tarball()

    monkeypatch.setattr(repo_service, "fetch_repo_metadata", fake_fetch_repo_metadata)
    monkeypatch.setattr(repo_service, "download_tarball", fake_download_tarball)

    owner, name = FAKE_TARBALL_OWNER_REPO
    github_url = f"https://github.com/{owner}/{name}"

    async with session_maker() as db:
        result = await repo_service.connect_repo(db, github_url, settings)
        assert result.file_count == 2
        repo_id = result.repo.id

        list_result = await file_tools.list_files(db, repo_id, settings)
        assert {f.path for f in list_result.files} == {"index.js", "README.md"}

        read_result = await file_tools.read_file(db, repo_id, "index.js", settings)
        assert "console.log" in read_result.content

        search_result = await file_tools.search_code(db, repo_id, "demo", settings)
        assert search_result.total_matches == 1

        # Cleanup: this test writes real rows, so remove them after asserting.
        await db.execute(delete(RepoFile).where(RepoFile.repo_id == repo_id))
        await db.delete(await db.get(Repo, repo_id))
        await db.commit()

    await engine.dispose()
