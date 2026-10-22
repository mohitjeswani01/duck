"""Connects a repo: validates the URL, reuses a fresh stored copy if one
exists, otherwise downloads+extracts a tarball and replaces the stored copy.
"""
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Repo, RepoFile
from app.services.github_client import (
    download_tarball,
    extract_text_files,
    fetch_repo_metadata,
    parse_github_url,
)


@dataclass(frozen=True)
class RepoConnectResult:
    repo: Repo
    file_count: int
    total_size_bytes: int
    languages: dict[str, int]
    reused_cached_copy: bool


def _is_fresh(repo: Repo, ttl_seconds: int) -> bool:
    if repo.last_indexed_at is None:
        return False
    age = datetime.now(timezone.utc) - repo.last_indexed_at
    return age.total_seconds() < ttl_seconds


async def _summarize_stored_files(db: AsyncSession, repo_id: uuid.UUID) -> tuple[int, int, dict[str, int]]:
    result = await db.execute(
        select(RepoFile.language, func.count(), func.sum(RepoFile.size_bytes))
        .where(RepoFile.repo_id == repo_id)
        .group_by(RepoFile.language)
    )
    languages: dict[str, int] = {}
    file_count = 0
    total_size = 0
    for language, count, size_sum in result.all():
        languages[language] = count
        file_count += count
        total_size += size_sum or 0
    return file_count, total_size, languages


async def connect_repo(db: AsyncSession, github_url: str, settings: Settings) -> RepoConnectResult:
    owner, name = parse_github_url(github_url)
    canonical_url = f"https://github.com/{owner}/{name}"

    existing = await db.scalar(select(Repo).where(Repo.github_url == canonical_url))

    if existing is not None and _is_fresh(existing, settings.repo_cache_ttl_seconds):
        file_count, total_size, languages = await _summarize_stored_files(db, existing.id)
        return RepoConnectResult(
            repo=existing,
            file_count=file_count,
            total_size_bytes=total_size,
            languages=languages,
            reused_cached_copy=True,
        )

    metadata = await fetch_repo_metadata(owner, name, settings)
    default_branch = metadata["default_branch"]
    tarball = await download_tarball(owner, name, default_branch, settings)
    extracted = extract_text_files(tarball, settings)

    if existing is not None:
        repo = existing
        repo.owner = owner
        repo.name = name
        repo.default_branch = default_branch
    else:
        repo = Repo(id=uuid.uuid4(), github_url=canonical_url, owner=owner, name=name, default_branch=default_branch)
        db.add(repo)
        await db.flush()

    await db.execute(delete(RepoFile).where(RepoFile.repo_id == repo.id))
    for file in extracted.files:
        db.add(
            RepoFile(
                repo_id=repo.id,
                file_path=file.path,
                content=file.content,
                size_bytes=file.size_bytes,
                language=file.language,
            )
        )

    repo.last_indexed_at = datetime.now(timezone.utc)
    await db.commit()

    languages = dict(Counter(f.language for f in extracted.files))
    total_size = sum(f.size_bytes for f in extracted.files)

    return RepoConnectResult(
        repo=repo,
        file_count=len(extracted.files),
        total_size_bytes=total_size,
        languages=languages,
        reused_cached_copy=False,
    )
