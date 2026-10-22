from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Repo, RepoFile
from app.schemas.repo import RepoConnectRequest, RepoConnectResponse, RepoFileOut, RepoOut
from app.services.github_client import (
    GithubClientError,
    GithubRateLimitError,
    GithubUnavailableError,
    InvalidRepoUrlError,
    RepoNotFoundError,
    RepoPrivateError,
    RepoTooLargeError,
)
from app.services.repo_service import connect_repo

router = APIRouter(prefix="/repos", tags=["repos"])

_ERROR_STATUS = {
    InvalidRepoUrlError: 422,
    RepoNotFoundError: 404,
    RepoPrivateError: 422,
    RepoTooLargeError: 422,
    GithubRateLimitError: 429,
    GithubUnavailableError: 503,
}


def _to_repo_out(repo: Repo) -> RepoOut:
    return RepoOut(
        id=str(repo.id),
        github_url=repo.github_url,
        owner=repo.owner,
        name=repo.name,
        default_branch=repo.default_branch,
    )


@router.get("", response_model=list[RepoOut])
async def list_repos(db: AsyncSession = Depends(get_db)) -> list[RepoOut]:
    """Lists connected repos."""
    result = await db.execute(select(Repo))
    repos = result.scalars().all()
    return [_to_repo_out(repo) for repo in repos]


@router.post("/connect", response_model=RepoConnectResponse)
async def connect_repo_endpoint(
    body: RepoConnectRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepoConnectResponse:
    """Downloads (or reuses a fresh stored copy of) a public GitHub repo and
    stores its filtered text files, ready for the file tools to query."""
    try:
        result = await connect_repo(db, body.github_url, settings)
    except GithubClientError as exc:
        status_code = _ERROR_STATUS.get(type(exc), 502)
        raise HTTPException(status_code=status_code, detail=exc.friendly_message) from exc

    return RepoConnectResponse(
        repo=_to_repo_out(result.repo),
        file_count=result.file_count,
        total_size_bytes=result.total_size_bytes,
        languages=result.languages,
        reused_cached_copy=result.reused_cached_copy,
    )


@router.get("/{repo_id}/files", response_model=list[RepoFileOut])
async def list_repo_files(repo_id: UUID, db: AsyncSession = Depends(get_db)) -> list[RepoFileOut]:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found. Connect it first via POST /repos/connect.")

    result = await db.execute(select(RepoFile).where(RepoFile.repo_id == repo_id).order_by(RepoFile.file_path))
    files = result.scalars().all()
    return [
        RepoFileOut(path=f.file_path, size_bytes=f.size_bytes, language=f.language, created_at=f.created_at)
        for f in files
    ]
